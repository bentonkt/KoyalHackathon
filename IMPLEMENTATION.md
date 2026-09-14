# PocketStage — first implementation slice

This is the **checkpoint-A runner with a hosted SAM/depth smoke-test path**, not the completed Phase 1 app. The intended full pipeline remains **SAM 2 Video masks + Video Depth Anything + local geometric solving**, with independent OpenCV fallback. No 6-DoF, scanning or GPU rental.

**Fast demo path is now working:** phone motion relative to a stationary bottle (local media artifacts; not committed). It uses explicitly approximate SAM-centroid controls, shared raw depth and a rendered preview, without waiting for the full UI or stable-surface solver.

## Fast motion demo commands

After the first object's SAM/depth run completes, add another object without uploading again or rerunning depth:

```sh
.venv/bin/python -m pocketstage cloud-object PARENT_RUN_DIRECTORY --id bottle --point X Y FRAME --consent-upload --sponsor-covered
.venv/bin/python -m pocketstage cloud-poll NEW_RUN_DIRECTORY
```

Visually review each SAM output to confirm the binary-mask profile and selected object. Then export:

```sh
.venv/bin/python -m pocketstage motion-demo --object phone PHONE_RUN_DIRECTORY --object bottle BOTTLE_RUN_DIRECTORY --reference bottle --static bottle --out projects/demo-export --reviewed-masks
```

Output includes JSON with absolute and relative tracks, a flat CSV and an H.264 preview. Repeat `--object` for other objects and `--static` for additional stationary roles. All runs must reference the same canonical clip; missing reference/object observations remain gaps. Select a new export directory for each result. Coordinates are normalized image offsets; centroid shifts and raw depth differences are not physical pose measurements.

## Implemented

- Immutable local video import, original-file hashes, canonical 15-fps proxy and explicit source-frame/time mapping.
- Reviewed rectangular selection in proxy coordinates; OpenCV feature tracking, forward/backward checks and robust accumulated transforms.
- Optional binary-mask gating at the tracking interface; no assumption that a hosted segmented video is a mask.
- Fail-closed loss, missing prefixes, no automatic reacquisition or fabricated depth/heading.
- Explicit tabletop control mapping, separate from image-space evidence; virtual units, not measured 3D position.
- New, unaccepted trajectory candidates saved without overwriting previous results.
- fal upload/queue/result retrieval, single-attempt submission, persisted request IDs, conservative output inspection, bounded raw-depth NPZ and mask validators.
- A deterministic synthetic clip and runnable local tests.

## Run on this Mac

After installing the isolated environment below, run from the repository root:

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

**Live smoke test passed on the supplied clip:** both endpoints completed; reviewed SAM masks and raw numeric depth were extracted. Results and comparison video (local media artifacts; not committed). This is model integration evidence, not completion of the full tracking application.

The backend reads `FAL_KEY` from the environment or this directory's ignored `.env`. A single bare `id:secret` credential in that file is also supported without rewriting or displaying it. The user has now confirmed sponsor coverage and consent to upload the supplied clip. Actual model-output findings are recorded separately; installed client code alone is not a passed endpoint contract.

`providers.py` defines request/array contracts; `fal_transport.py` handles network transport; `cloud.py` persists bounded runs. One shared clip upload feeds one SAM job and one depth job. A saved run is never automatically submitted again, including after an ambiguous submission. `cloud-poll` retrieves existing requests without creating replacements. Review-ready does not mean verified masks, metric depth or full pipeline completion.

Install hosted dependencies with `.venv/bin/python -m pip install -e '.[cloud]'`. Then:

```sh
# Dry-run: no upload or inference.
.venv/bin/python -m pocketstage cloud-start --project projects/my-shot --take TAKE_UUID --point X Y FRAME

# Only after confirming coverage and upload permission:
.venv/bin/python -m pocketstage cloud-start --project projects/my-shot --take TAKE_UUID --point X Y FRAME --execute --consent-upload --sponsor-covered

# Use the run_directory printed by cloud-start. Each invocation checks once.
.venv/bin/python -m pocketstage cloud-poll RUN_DIRECTORY
```

X/Y are canonical-proxy pixels; FRAME is its zero-based frame index. The first smoke profile probes `apply_mask=false` without assuming that it returns binary masks. Depth requests raw NPZ output. Both jobs retain actual artifacts and inspection reports. A failed inspection does not launch a different endpoint or silently substitute an overlay for masks. Submission uses a non-retrying POST; upload/status/result may use SDK retries. Manual reconciliation is required if a submission returned no reliable ID.

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

Verified on September 14, 2026 before publishing: **all 61 Python tests passed** in the merged checkout. The unchanged web app was not rebuilt or retested in this backend publishing pass. The assembled synthetic import/proxy/tracking run previously produced **75 valid samples out of 75**. Variable-frame-rate index selection is unit-tested, but a real VFR clip with frame-by-frame visual correspondence remains an acceptance check.

## Next implementation gates

1. Evaluate the user's real 5–10-second manipulation clip and document failure cases.
2. Expand the successful endpoint smoke test into repeatable quality/alignment checks and lock the observed output profile.
3. Add durable processing jobs and adapters; integrate mask-assisted tracking and separately validated relative-depth fusion.
4. Build the capture/review interface, two-actor workflow, independent camera pass and PNG/manifest export.

The full Phase 1 and even its full local-fallback profile are **not complete**. CoTracker, SpatialTrackerV2, OnePose++, World Labs and Tavus are not installed or dependencies of this slice.
