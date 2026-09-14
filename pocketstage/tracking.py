"""Small, fail-closed OpenCV tracking baseline.

This estimates only an image-plane control trajectory.  It deliberately does
not claim object identity, depth, heading, or 6-DoF pose.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

import cv2
import numpy as np


def _sample(time_s: float, status: str, reason: str, position=None) -> dict:
    return {
        "time_s": float(time_s),
        "position_px": None if position is None else [float(position[0]), float(position[1])],
        "position_status": status,
        "reason": reason,
        "heading_rad": None,
        "heading_status": "UNAVAILABLE",
        "depth_relative": None,
        "depth_status": "UNAVAILABLE",
    }


def _validate(frames, timestamps_s, region, start_frame, masks):
    if not isinstance(frames, Sequence) or not frames:
        raise ValueError("frames must be a non-empty sequence")
    if len(frames) != len(timestamps_s):
        raise ValueError("frames and timestamps_s must have equal length")
    if not isinstance(start_frame, int) or not 0 <= start_frame < len(frames):
        raise ValueError("start_frame is out of range")
    ts = np.asarray(timestamps_s, dtype=np.float64)
    if ts.ndim != 1 or not np.all(np.isfinite(ts)) or np.any(np.diff(ts) <= 0):
        raise ValueError("timestamps_s must be finite and strictly increasing")
    if len(region) != 4 or not np.all(np.isfinite(region)):
        raise ValueError("region must be [x, y, width, height]")
    x, y, w, h = map(float, region)
    first = np.asarray(frames[0])
    if first.ndim not in (2, 3) or first.dtype != np.uint8:
        raise ValueError("frames must be uint8 grayscale or BGR arrays")
    height, width = first.shape[:2]
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
        raise ValueError("region is outside the frame")
    for frame in frames:
        a = np.asarray(frame)
        if a.dtype != np.uint8 or a.shape[:2] != (height, width) or a.ndim not in (2, 3):
            raise ValueError("all frames must be aligned uint8 arrays")
        if a.ndim == 3 and a.shape[2] not in (3, 4):
            raise ValueError("color frames must have 3 or 4 channels")
    if masks is not None:
        if not isinstance(masks, Sequence) or len(masks) != len(frames):
            raise ValueError("masks must be a frame-aligned sequence")
        for mask in masks:
            a = np.asarray(mask)
            if a.ndim != 2 or a.shape != (height, width):
                raise ValueError("each mask must match the frame dimensions")
            if not np.all(np.isfinite(a)) or not np.all(np.isin(a, (0, 1, 255))):
                raise ValueError("masks must contain only 0/1/255 values")
    return x, y, w, h


def _gray(frame):
    return frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY if frame.shape[2] == 4 else cv2.COLOR_BGR2GRAY)


def _interior(mask):
    binary = (np.asarray(mask) != 0).astype(np.uint8) * 255
    return cv2.erode(binary, np.ones((3, 3), np.uint8), iterations=1)


def generate_fixture(frame_count=75, width=320, height=240, fps=15):
    """Return a deterministic textured translating-patch smoke-test fixture."""
    if frame_count <= 0 or width < 200 or height < 160 or fps <= 0:
        raise ValueError("fixture dimensions, count, and fps must be positive and usable")
    rng = np.random.default_rng(901)
    texture = cv2.GaussianBlur(rng.integers(25, 235, (58, 72, 3), dtype=np.uint8), (3, 3), 0)
    frames, expected = [], []
    x0, y0, dx, dy = 36, 72, 1.25, .55
    base = np.zeros((height, width, 3), np.uint8)
    base[y0:y0 + 58, x0:x0 + 72] = texture
    support0 = np.zeros((height, width), np.uint8)
    support0[y0:y0 + 58, x0:x0 + 72] = 255
    for i in range(frame_count):
        x, y = x0 + dx * i, y0 + dy * i
        matrix = np.float32([[1, 0, x - x0], [0, 1, y - y0]])
        moved = cv2.warpAffine(base, matrix, (width, height))
        support = cv2.warpAffine(support0, matrix, (width, height))
        frame = np.full((height, width, 3), 12, np.uint8)
        frame[support != 0] = moved[support != 0]
        frames.append(frame)
        expected.append([x + 36, y + 29])
    return frames, [i / fps for i in range(frame_count)], [x0, y0, 72, 58], expected


def track_frames(frames, timestamps_s, region, start_frame=0, masks=None) -> dict:
    """Track a reviewed region forward, stopping permanently at first loss."""
    x, y, w, h = _validate(frames, timestamps_s, region, start_frame, masks)
    result = {"samples": []}
    for i in range(start_frame):
        result["samples"].append(_sample(timestamps_s[i], "UNAVAILABLE", "before_start_frame"))

    previous = _gray(np.asarray(frames[start_frame]))
    feature_mask = np.zeros(previous.shape, np.uint8)
    feature_mask[int(y):int(math.ceil(y + h)), int(x):int(math.ceil(x + w))] = 255
    if masks is not None:
        feature_mask = cv2.bitwise_and(feature_mask, _interior(masks[start_frame]))
    points = cv2.goodFeaturesToTrack(previous, maxCorners=120, qualityLevel=.01,
                                     minDistance=5, blockSize=5, mask=feature_mask)
    anchor = np.array([x + w / 2.0, y + h / 2.0, 1.0], np.float64)
    accumulated = np.eye(3, dtype=np.float64)
    if points is None or len(points) < 6:
        reason = "insufficient_initial_features"
        result["samples"].append(_sample(timestamps_s[start_frame], "LOST", reason))
        for i in range(start_frame + 1, len(frames)):
            result["samples"].append(_sample(timestamps_s[i], "LOST", "not_reacquired_after_loss"))
        return result
    result["samples"].append(_sample(timestamps_s[start_frame], "VALID", "initialized", anchor[:2]))

    lost = False
    for i in range(start_frame + 1, len(frames)):
        if lost:
            result["samples"].append(_sample(timestamps_s[i], "LOST", "not_reacquired_after_loss"))
            continue
        current = _gray(np.asarray(frames[i]))
        nxt, ok1, err = cv2.calcOpticalFlowPyrLK(previous, current, points, None,
                                                winSize=(21, 21), maxLevel=3)
        if nxt is None or ok1 is None or err is None or not np.all(np.isfinite(nxt)):
            lost = True
            result["samples"].append(_sample(timestamps_s[i], "LOST", "optical_flow_failed"))
            continue
        back, ok2, _ = cv2.calcOpticalFlowPyrLK(current, previous, nxt, None,
                                                winSize=(21, 21), maxLevel=3)
        if back is None or ok2 is None or not np.all(np.isfinite(back)):
            lost = True
            result["samples"].append(_sample(timestamps_s[i], "LOST", "reverse_optical_flow_failed"))
            continue
        good = (ok1.ravel() != 0) & (ok2.ravel() != 0)
        good &= np.linalg.norm(points.reshape(-1, 2) - back.reshape(-1, 2), axis=1) <= 1.25
        good &= err.ravel() <= 30.0
        raw_dest = nxt.reshape(-1, 2)
        finite = np.all(np.isfinite(raw_dest), axis=1)
        dest = np.rint(np.where(finite[:, None], raw_dest, -1)).astype(int)
        in_bounds = (finite & (dest[:, 0] >= 0) & (dest[:, 0] < current.shape[1]) &
                         (dest[:, 1] >= 0) & (dest[:, 1] < current.shape[0]))
        good &= in_bounds
        if masks is not None:
            supported = np.zeros(len(dest), dtype=bool)
            ids = np.flatnonzero(in_bounds)
            m = _interior(masks[i]) != 0
            supported[ids] = m[dest[ids, 1], dest[ids, 0]]
            good &= supported
        src, dst = points.reshape(-1, 2)[good], nxt.reshape(-1, 2)[good]
        transform = None
        inliers = None
        if len(src) >= 6:
            transform, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                                             ransacReprojThreshold=2.0,
                                                             maxIters=1000, confidence=.99)
        count = 0 if inliers is None else int(inliers.sum())
        spread_ok = False
        if count >= 6:
            supported_src = src[inliers.ravel() != 0]
            spans = np.ptp(supported_src, axis=0)
            spread_ok = spans[0] >= max(8.0, .18 * w) and spans[1] >= max(8.0, .18 * h)
        if transform is None or count < 6 or not spread_ok:
            lost = True
            result["samples"].append(_sample(timestamps_s[i], "LOST", "insufficient_geometric_support"))
            continue
        step = np.eye(3, dtype=np.float64)
        step[:2] = transform
        accumulated = step @ accumulated
        position = (accumulated @ anchor)[:2]
        if not np.all(np.isfinite(position)):
            lost = True
            result["samples"].append(_sample(timestamps_s[i], "LOST", "nonfinite_transform"))
            continue
        result["samples"].append(_sample(timestamps_s[i], "VALID", "tracked", position))
        points = dst[inliers.ravel() != 0].reshape(-1, 1, 2).astype(np.float32)
        previous = current
    return result
