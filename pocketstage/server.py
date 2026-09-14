"""Loopback-only Capture Studio API for the established SAM 2 + depth pipeline."""

from __future__ import annotations

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
import uuid

from .cloud import load_key, plan_run, poll_run, start_run
from .demo import build_motion_demo
from .fal_transport import FalTransport
from .media import import_take
from .objects import add_object_run


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_ROOT = ROOT / "artifacts" / "capture-studio"
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_METADATA_BYTES = 32 * 1024
POLL_SECONDS = 2.0
JOB_TIMEOUT_SECONDS = 5 * 60
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
}


def _safe_object_ids(objects: list[dict]) -> list[str]:
    used: set[str] = set()
    output: list[str] = []
    for index, item in enumerate(objects):
        label = str(item.get("label", "")).strip().lower()
        slug = re.sub(r"[^a-z0-9_-]+", "-", label).strip("-_")[:20] or f"object-{index + 1}"
        candidate = slug
        suffix = 2
        while candidate in used:
            candidate = f"{slug[:17]}-{suffix}"
            suffix += 1
        used.add(candidate)
        output.append(candidate)
    return output


def _decode_metadata(value: str | None) -> dict:
    if not value or len(value) > MAX_METADATA_BYTES * 2:
        raise ValueError("Missing or oversized selection metadata")
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > MAX_METADATA_BYTES:
            raise ValueError
        metadata = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Invalid selection metadata") from None
    if not isinstance(metadata, dict) or metadata.get("upload_consent") is not True:
        raise ValueError("Explicit fal.ai upload consent is required")
    if metadata.get("sponsor_coverage") is not True:
        raise ValueError("Confirmed sponsored processing is required")
    objects = metadata.get("objects")
    if not isinstance(objects, list) or not 1 <= len(objects) <= 8:
        raise ValueError("Select between one and eight objects")
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("Each object selection must be an object")
        label = item.get("label")
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 24:
            raise ValueError("Object labels must contain 1 to 24 characters")
        if item.get("role") not in {"actor-a", "actor-b", "camera", "reference"}:
            raise ValueError("Invalid object role")
        for axis in ("x", "y"):
            value = item.get(axis)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Object points must use normalized coordinates")
    return metadata


