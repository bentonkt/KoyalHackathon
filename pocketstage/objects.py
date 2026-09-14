"""Idempotent expansion of a cloud run with one additional SAM-tracked object."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

from .cloud import _lock, _save
from .providers import SAM2_MODEL, DEPTH_MODEL, sam2_request


def add_object_run(
    parent_directory, object_id, point, transport, *, upload_consent=False, sponsor_coverage=False
):
    parent = Path(parent_directory).resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", object_id or ""):
        raise ValueError("object_id must be a safe slug")
    state = json.loads((parent / "state.json").read_text())
    proxy = state["configuration"]["proxy"]
    if not isinstance(point, (tuple, list)) or len(point) != 3 or any(type(v) is not int for v in point):
        raise ValueError("point must be integer X Y FRAME")
    x, y, frame = point
    if not (0 <= x < proxy["width"] and 0 <= y < proxy["height"] and 0 <= frame < proxy["frame_count"]):
        raise ValueError("point must be within the canonical proxy")
    if not upload_consent or not sponsor_coverage:
        raise ValueError("upload consent and sponsor coverage are required")
    if not state.get("upload_consent") or not state.get("sponsor_coverage_confirmed_by_user"):
        raise ValueError("parent run lacks recorded consent or coverage")
    uploaded_url = state.get("uploaded_url")
    if not isinstance(uploaded_url, str):
        raise ValueError("parent run has no uploaded proxy URL")
    depth = state.get("jobs", {}).get("depth", {})
    configured_depth = state["configuration"].get("jobs", {}).get("depth", {})
    if configured_depth.get("model") != DEPTH_MODEL or depth.get("model") != DEPTH_MODEL:
        raise ValueError("parent depth model is incompatible")
    if depth.get("status") not in {"COMPLETED", "REVIEW_READY"} or not depth.get("request_id"):
        raise ValueError("parent depth job is not complete and reusable")

    identity = {"parent_run_id": state["run_id"], "object_id": object_id, "point": list(point)}
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    directory = parent.parent / run_id
    with _lock(directory):
        state_path = directory / "state.json"
        if state_path.exists():
            return dict(json.loads(state_path.read_text()), run_directory=str(directory))
        sam = sam2_request(uploaded_url, [{"x": x, "y": y, "label": 1, "frame_index": frame}])
        sam["input"].update(apply_mask=False, boundingbox_zip=False)
        configuration = copy.deepcopy(state["configuration"])
        configuration["jobs"]["sam2"] = sam
        new_state = {
            "run_id": run_id,
            "run_directory": str(directory),
            "parent_run_id": state["run_id"],
            "object_id": object_id,
            "configuration": configuration,
            "uploaded_url": uploaded_url,
            "upload_consent": True,
            "sponsor_coverage_confirmed_by_user": True,
            "status": "SUBMITTING",
            "jobs": {"depth": copy.deepcopy(depth)},
        }
        new_state["jobs"]["sam2"] = {"model": SAM2_MODEL, "status": "SUBMITTING", "request_id": None}
        _save(state_path, new_state)
        try:
            request_id = transport.submit(SAM2_MODEL, sam["input"])
            new_state["jobs"]["sam2"].update(request_id=request_id, status="QUEUED")
            new_state["status"] = "QUEUED"
            _save(state_path, new_state)
        except Exception as exc:
            new_state["status"] = "NEEDS_RECONCILIATION"
            new_state["error"] = "SAM submission failed or is uncertain; inspect provider requests before retrying"
            new_state["diagnostic_type"] = type(exc).__name__
            _save(state_path, new_state)
            raise RuntimeError(new_state["error"]) from None
        return new_state
