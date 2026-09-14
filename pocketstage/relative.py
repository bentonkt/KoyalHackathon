"""Conservative relative screen-plane and raw-depth annotations."""

from __future__ import annotations

import copy
import math

import numpy as np


def _erode3(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, constant_values=False)
    out = np.ones(mask.shape, dtype=bool)
    for y in range(3):
        for x in range(3):
            out &= padded[y : y + mask.shape[0], x : x + mask.shape[1]]
    return out


def attach_relative_depth(track, depths, masks, available):
    """Return a copy annotated with mask-median raw depth; no metric semantics."""
    result = copy.deepcopy(track)
    samples = result.get("samples")
    depth_array = np.asarray(depths)
    mask_array = np.asarray(masks)
    availability = np.asarray(available)
    if not isinstance(samples, list) or depth_array.ndim != 3:
        raise ValueError("track samples and (N,H,W) depths are required")
    if mask_array.shape != depth_array.shape or mask_array.dtype != np.bool_:
        raise ValueError("masks must be boolean and match depths")
    if availability.shape != (len(samples),) or availability.dtype != np.bool_:
        raise ValueError("available must be a boolean vector matching samples")
    if depth_array.shape[0] != len(samples) or not np.issubdtype(depth_array.dtype, np.floating):
        raise ValueError("depth frames must be floating and match samples")

    baseline = None
    for index, sample in enumerate(samples):
        sample.update(
            depth_raw=None,
            depth_delta_from_first_valid=None,
            depth_iqr=None,
            depth_status="UNAVAILABLE",
            depth_semantics="raw_relative_model_output_not_metres_or_near_far",
        )
        if sample.get("position_status") not in {"VALID", "DEGRADED"} or sample.get("position_px") is None:
            continue
        if not availability[index]:
            continue
        interior = _erode3(mask_array[index])
        values = depth_array[index][interior]
        values = values[np.isfinite(values)]
        if values.size < 9:
            sample["depth_status"] = "INSUFFICIENT_MASK_SUPPORT"
            continue
        median = float(np.median(values))
        q1, q3 = np.percentile(values, (25, 75))
        if baseline is None:
            baseline = median
        sample.update(
            depth_raw=median,
            depth_delta_from_first_valid=median - baseline,
            depth_iqr=float(q3 - q1),
            depth_status="RELATIVE_UNVALIDATED",
        )
    result["depth_provenance"] = {
        "identity_certified": False,
        "alignment_certified": False,
        "normalization": "none",
        "gap_interpolation": "none",
    }
    return result


def _position(sample):
    if sample.get("position_status") not in {"VALID", "DEGRADED"}:
        return None
    value = sample.get("position_normalized")
    if value is None:
        return None
    point = np.asarray(value, dtype=float)
    if point.shape != (2,) or not np.isfinite(point).all():
        return None
    return point


def relative_scene(tracks, reference_id, static_ids=()):
    """Subtract measured, simultaneous reference motion in normalized screen plane."""
    if reference_id not in tracks or not tracks:
        raise ValueError("reference_id must identify a track")
    ids = list(tracks)
    sample_lists = [tracks[object_id].get("samples") for object_id in ids]
    if any(not isinstance(samples, list) for samples in sample_lists):
        raise ValueError("each track must contain samples")
    count = len(sample_lists[0])
    if any(len(samples) != count for samples in sample_lists):
        raise ValueError("tracks must have equal sample counts")
    times = [float(sample["time_s"]) for sample in sample_lists[0]]
    for samples in sample_lists[1:]:
        other = [float(sample["time_s"]) for sample in samples]
        if len(other) != len(times) or any(not math.isclose(a, b, abs_tol=1e-9) for a, b in zip(times, other)):
            raise ValueError("tracks must use identical sample times")

    static = set(static_ids)
    unknown_static = static.difference(ids)
    if unknown_static:
        raise ValueError("static_ids must identify existing tracks")
    if any(not math.isfinite(value) for value in times) or any(
        current <= previous for previous, current in zip(times, times[1:])
    ):
        raise ValueError("sample times must be finite and strictly increasing")
    output_samples = []
    reference_samples = tracks[reference_id]["samples"]
    for index, time_s in enumerate(times):
        reference = reference_samples[index]
        reference_position = _position(reference)
        objects = {}
        for object_id in ids:
            sample = tracks[object_id]["samples"][index]
            point = _position(sample)
            valid = reference_position is not None and point is not None
            relative = (point - reference_position).tolist() if valid else None
            raw = sample.get("depth_raw")
            reference_raw = reference.get("depth_raw")
            raw_valid = valid and isinstance(raw, (int, float)) and isinstance(reference_raw, (int, float))
            raw_valid = raw_valid and math.isfinite(raw) and math.isfinite(reference_raw)
            objects[object_id] = {
                "position_relative": relative,
                "depth_difference_raw": float(raw - reference_raw) if raw_valid else None,
                "status": "RELATIVE_UNVALIDATED_IDENTITY" if valid else "REFERENCE_OR_OBJECT_GAP",
                "role": "static_measured" if object_id in static else "moving_measured",
            }
        output_samples.append({"time_s": time_s, "objects": objects})
    return {
        "reference_id": reference_id,
        "samples": output_samples,
        "tracks_absolute": copy.deepcopy(tracks),
        "semantics": "normalized_screen_plane_relative_to_measured_reference_not_3d_or_metres",
        "identity_certified": False,
        "static_policy": "role_only_coordinates_remain_measured",
    }
