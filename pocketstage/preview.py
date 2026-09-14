"""Offline, illustrative 2D motion preview renderer."""

from __future__ import annotations

from pathlib import Path
import math
import os
import subprocess
import tempfile

import cv2
import numpy as np

from .media import probe_video


def project_relative(position: list[float] | tuple[float, float] | None,
                     center: tuple[int, int], extent: tuple[int, int]) -> tuple[int, int] | None:
    """Project normalized image-relative x/y onto an illustrative stage."""
    if position is None or len(position) != 2:
        return None
    x, y = float(position[0]), float(position[1])
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return (int(round(center[0] + x * extent[0] / 2)),
            int(round(center[1] + y * extent[1] / 2)))


def _scene_point(object_id: str, reference_id: str, entry: dict,
                 center: tuple[int, int], extent: tuple[int, int], bound: float) -> tuple[int, int] | None:
    position = entry.get("position_relative")
    if position is None:
        return None
    if object_id == reference_id:
        return center
    return project_relative([float(position[0]) / bound, float(position[1]) / bound], center, extent)


def _fit(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))))
    canvas = np.full((height, width, 3), 22, np.uint8)
    x, y = (width - resized.shape[1]) // 2, (height - resized.shape[0]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def render_motion_preview(source_video: Path, scene: dict, output: Path) -> dict:
    """Render source beside a non-metric, top-down relative-motion diagram."""
    source_video, output = Path(source_video), Path(output)
    if output.exists():
        raise FileExistsError(output)
    samples = scene.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("scene.samples must be a non-empty list")
    metadata = probe_video(source_video)
    if len(samples) != metadata["frame_count"]:
        raise ValueError("scene sample count must equal source frame count")
    source_times = [value - metadata["timestamps"][0] for value in metadata["timestamps"]]
    for sample, expected in zip(samples, source_times):
        actual = float(sample.get("time_s"))
        if not math.isfinite(actual) or abs(actual - expected) > 1e-3:
            raise ValueError("scene sample times must match source presentation timestamps")
    ids = scene.get("object_ids") or list((scene.get("tracks") or {}).keys())
    if not ids:
        ids = sorted({key for sample in samples for key in sample.get("objects", {})})
    ids = [str(value) for value in ids]
    reference = str(scene.get("reference_id"))
    if reference not in ids:
        ids.insert(0, reference)
    valid_values = [abs(float(value)) for sample in samples for entry in sample.get("objects", {}).values()
                    if entry.get("position_relative") is not None for value in entry["position_relative"]
                    if math.isfinite(float(value))]
    display_bound = max(0.25, max(valid_values, default=0.25))

    capture = cv2.VideoCapture(str(source_video))
    fps = 1.0 / np.median(np.diff(source_times)) if len(source_times) > 1 else 15.0
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("source fps cannot be determined")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(suffix=".mp4", dir=output.parent)
    os.close(fd)
    os.unlink(temporary_name)
    temporary = Path(temporary_name)
    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, (960, 540))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("preview encoder could not open")
    colors = [(70, 210, 255), (255, 140, 80), (130, 230, 110), (220, 100, 220)]
    trails: dict[str, list[tuple[int, int]]] = {item: [] for item in ids}
    center, extent = (720, 285), (390, 360)
    rendered = 0
    try:
        for sample in samples:
            ok, source = capture.read()
            if not ok:
                raise ValueError("source decode ended before scene samples")
            frame = np.full((540, 960, 3), 18, np.uint8)
            frame[:, :480] = _fit(source, 480, 540)
            cv2.putText(frame, "SOURCE", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
            cv2.putText(frame, "RELATIVE MOTION (NON-METRIC)", (500, 30), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
            cv2.rectangle(frame, (510, 90), (930, 480), (80, 80, 80), 1)
            objects = sample.get("objects", {})
            for index, object_id in enumerate(ids):
                entry = objects.get(object_id, {})
                point = _scene_point(object_id, reference, entry, center, extent, display_bound)
                if point is None:
                    trails[object_id] = []
                    continue
                color = colors[index % len(colors)]
                trails[object_id].append(point)
                if len(trails[object_id]) > 1:
                    cv2.polylines(frame, [np.asarray(trails[object_id], np.int32)], False, color, 2)
                cv2.circle(frame, point, 8 if object_id == reference else 6, color, -1)
                status = str(entry.get("status", "unknown"))
                depth = entry.get("depth_difference_raw")
                depth_text = "depth raw: null" if depth is None else f"depth raw: {float(depth):.3g}"
                cv2.putText(frame, object_id, (point[0] + 10, point[1] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1)
                cv2.putText(frame, f"{object_id}: {status}; {depth_text}", (510, 55 + index * 17),
                            cv2.FONT_HERSHEY_SIMPLEX, .36, color, 1)
            cv2.putText(frame, "Fixed heading; raw depth is not physical height", (510, 520),
                        cv2.FONT_HERSHEY_SIMPLEX, .42, (190, 190, 190), 1)
            writer.write(frame)
            rendered += 1
    finally:
        writer.release()
        capture.release()
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(temporary), "-an",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        temporary.unlink(missing_ok=True)
    result = probe_video(output)
    if result["frame_count"] != rendered or result["width"] != 960 or result["height"] != 540:
        raise ValueError("rendered preview failed validation")
    return {"path": str(output), "frame_count": rendered, "width": 960, "height": 540,
            "fps": float(fps), "representation": "illustrative_non_metric", "heading": "fixed",
            "display_relative_bound": display_bound}
