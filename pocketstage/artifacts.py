"""Conservative, offline inspection of downloaded model artifacts."""

from __future__ import annotations

from pathlib import Path
import math

import cv2
import numpy as np

from .media import probe_video
from .providers import load_raw_depths


def _expectations(shape: tuple[int, int, int], fps: float) -> tuple[int, int, int, float]:
    if len(shape) != 3 or any(type(value) is not int or value <= 0 for value in shape):
        raise ValueError("expected_shape must be a positive (N, H, W) tuple")
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("expected_fps must be positive and finite")
    return shape[0], shape[1], shape[2], float(fps)


def inspect_sam_video(path: Path, expected_shape: tuple[int, int, int], expected_fps: float) -> dict:
    """Inspect whether a video merely looks like binary masks; never certify identity."""
    frames, height, width, fps = _expectations(expected_shape, expected_fps)
    metadata = probe_video(Path(path))
    geometry_match = (metadata["frame_count"], metadata["height"], metadata["width"]) == (frames, height, width)
    relative_times = [value - metadata["timestamps"][0] for value in metadata["timestamps"]]
    timing_match = len(relative_times) == frames and all(
        abs(actual - index / fps) <= max(1e-4, 0.02 / fps)
        for index, actual in enumerate(relative_times)
    )
    capture = cv2.VideoCapture(str(path))
    decoded = 0
    channels_agree = True
    near_binary = True
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            decoded += 1
            if image.ndim != 3 or image.shape[2] != 3:
                channels_agree = False
                near_binary = False
                continue
            spread = image.max(axis=2).astype(np.int16) - image.min(axis=2).astype(np.int16)
            channels_agree &= bool(np.all(spread <= 2))
            gray = image[:, :, 0]
            near_binary &= bool(np.all((gray <= 8) | (gray >= 247)))
    finally:
        capture.release()
    decoded_match = decoded == frames
    candidate = bool(geometry_match and timing_match and decoded_match and channels_agree and near_binary)
    return {
        "artifact_kind": "sam_video",
        "frame_count": metadata["frame_count"],
        "width": metadata["width"],
        "height": metadata["height"],
        "timestamps": relative_times,
        "expected_fps": fps,
        "geometry_match": geometry_match,
        "timing_match": timing_match,
        "decoded_frame_count_match": decoded_match,
        "channels_agree": channels_agree,
        "near_black_white": near_binary,
        "binary_candidate": candidate,
        "mask_contract": "requires_review",
        "object_identity": "unverified",
        "temporal_alignment": "unverified",
    }


def inspect_depth(path: Path, expected_shape: tuple[int, int, int], expected_fps: float) -> dict:
    """Validate bounded numeric depth data without claiming units or alignment."""
    frames, height, width, fps = _expectations(expected_shape, expected_fps)
    depths = load_raw_depths(Path(path), (frames, height, width), fps)
    return {
        "artifact_kind": "raw_depth",
        "valid_numeric_depth": True,
        "shape": [frames, height, width],
        "fps": fps,
        "minimum": float(np.min(depths)),
        "maximum": float(np.max(depths)),
        "units": "unknown",
        "temporal_alignment": "unverified",
        "model_confidence": None,
        "source_identity": "unverified",
    }


def extract_reviewed_sam_masks(path, expected_shape, expected_fps, *, start_frame, reviewed_binary_video=False):
    """Decode an explicitly reviewed B/W mask video, not arbitrary segmented RGB.

    H.264 edge pixels are thresholded only after grayscale/near-binary checks.
    Pre-prompt and empty/full-frame outputs are unavailable, never object masks.
    Availability does not certify object identity or accuracy.
    """
    if not reviewed_binary_video:
        raise ValueError('Mask video format must be visually reviewed before extraction')
    count,height,width,_=_expectations(expected_shape,expected_fps)
    if type(start_frame) is not int or not 0 <= start_frame < count:
        raise ValueError('Invalid prompt frame')
    report=inspect_sam_video(path,expected_shape,expected_fps)
    if not all(report[k] for k in ('geometry_match','timing_match','decoded_frame_count_match','channels_agree')):
        raise ValueError('Mask video geometry/timing/channels do not match the reviewed profile')
    if count*height*width > 128*1024*1024:
        raise ValueError('Mask array exceeds allocation limit')
    masks=np.zeros(expected_shape,dtype=bool)
    available=np.zeros(count,dtype=bool)
    capture=cv2.VideoCapture(str(path))
    gray_fractions=[]
    try:
        for index in range(count):
            ok,frame=capture.read()
            if not ok:
                raise ValueError('Mask decode ended early')
            if index<start_frame:
                continue
            gray=frame[:,:,0]
            fraction=float(np.mean((gray>8)&(gray<247)))
            if fraction>0.01:
                raise ValueError('Too much grayscale content for the reviewed binary-mask profile')
            gray_fractions.append(fraction)
            mask=gray>=128
            if mask.any() and not mask.all():
                masks[index]=mask
                available[index]=True
    finally:
        capture.release()
    return {'masks':masks,'available':available,'metadata':{
        'start_frame':start_frame,'threshold':128,'gray_edge_fraction_limit':0.01,
        'maximum_gray_edge_fraction':max(gray_fractions,default=0.0),
        'prefix_policy':'unavailable','availability_is_not_identity_confidence':True}}
