"""Demo motion controls derived from SAM mask silhouettes.

These centroids are approximate image controls, not stable surface anchors,
identity guarantees, 3-D positions, or object poses.
"""

from __future__ import annotations

import cv2
import numpy as np


def _sample(time_s, status, reason, raw=None, area=None, new_segment=False):
    return {
        "time_s": float(time_s),
        "position_px": None,
        "raw_position_px": None if raw is None else [float(raw[0]), float(raw[1])],
        "position_normalized": None,
        "position_status": status,
        "reason": reason,
        "mask_area": None if area is None else int(area),
        "new_segment": bool(new_segment),
        "depth_relative": None,
        "heading_rad": None,
    }


def motion_from_masks(masks, available, timestamps_s) -> dict:
    """Convert aligned binary masks to a gap-aware silhouette-centroid track."""
    masks = np.asarray(masks)
    available = np.asarray(available)
    times = np.asarray(timestamps_s, dtype=np.float64)
    if masks.ndim != 3 or masks.dtype != np.bool_:
        raise ValueError("masks must be a bool array shaped [N,H,W]")
    count, height, width = masks.shape
    if count == 0 or height < 2 or width < 2:
        raise ValueError("masks must have non-empty frames at least 2x2")
    if available.shape != (count,) or available.dtype != np.bool_:
        raise ValueError("available must be a bool array of length N")
    if times.shape != (count,) or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("timestamps_s must be finite and strictly increasing")

    samples = []
    last_raw = None
    last_area = None
    prior_valid = False
    segment_pending = False
    diagonal = float(np.hypot(width, height))
    for index in range(count):
        if not available[index]:
            samples.append(_sample(times[index], "UNAVAILABLE", "mask_unavailable"))
            prior_valid = False
            segment_pending = True
            continue
        binary = masks[index].astype(np.uint8)
        total = int(binary.sum())
        if total < 20:
            samples.append(_sample(times[index], "LOST", "mask_empty_or_too_small", area=total))
            prior_valid = False
            segment_pending = True
            continue
        labels_count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
        if labels_count <= 1:
            samples.append(_sample(times[index], "LOST", "mask_empty_or_too_small", area=total))
            prior_valid = False
            segment_pending = True
            continue
        component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area = int(stats[component, cv2.CC_STAT_AREA])
        raw = centroids[component]
        reason = None
        if total > 0.4 * height * width:
            reason = "mask_too_large"
        elif area < 0.7 * total:
            reason = "fragmented_ambiguous_mask"
        elif prior_valid and last_area is not None and max(area / last_area, last_area / area) > 4.0:
            reason = "mask_area_jump"
        elif prior_valid and np.linalg.norm(raw - last_raw) > 0.2 * diagonal:
            reason = "centroid_jump"
        if reason:
            samples.append(_sample(times[index], "LOST", reason, area=area))
            prior_valid = False
            segment_pending = True
            continue
        is_new = segment_pending
        samples.append(_sample(times[index], "VALID", "new_segment" if is_new else "mask_centroid",
                               raw=raw, area=area, new_segment=is_new))
        last_raw, last_area, prior_valid, segment_pending = raw, area, True, False

    # Centered mean-of-three, confined to each contiguous VALID run. Endpoints use
    # the two available neighbors; gaps are never bridged or interpolated.
    i = 0
    while i < count:
        if samples[i]["position_status"] != "VALID":
            i += 1
            continue
        end = i
        while end + 1 < count and samples[end + 1]["position_status"] == "VALID":
            end += 1
        for j in range(i, end + 1):
            lo, hi = max(i, j - 1), min(end, j + 1)
            smoothed = np.mean([samples[k]["raw_position_px"] for k in range(lo, hi + 1)], axis=0)
            samples[j]["position_px"] = [float(smoothed[0]), float(smoothed[1])]
            samples[j]["position_normalized"] = [float(smoothed[0] / (width - 1)),
                                                   float(smoothed[1] / (height - 1))]
        i = end + 1
    return {
        "metadata": {
            "method": "sam_mask_centroid_demo",
            "units": "normalized_image",
            "identity_guarantee": False,
            "smoothing": "centered_mean_3_contiguous_valid_only",
        },
        "samples": samples,
    }
