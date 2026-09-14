# PocketStage — first implementation slice

This is the **offline checkpoint-A runner**, not the completed Phase 1 app. The intended full pipeline remains **SAM 2 Video masks + Video Depth Anything + local geometric solving**, with independent OpenCV fallback. No 6-DoF, scanning or GPU rental.

## Implemented

- Immutable local video import, original-file hashes, canonical 15-fps proxy and explicit source-frame/time mapping.
- Reviewed rectangular selection in proxy coordinates; OpenCV feature tracking, forward/backward checks and robust accumulated transforms.
- Optional binary-mask gating at the tracking interface; no assumption that a hosted segmented video is a mask.
- Fail-closed loss, missing prefixes, no automatic reacquisition or fabricated depth/heading.
- Explicit tabletop control mapping, separate from image-space evidence; virtual units, not measured 3D position.
- New, unaccepted trajectory candidates saved without overwriting previous results.
- Offline fal request builders, conservative contract reporting, bounded raw-depth NPZ and binary-mask validators.
- A deterministic synthetic clip and runnable local tests.

## Run on this Mac

The isolated environment has been installed in this directory. From this directory:

```sh
.venv/bin/python -m pocketstage doctor
.venv/bin/python -m pocketstage demo --project projects/demo
```

The demo creates a synthetic five-second clip, imports it, builds its proxy and saves a baseline candidate. It is **not evidence of reliable everyday-object tracking**.

On another machine, install Python 3.11+, FFmpeg (including ffprobe), then:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The development environment currently uses Python 3.14, NumPy 2.5.3 and OpenCV 4.14.0.94. Package ranges live in pyproject.toml; these observed versions are not a cross-platform compatibility guarantee.

## Try a real take

Use a fixed camera, a textured ordinary prop and an unobstructed start frame. Keep the clip at most ten seconds. This spike imports footage; it does not yet operate the webcam.

```sh
.venv/bin/python -m pocketstage import /absolute/path/take.mp4 --project projects/my-shot
.venv/bin/python -m pocketstage track --project projects/my-shot --take TAKE_UUID --region 40 60 90 80
```

Replace TAKE_UUID with the ID returned by import. Region is x, y, width, height **in the canonical proxy**, not necessarily the original video. Inspect `takes/TAKE_UUID/proxy.mp4` to choose it. Use `--start-frame` for later selection; earlier samples remain unavailable. Optional `--corners` accepts eight proxy-pixel coordinates in top-left, top-right, bottom-right, bottom-left order and maps them to a unit virtual stage.

Current output is JSON evidence, not a visual review UI. A candidate is always `accepted: false`; there is no implicit acceptance workflow hidden in this spike.

## Hosted integration status

No key is configured in this session. **No video has been uploaded, no hosted inference has run, and no money has been spent on inference or rented GPUs.** The CLI intentionally has no submit command yet.

`providers.py` prepares the two documented request shapes and checks locally supplied artifacts. It does not provide upload, queue, billing, consent, cancellation or completed adapter integration. Those must precede live submissions.

Before enabling hosted processing:

1. Configure `FAL_KEY` in the backend environment, never in frontend code or a committed file. Do not paste it into chat.
2. Confirm sponsor coverage, expiry and billing for both exact endpoints.
3. Obtain consent for the specific fixture upload.
4. Verify SAM 2 returns usable per-frame object masks—not just colored video or bounding-box overlays.
5. Verify raw depth and masks are aligned to the same proxy. Matching shapes/fps alone do not prove timing or semantic alignment.
6. Test near/far behavior and background drift before any relative-depth mapping. Nothing here reports metric depth.

Endpoint references: [SAM 2 Video](https://fal.ai/models/fal-ai/sam2/video/api), [Video Depth Anything](https://fal.ai/models/fal-ai/depth-anything-video/api).

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Run only the relevant test module after narrow changes. Tests cover synthetic motion/loss, stage mapping, media persistence/timing, provider contracts and CLI validation. Synthetic success does not certify hand occlusion, two-object identity or real-object accuracy.

Verified on September 14, 2026: **25 targeted tests passed** (tracking 4, media 6, providers 10, geometry 3, CLI 2). The assembled synthetic import/proxy/tracking run produced **75 valid samples out of 75** after the integration fixes. No full UI suite exists. Variable-frame-rate index selection is unit-tested, but a real VFR clip with frame-by-frame visual correspondence remains an acceptance check.

## Next implementation gates

1. Evaluate the user's real 5–10-second manipulation clip and document failure cases.
2. Complete authorized endpoint smoke tests and lock actual output contracts.
3. Add durable processing jobs and adapters; integrate mask-assisted tracking and separately validated relative-depth fusion.
4. Build the capture/review interface, two-actor workflow, independent camera pass and PNG/manifest export.

The full Phase 1 and even its full local-fallback profile are **not complete**. CoTracker, SpatialTrackerV2, OnePose++, World Labs and Tavus are not installed or dependencies of this slice.