class JobService:
    def __init__(self, jobs_root: Path = DEFAULT_JOBS_ROOT):
        self.jobs_root = Path(jobs_root)
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _state_path(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "api-state.json"

    def update(self, job_id: str, **changes) -> dict:
        path = self._state_path(job_id)
        with self._lock:
            state = json.loads(path.read_text())
            state.update(changes, updated_at=time.time())
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, indent=2, allow_nan=False) + "\n")
            os.replace(temporary, path)
            return state

    def read(self, job_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise FileNotFoundError
        state = json.loads(self._state_path(job_id).read_text())
        return {key: value for key, value in state.items() if key not in {"source_path", "project_path", "result_path"}}

    def create(self, source: Path, metadata: dict) -> dict:
        job_id = source.parent.name
        state = {
            "job_id": job_id,
            "status": "QUEUED",
            "stage": "PREPARING",
            "progress": 2,
            "message": "Video received. Preparing the canonical proxy.",
            "created_at": time.time(),
            "updated_at": time.time(),
            "source_path": str(source),
            "project_path": str(source.parent / "project"),
            "result_path": str(source.parent / "result"),
            "objects": metadata["objects"],
        }
        self._state_path(job_id).write_text(json.dumps(state, indent=2, allow_nan=False) + "\n")
        threading.Thread(target=self._process, args=(job_id,), daemon=True, name=f"capture-{job_id[:8]}").start()
        return self.read(job_id)

    def _wait_for_run(self, job_id: str, directory: Path, transport: FalTransport, deadline: float, message: str) -> dict:
        while time.monotonic() < deadline:
            state = poll_run(directory, transport)
            jobs = state.get("jobs", {})
            if state.get("status") == "REVIEW_READY":
                return state
            if any(job.get("status") in {"INSPECTION_OR_FETCH_FAILED", "NEEDS_RECONCILIATION"} for job in jobs.values()):
                raise RuntimeError("A model result could not be retrieved or validated; no replacement job was submitted")
            self.update(job_id, message=message, provider_jobs={name: job.get("status") for name, job in jobs.items()})
            time.sleep(POLL_SECONDS)
        raise TimeoutError("Model processing exceeded the five-minute local wait limit")

    def _process(self, job_id: str) -> None:
        try:
            private = json.loads(self._state_path(job_id).read_text())
            source = Path(private["source_path"])
            project = Path(private["project_path"])
            output = Path(private["result_path"])
            objects = private["objects"]
            object_ids = _safe_object_ids(objects)

            self.update(job_id, status="RUNNING", stage="PREPARING", progress=5, message="Creating and validating the 15 FPS analysis proxy.")
            manifest = import_take(source, project)
            proxy = manifest["proxy"]
            points = [
                (
                    min(proxy["width"] - 1, max(0, round(float(item["x"]) * (proxy["width"] - 1)))),
                    min(proxy["height"] - 1, max(0, round(float(item["y"]) * (proxy["height"] - 1)))),
                    0,
                )
                for item in objects
            ]
            key = load_key(ROOT / ".env")
            if not key:
                raise RuntimeError("FAL_KEY is not configured in the local backend")
            transport = FalTransport(key=key)
            deadline = time.monotonic() + JOB_TIMEOUT_SECONDS

            self.update(job_id, stage="UPLOADING", progress=12, message="Uploading the canonical proxy to fal.ai with your consent.")
            parent_plan = plan_run(project, manifest["id"], points[0])
            parent = start_run(parent_plan, transport, upload_consent=True, sponsor_coverage=True)
            parent_directory = Path(parent_plan["directory"])
            self.update(job_id, stage="SAM_DEPTH", progress=25, message="Running the first SAM 2 pass and shared Depth Anything pass.")
            self._wait_for_run(job_id, parent_directory, transport, deadline, "Waiting for SAM 2 and Depth Anything results.")

            run_directories: dict[str, Path] = {object_ids[0]: parent_directory}
            if len(objects) > 1:
                self.update(job_id, stage="SAM_OBJECTS", progress=55, message=f"Starting SAM 2 for {len(objects) - 1} additional objects; depth is reused.")
                for object_id, point in zip(object_ids[1:], points[1:]):
                    child = add_object_run(parent_directory, object_id, point, transport, upload_consent=True, sponsor_coverage=True)
                    run_directories[object_id] = Path(child["run_directory"])
                for index, (object_id, directory) in enumerate(list(run_directories.items())[1:], start=1):
                    progress = 55 + round(index / max(1, len(objects) - 1) * 25)
                    self.update(job_id, progress=progress, message=f"Waiting for SAM 2 object {index + 1} of {len(objects)} ({object_id}).")
                    self._wait_for_run(job_id, directory, transport, deadline, f"Waiting for SAM 2 tracking of {object_id}.")

            reference_index = next((index for index, item in enumerate(objects) if item["role"] == "reference"), 0)
            reference_id = object_ids[reference_index]
            static_ids = [object_id for object_id, item in zip(object_ids, objects) if item["role"] == "reference"]
            self.update(job_id, stage="RENDERING", progress=88, message="Building motion tracks and rendering the review video.")
            summary = build_motion_demo(run_directories, reference_id, static_ids, output, reviewed_masks=True)
            self.update(
                job_id,
                status="READY",
                stage="READY",
                progress=100,
                message="SAM 2 and Depth Anything processing is complete.",
                preview_url=f"/api/jobs/{job_id}/preview",
                tracks_url=f"/api/jobs/{job_id}/tracks",
                summary=summary,
            )
        except Exception as error:
            self.update(
                job_id,
                status="FAILED",
                stage="FAILED",
                message="Processing stopped safely.",
                error=str(error) if str(error) else type(error).__name__,
            )

    def artifact(self, job_id: str, name: str) -> Path:
        public = self.read(job_id)
        if public.get("status") != "READY":
            raise FileNotFoundError
        filename = "motion-preview.mp4" if name == "preview" else "motion-tracks.json"
        path = self.jobs_root / job_id / "result" / filename
        if not path.is_file():
            raise FileNotFoundError
        return path


class CaptureStudioHandler(BaseHTTPRequestHandler):
    server_version = "PocketStage/0.1"

    @property
    def service(self) -> JobService:
        return self.server.service  # type: ignore[attr-defined]

    def _origin(self) -> str | None:
        origin = self.headers.get("Origin")
        return origin if origin in ALLOWED_ORIGINS else None

    def _cors(self) -> None:
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            self.send_error(403)
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-PocketStage-Metadata, X-PocketStage-Filename, X-PocketStage-Job")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/jobs":
            self.send_error(404)
            return
        if self.headers.get("Origin") and not self._origin():
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 1 <= length <= MAX_UPLOAD_BYTES:
                raise ValueError("Video upload must be between 1 byte and 500 MB")
            metadata = _decode_metadata(self.headers.get("X-PocketStage-Metadata"))
            filename = self.headers.get("X-PocketStage-Filename", "video.mov")
            suffix = Path(filename).suffix.lower()
            if suffix not in {".mov", ".mp4", ".m4v"}:
                suffix = ".mov"
            requested_job_id = self.headers.get("X-PocketStage-Job", "")
            job_id = requested_job_id if re.fullmatch(r"[0-9a-f]{32}", requested_job_id) else uuid.uuid4().hex
            directory = self.service.jobs_root / job_id
            if directory.exists():
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                self._json(200, self.service.read(job_id))
                return
            directory.mkdir(parents=True, exist_ok=False)
            source = directory / f"incoming{suffix}"
            remaining = length
            with source.open("xb") as stream:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Video upload ended early")
                    stream.write(chunk)
                    remaining -= len(chunk)
            state = self.service.create(source, metadata)
            self._json(202, state)
        except (ValueError, OSError) as error:
            self._json(400, {"error": str(error)})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"status": "ok", "fal_key_configured": bool(load_key(ROOT / ".env"))})
            return
        match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})(?:/(preview|tracks))?", path)
        if not match:
            self.send_error(404)
            return
        try:
            job_id, artifact_name = match.groups()
            if not artifact_name:
                self._json(200, self.service.read(job_id))
                return
            artifact = self.service.artifact(job_id, artifact_name)
            self._file(artifact, download=artifact_name == "tracks")
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            self.send_error(404)

    def _file(self, path: Path, *, download: bool) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range")
        status = 200
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match:
                self.send_error(416)
                return
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
                end = min(int(raw_end), end) if raw_end else end
            elif raw_end:
                start = max(0, size - int(raw_end))
            if start > end or start >= size:
                self.send_error(416)
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, format: str, *args) -> None:
        print(f"Capture Studio API: {format % args}")


class CaptureStudioServer(ThreadingHTTPServer):
    def __init__(self, address, handler, service: JobService):
        super().__init__(address, handler)
        self.service = service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS_ROOT)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Capture Studio API must remain loopback-only")
    server = CaptureStudioServer((args.host, args.port), CaptureStudioHandler, JobService(args.jobs_root))
    print(f"Capture Studio API listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
