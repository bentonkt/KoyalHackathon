"""Immutable source ingestion and deterministic canonical proxy generation."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(args: list[str], **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def probe_video(path: Path) -> dict:
    """Return normalized video metadata and every decoded frame presentation time."""
    result = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name:stream_tags=rotate:stream_side_data=rotation:frame=best_effort_timestamp_time,pkt_duration_time",
        "-of", "json", str(path),
    ])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise ValueError(f"no video stream: {path}")
    frames = data.get("frames", [])
    if not frames:
        raise ValueError(f"video has no frames: {path}")
    timestamps: list[float] = []
    durations: list[float | None] = []
    for frame in frames:
        raw = frame.get("best_effort_timestamp_time")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("missing or invalid source frame timestamp") from exc
        if not math.isfinite(value) or (timestamps and value <= timestamps[-1]):
            raise ValueError("source frame timestamps must be finite and strictly increasing")
        timestamps.append(value)
        try:
            duration = float(frame.get("pkt_duration_time"))
            if not math.isfinite(duration) or duration <= 0:
                duration = None
        except (TypeError, ValueError):
            duration = None
        durations.append(duration)
    stream = streams[0]
    width, height = int(stream["width"]), int(stream["height"])
    rotations = [stream.get("tags", {}).get("rotate")]
    rotations.extend(item.get("rotation") for item in stream.get("side_data_list", []))
    try:
        rotation = next((float(value) for value in rotations if value is not None), 0.0)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid video rotation metadata") from exc
    if not math.isfinite(rotation) or abs(rotation) % 360 > 1e-6:
        raise ValueError("rotated video is unsupported by the canonical proxy spike")
    if width <= 0 or height <= 0 or width > 8192 or height > 8192 or len(timestamps) > 18_100:
        raise ValueError("invalid video dimensions")
    return {
        "codec": stream.get("codec_name"),
        "width": width,
        "height": height,
        "frame_count": len(timestamps),
        "timestamps": timestamps,
        "frame_durations": durations,
    }


def atomic_write_json(path: Path, value: dict) -> None:
    """Atomically publish new JSON; refuse to replace an existing record."""
    if path.exists():
        raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link provides atomic no-replace publication on the same filesystem.
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _duration(probe: dict) -> float:
    pts = probe["timestamps"]
    if probe["frame_durations"][-1] is not None:
        tail = probe["frame_durations"][-1]
    elif len(pts) > 1:
        tail = pts[-1] - pts[-2]
    else:
        raise ValueError("single-frame source lacks a frame duration")
    return pts[-1] - pts[0] + tail


def _mapping(probe: dict, fps: int) -> tuple[list[float], list[int]]:
    duration = _duration(probe)
    # ffprobe's decimal rendering can put an exact boundary a few microseconds
    # above the mathematical value (for example 0.600001 instead of 0.6).
    count = max(1, int(math.ceil((duration - 1e-5) * fps)))
    proxy_times = [i / fps for i in range(count)]
    relative = [p - probe["timestamps"][0] for p in probe["timestamps"]]
    indices: list[int] = []
    cursor = 0
    for target in proxy_times:
        while cursor + 1 < len(relative) and abs(relative[cursor + 1] - target) < abs(relative[cursor] - target):
            cursor += 1
        indices.append(cursor)
    return proxy_times, indices


def _proxy_dimensions(width: int, height: int, target_height: int) -> tuple[int, int]:
    out_h = min(height, target_height)
    out_h -= out_h % 2
    if out_h < 2:
        raise ValueError("target height is too small")
    out_w = int(round(width * out_h / height))
    out_w += out_w % 2
    return max(2, out_w), out_h


def _encode_selected(source: Path, destination: Path, probe: dict, indices: list[int], fps: int, size: tuple[int, int]) -> None:
    width, height = probe["width"], probe["height"]
    frame_bytes = width * height * 3
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(source), "-map", "0:v:0",
         "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    encoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-n", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-an",
         "-vf", f"scale={size[0]}:{size[1]}:flags=lanczos", "-c:v", "mpeg4", "-q:v", "3", str(destination)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    wanted = 0
    try:
        for source_index in range(probe["frame_count"]):
            frame = decoder.stdout.read(frame_bytes)
            if len(frame) != frame_bytes:
                raise ValueError(f"decoder produced only {source_index} complete frames")
            while wanted < len(indices) and indices[wanted] == source_index:
                encoder.stdin.write(frame)
                wanted += 1
        encoder.stdin.close()
        decoder.stdout.close()
        decoder_error = decoder.stderr.read().decode(errors="replace")
        encoder_error = encoder.stderr.read().decode(errors="replace")
        decoder_status, encoder_status = decoder.wait(), encoder.wait()
        decoder.stderr.close()
        encoder.stderr.close()
        encoder.stdout.close()
        if decoder_status or encoder_status or wanted != len(indices):
            raise RuntimeError(f"proxy conversion failed: {decoder_error} {encoder_error}".strip())
    except Exception:
        decoder.kill()
        encoder.kill()
        raise


def import_take(source: Path, project: Path, fps: int = 15, height: int = 480) -> dict:
    """Copy a source immutably, create its canonical proxy, and publish a ready manifest."""
    source, project = Path(source), Path(project)
    if (not source.is_file() or isinstance(fps, bool) or not isinstance(fps, int)
            or not 1 <= fps <= 30 or isinstance(height, bool) or not isinstance(height, int)
            or not 2 <= height <= 2160):
        raise ValueError("source must be a file, fps 1..30, and height 2..2160")
    project.joinpath("takes").mkdir(parents=True, exist_ok=True)
    while True:
        take_id = str(uuid.uuid4())
        take_dir = project / "takes" / take_id
        try:
            take_dir.mkdir()
            break
        except FileExistsError:
            continue
    stored_source = take_dir / f"source{source.suffix.lower()}"
    with source.open("rb") as incoming, stored_source.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    source_probe = probe_video(stored_source)
    if _duration(source_probe) > 10.05:
        raise ValueError("source duration exceeds the 10.05 second import limit")
    proxy_times, source_indices = _mapping(source_probe, fps)
    proxy_path = take_dir / "proxy.mp4"
    size = _proxy_dimensions(source_probe["width"], source_probe["height"], height)
    _encode_selected(stored_source, proxy_path, source_probe, source_indices, fps, size)
    proxy_probe = probe_video(proxy_path)
    timestamps_match = len(proxy_probe["timestamps"]) == len(proxy_times) and all(
        abs((actual - proxy_probe["timestamps"][0]) - expected) <= 1e-4
        for actual, expected in zip(proxy_probe["timestamps"], proxy_times)
    )
    if (proxy_probe["frame_count"] != len(proxy_times)
            or (proxy_probe["width"], proxy_probe["height"]) != size
            or not timestamps_match):
        raise ValueError("canonical proxy validation failed")
    source_hash, proxy_hash = _sha256(stored_source), _sha256(proxy_path)
    stored_source.chmod(0o444)
    proxy_path.chmod(0o444)
    manifest = {
        "id": take_id,
        "status": "ready",
        "source": {"path": str(stored_source.relative_to(project)), "sha256": source_hash, **source_probe},
        "proxy": {
            "path": str(proxy_path.relative_to(project)), "sha256": proxy_hash,
            "codec": proxy_probe["codec"], "width": size[0], "height": size[1],
            "fps": fps, "frame_count": len(proxy_times), "timestamps": proxy_times,
            "source_frame_indices": source_indices,
            "source_timestamps": [source_probe["timestamps"][i] for i in source_indices],
            "transform": {"kind": "scale", "source_width": source_probe["width"], "source_height": source_probe["height"]},
        },
    }
    atomic_write_json(take_dir / "manifest.json", manifest)
    return manifest
