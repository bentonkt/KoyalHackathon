"""Explicit tabletop control mapping; never a metric free-space pose."""

import math

import cv2
import numpy as np


def map_planar_samples(samples, corners, stage_width=1.0, stage_depth=1.0):
    """Map image anchors through ordered TL, TR, BR, BL stage corners.

    Coordinates are virtual stage units. Height/parallax are not recovered.
    Return copies, preserving pixel evidence and loss states.
    """
    points = np.asarray(corners, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Four finite ordered stage corners are required")
    if not all(math.isfinite(v) and v > 0 for v in (stage_width, stage_depth)):
        raise ValueError("Stage dimensions must be finite and positive")
    contour = points.reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 1:
        raise ValueError("Stage corners must form a nondegenerate convex rectangle projection")
    target = np.array([[0, 0], [stage_width, 0], [stage_width, stage_depth], [0, stage_depth]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(points, target)
    result = []
    for sample in samples:
        updated = dict(sample, position_stage=None, stage_units="virtual", geometry_mode="table_control")
        xy = sample.get("position_px")
        if xy is not None and sample.get("position_status") in ("VALID", "DEGRADED"):
            anchor = np.asarray(xy, dtype=float)
            if anchor.shape != (2,) or not np.isfinite(anchor).all():
                raise ValueError("Invalid pixel anchor")
            homogeneous = matrix @ np.array([*anchor, 1.0])
            if abs(homogeneous[2]) < 1e-9:
                updated.update(position_status="LOST", reason="stage_projection_invalid")
            else:
                updated["position_stage"] = (homogeneous[:2] / homogeneous[2]).tolist()
        result.append(updated)
    return result
