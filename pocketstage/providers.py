"""Offline contract helpers for the proposed fal PocketStage adapters.

This module deliberately does not contain a fal client.  It builds payloads and
validates downloaded artifacts after a caller has applied consent, billing, and
job-lifecycle policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import urlparse
import math
import zipfile

import numpy as np


SAM2_MODEL = "fal-ai/sam2/video"
DEPTH_MODEL = "fal-ai/depth-anything-video"


def _https_url(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise ValueError(f"{name} must be an absolute HTTPS URL without credentials")
    return value


def sam2_request(video_url: str, prompts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Build, but do not submit, one ``fal-ai/sam2/video`` request."""
    video_url = _https_url(video_url, "video_url")
    if isinstance(prompts, (str, bytes)) or not isinstance(prompts, Sequence) or not prompts:
        raise ValueError("prompts must be a non-empty sequence of prompt mappings")
    clean_prompts: list[dict[str, object]] = []
    for prompt in prompts:
        if not isinstance(prompt, Mapping) or not prompt:
            raise ValueError("each prompt must be a non-empty mapping")
        if set(prompt) != {"x", "y", "label", "frame_index"}:
            raise ValueError("each prompt must contain exactly x, y, label, and frame_index")
        for key in ("x", "y", "frame_index"):
            value = prompt[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{key} must be a non-negative integer")
        if (
            isinstance(prompt["label"], bool)
            or not isinstance(prompt["label"], int)
            or prompt["label"] not in (0, 1)
        ):
            raise ValueError("label must be integer 0 or 1")
        clean_prompts.append(dict(prompt))
    return {"model": SAM2_MODEL, "input": {"video_url": video_url, "prompts": clean_prompts}}


def depth_request(video_url: str) -> dict[str, object]:
    """Build, but do not submit, the fixed VDA-Small depth request."""
    return {
        "model": DEPTH_MODEL,
        "input": {
            "video_url": _https_url(video_url, "video_url"),
            "model": "VDA-Small",
            "include_raw_depths": True,
        },
    }


def contract_report(
    sam_result: Mapping[str, object] | None,
    depth_result: Mapping[str, object] | None,
) -> dict[str, object]:
    """Describe artifact availability without promoting it to validation evidence."""
    sam = sam_result if isinstance(sam_result, Mapping) else {}
    depth = depth_result if isinstance(depth_result, Mapping) else {}
    return {
        "mask_contract": {
            "status": "unverified",
            "usable_raw_masks": False,
            "reason": "segmented video and bounding-box frame ZIP are not a documented raw-mask contract",
            "segmented_video_available": bool(sam.get("video")),
            "boundingbox_frames_zip_available": bool(sam.get("boundingbox_frames_zip")),
        },
        "depth_contract": {
            "status": "unverified",
            "raw_depth_url_available": bool(depth.get("raw_depths")),
            "raw_depth_validated": False,
            "alignment_proven": False,
        },
        "endpoint_contract_passed": False,
    }


def load_raw_depths(
    path: str | Path,
    expected_shape: tuple[int, int, int],
    expected_fps: float,
    *,
    max_uncompressed_bytes: int = 128 * 1024 * 1024,
    max_compression_ratio: float = 200.0,
) -> np.ndarray:
    """Safely load a bounded NPZ ``depths`` array; shape alone does not prove alignment."""
    if len(expected_shape) != 3 or any(type(v) is not int or v <= 0 for v in expected_shape):
        raise ValueError("expected_shape must be a positive (N, H, W) tuple")
    if not np.isfinite(expected_fps) or expected_fps <= 0:
        raise ValueError("expected_fps must be positive and finite")
    if max_uncompressed_bytes <= 0 or max_compression_ratio <= 0:
        raise ValueError("archive limits must be positive")
    expected_elements = math.prod(expected_shape)
    if expected_elements > max_uncompressed_bytes:
        raise ValueError("expected_shape exceeds the allocation limit")
    archive_path = Path(path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if not infos:
                raise ValueError("depth NPZ is empty")
            if len({info.filename for info in infos}) != len(infos):
                raise ValueError("depth NPZ contains duplicate member names")
            total = 0
            for info in infos:
                if info.is_dir() or info.flag_bits & 0x1:
                    raise ValueError("depth NPZ contains a directory or encrypted member")
                member = Path(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError("depth NPZ contains an unsafe member path")
                total += info.file_size
                if total > max_uncompressed_bytes:
                    raise ValueError("depth NPZ exceeds the uncompressed-size limit")
                denominator = max(info.compress_size, 1)
                if info.file_size / denominator > max_compression_ratio:
                    raise ValueError("depth NPZ exceeds the compression-ratio limit")
            members = {info.filename: info for info in infos}
            for array_name in ("depths", "shape", "fps"):
                member_name = f"{array_name}.npy"
                if member_name not in members:
                    continue
                with archive.open(member_name) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version == (1, 0):
                        shape, _fortran, dtype = np.lib.format.read_array_header_1_0(stream)
                    elif version in ((2, 0), (3, 0)):
                        shape, _fortran, dtype = np.lib.format.read_array_header_2_0(stream)
                    else:
                        raise ValueError("depth NPZ contains an unsupported NPY version")
                    if dtype.hasobject:
                        raise ValueError("depth NPZ contains an object array")
                    elements = math.prod(shape) if shape else 1
                    required = elements * dtype.itemsize
                    payload_available = members[member_name].file_size - stream.tell()
                    if required > max_uncompressed_bytes or required > payload_available:
                        raise ValueError("depth NPZ array header exceeds allocation or member bounds")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("invalid depth NPZ archive") from exc

    try:
        with np.load(archive_path, allow_pickle=False) as data:
            if "depths" not in data.files:
                raise ValueError("depth NPZ must contain a 'depths' array")
            depths = np.array(data["depths"], copy=True)
            if "shape" in data.files:
                recorded_shape = tuple(int(v) for v in np.asarray(data["shape"]).reshape(-1))
                if recorded_shape != expected_shape:
                    raise ValueError("depth metadata shape does not match expected_shape")
            if "fps" not in data.files:
                raise ValueError("depth NPZ must include fps metadata for temporal alignment")
            recorded_fps = float(np.asarray(data["fps"]).reshape(()))
    except (OSError, EOFError, zipfile.BadZipFile) as exc:
        raise ValueError("could not load depth NPZ") from exc

    if depths.shape != expected_shape or depths.ndim != 3:
        raise ValueError("depths must match expected (N, H, W) shape")
    if not np.issubdtype(depths.dtype, np.floating):
        raise ValueError("depths must have a floating dtype")
    if not np.all(np.isfinite(depths)):
        raise ValueError("depths contain non-finite values")
    if not np.isfinite(recorded_fps) or not np.isclose(recorded_fps, expected_fps, rtol=1e-6, atol=1e-6):
        raise ValueError("depth fps metadata does not match expected_fps")
    return depths


def validate_binary_masks(array: np.ndarray, expected_shape: tuple[int, int, int]) -> np.ndarray:
    """Validate numeric binary frames, returning bool; object identity remains unverified."""
    masks = np.asarray(array)
    if masks.ndim != 3 or masks.shape != expected_shape:
        raise ValueError("masks must match expected (N, H, W) shape; color overlays are unsupported")
    if masks.dtype == np.bool_:
        return masks.copy()
    if not np.issubdtype(masks.dtype, np.number) or not np.all(np.isfinite(masks)):
        raise ValueError("masks must be finite numeric or boolean data")
    values = np.unique(masks)
    if not (np.all(np.isin(values, (0, 1))) or np.all(np.isin(values, (0, 255)))):
        raise ValueError("masks must use only 0/1 or 0/255 values")
    return masks != 0
