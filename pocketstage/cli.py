"""Offline-first checkpoint A runner. This CLI never submits paid model jobs."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def _emit(value):
    print(json.dumps(value, indent=2, allow_nan=False))


def _write_new(path, value):
    from .media import atomic_write_json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Check JSON finiteness before atomic publication.
    json.dumps(value, allow_nan=False)
    atomic_write_json(path, value)


def _decode(path):
    import cv2

    cap = cv2.VideoCapture(str(path))
    frames = []
    try:
        if not cap.isOpened():
            raise ValueError("Cannot decode proxy")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
            if len(frames) > 300:
                raise ValueError("Spike supports at most 300 proxy frames")
    finally:
        cap.release()
    if not frames:
        raise ValueError("Proxy has no decoded frames")
    return frames


def _track(project, manifest, region, start_frame=0, corners=None):
    from .tracking import track_frames
    from .geometry import map_planar_samples
    import hashlib

    project = Path(project).resolve()
    proxy = manifest["proxy"]
    path = (project / proxy["path"]).resolve()
    if not path.is_relative_to(project):
        raise ValueError("Proxy path escapes project")
    if hashlib.sha256(path.read_bytes()).hexdigest() != proxy["sha256"]:
        raise ValueError("Proxy hash mismatch; immutable take has changed")
    frames = _decode(path)
    if len(frames) != proxy["frame_count"]:
        raise ValueError("Proxy decode count differs from manifest")
    result = track_frames(frames, proxy["timestamps"], region, start_frame=start_frame)
    if corners is not None:
        result["samples"] = map_planar_samples(result["samples"], corners)
    candidate_id = str(uuid.uuid4())
    result.update(schema_version=1, candidate_id=candidate_id, take_id=manifest["id"],
                  method="opencv_baseline", accepted=False, proxy_sha256=proxy["sha256"],
                  selection={"region": region, "start_frame": start_frame},
                  stage_corners=corners, depth_status="UNAVAILABLE", mask_provider="none")
    output = project / "candidates" / f"{candidate_id}.json"
    _write_new(output, result)
    valid = sum(s["position_status"] == "VALID" for s in result["samples"])
    return {"candidate": str(output), "valid_samples": valid, "total_samples": len(frames),
            "accepted": False, "scope": "offline baseline spike; not Phase 1 certified"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check dependencies and credential presence without disclosing keys")
    demo = sub.add_parser("demo", help="Generate/import/track a synthetic 5-second clip offline")
    demo.add_argument("--project", type=Path, required=True)
    imp = sub.add_parser("import", help="Preserve a local video and prepare its canonical proxy")
    imp.add_argument("video", type=Path)
    imp.add_argument("--project", type=Path, required=True)
    track = sub.add_parser("track", help="Create an unaccepted baseline candidate from a saved take")
    track.add_argument("--project", type=Path, required=True)
    track.add_argument("--take", required=True, help="Take UUID")
    track.add_argument("--region", type=float, nargs=4, required=True, metavar=("X", "Y", "W", "H"))
    track.add_argument("--start-frame", type=int, default=0)
    track.add_argument("--corners", type=float, nargs=8, help="Ordered TL TR BR BL proxy pixel corners")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            _emit({"python": sys.version.split()[0],
                   "dependencies": {name: importlib.util.find_spec(name) is not None for name in ("cv2", "numpy")},
                   "ffmpeg": shutil.which("ffmpeg") is not None,
                   "ffprobe": shutil.which("ffprobe") is not None,
                   "fal_key_configured": bool(os.environ.get("FAL_KEY")),
                   "sponsor_coverage": "unverified", "sam2_mask_contract": "unverified",
                   "paid_jobs_submitted": False})
        elif args.command == "import":
            from .media import import_take
            _emit(import_take(args.video, args.project))
        elif args.command == "track":
            # A UUID is a reference, never an arbitrary file path.
            take_id = str(uuid.UUID(args.take))
            manifest = json.loads((args.project / "takes" / take_id / "manifest.json").read_text())
            corners = None if args.corners is None else [args.corners[i:i+2] for i in range(0, 8, 2)]
            _emit(_track(args.project, manifest, args.region, args.start_frame, corners))
        elif args.command == "demo":
            import cv2
            from .tracking import generate_fixture
            from .media import import_take

            frames, _, region, _ = generate_fixture()
            directory = args.project / "fixtures" / str(uuid.uuid4())
            directory.mkdir(parents=True, exist_ok=False)
            fixture = directory / "synthetic.mp4"
            writer = cv2.VideoWriter(str(fixture), cv2.VideoWriter_fourcc(*"mp4v"), 15, (320, 240))
            if not writer.isOpened():
                raise ValueError("Synthetic video writer unavailable")
            try:
                for frame in frames:
                    writer.write(frame)
            finally:
                writer.release()
            manifest = import_take(fixture, args.project, fps=15, height=240)
            summary = _track(args.project, manifest, region, corners=[[0, 0], [320, 0], [320, 240], [0, 240]])
            summary.update(take_id=manifest["id"], synthetic=True, real_object_validated=False)
            _emit(summary)
        return 0
    except subprocess.CalledProcessError:
        print("PocketStage: media conversion failed; no ready take was published", file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        print(f"PocketStage: {error}", file=sys.stderr)
        return 2
