# PocketStage Phase 1 — SAM 2 Video, Video Depth Anything and local geometry

Revision: September 14, 2026. This is the controlling first-build specification. It supersedes earlier live-neural-first and enrolled-6-DoF proposals. The [feasibility runner](../IMPLEMENTATION.md) now includes a successful live SAM/depth smoke test (local media artifacts; not committed). The initial real-clip OpenCV-only trial failed to sustain phone tracking. Quality certification, integrated geometric solving and the complete application remain pending; requirements below are not completion claims.

## 1. The decision

Timeboxed demo update: at the user's request to prioritize an immediate demo, a mask-centroid relative-motion lane (local media artifacts; not committed) now runs before the full review UI and stable-surface solver. It includes moving/static object roles and raw depth differences. This approximate control path does not satisfy the calibrated/geometric or quality gates below, and does not replace the independent fallback.

**Record a 5–10-second RGB take → SAM 2 Video masks + Video Depth Anything → local geometric solving → reviewed virtual performance. Keep the lightweight OpenCV tracker as the independent fallback.**

This is the intended full Phase 1 pipeline, not a selection-only SAM integration or a CoTracker-first implementation. Both hosted models are in the planned build. Depth must produce a usable, tested relative signal before it is presented as working.

No 6-DoF requirement. No solvePnP, object enrollment, object measurements, intrinsic camera calibration, LiDAR, depth hardware or object scanning. “Geometric solving” here means table-constrained position and observable planar heading, with a separately qualified relative-depth cue. It does not mean reconstructing a physically accurate free-space object pose.

The Mac owns capture, processing orchestration, OpenCV solving, playback, persistence and export. Hosted inference runs after recording. A rented GPU is not required for the primary path.

### What the release does

- Capture up to two ordinary actor objects in one take under a fixed webcam.
- Select each object on a recorded frame, review the selection and run post-take processing.
- Transfer supported tabletop movement to two virtual actors; optionally use reliable planar heading.
- Show inferred relative depth beside the source evidence. Allow an explicitly reviewed, bounded artistic mapping of that cue to one virtual control.
- Record a separate object-driven camera pass while replaying accepted actor motion.
- Review, scrub, save/reopen and export three chosen shot-reference PNGs plus a trajectory/shot manifest.

For normal filmmaking, this is blocking and framing previsualization. For AI filmmaking, it provides references and structured motion data. It does not promise generator-specific motion conditioning, final generated footage or a calibrated physical camera move.

Start with textured, rigid, compact everyday props such as a patterned case, small package or toy. No markers, special bases or DancingBox rig. Transparent, reflective, deformable or rotationally symmetric objects are not guaranteed. Hand manipulation must be tested, not excluded from the demo.

### Honest completion labels

| Profile | Required result |
|---|---|
| Local fallback complete | Two actor tracks, separate camera pass, reviewed selection, planar playback, persistence and PNG/manifest export work without cloud access |
| Full Phase 1 complete | Local fallback plus verified SAM 2 temporal masks, aligned raw Video Depth Anything data, integrated local solving and a useful validated relative-depth cue |
| Experimental | CoTracker or later 3D candidates shown separately; not prerequisites for either profile |

If an endpoint or depth-quality gate fails, ship the last passing profile and name the missing capability. Do not call the full pipeline complete because requests merely returned successfully.

## 2. User flow and physical setup

1. Mount the webcam securely above or steeply overlooking the table. Select four ordered corners of a rectangular play area, specify its aspect ratio and choose virtual stage dimensions.
2. Record a 5–10-second actor take. Keep each object briefly unobstructed near the beginning. Raw video preview is sufficient; provisional local motion is optional.
3. On a clean saved frame, click actor A and actor B, add correction prompts if necessary and assign virtual assets. Manual reviewed regions remain available.
4. Process the take. Show baseline progress and separate mask/depth job states.
5. Review source video, masks/features, virtual stage and timeline together. Inspect gaps and optional depth mapping. Accept a candidate explicitly.
6. Replay the accepted actor performance from scene time zero while recording a separate camera-object take. The physical webcam stays fixed.
7. Process and accept the camera pass; replacing it must not change actor motion.
8. Save/reopen, scrub and export three selected reference images with their timing and camera settings.

Selection may start on a later clean frame, but earlier frames remain explicitly unavailable unless a separately tested backward-processing path supplies them. Never hide the missing prefix by shifting the timeline. Re-selection produces a new candidate from the original take; there is no in-take segment stitching or full trajectory editor.

Changing the physical camera or stage rectangle invalidates its capture mapping. A new mapping may reuse the same named stage only after an explicit compatibility check. Do not merge different origins, axis directions or scales automatically.

## 3. Build order: each checkpoint preserves the previous one

| Checkpoint | Build | Acceptance gate | Fallback |
|---|---|---|---|
| A — Evidence spike | Save a real manipulation fixture; test local tracking; smoke-test both sponsored endpoints | Usable object tracking; actual mask/depth payloads and billing coverage understood | Local fixture runner; report unsupported cloud contract |
| B — Durable local slice | Capture, immutable takes, canonical proxy, project records, one actor, baseline review | Capture survives processing failure; deterministic source mapping and reopen | A |
| C — Local directing loop | Two actors, camera pass, independent acceptance, PNG/manifest export | Complete useful local workflow and compatible composition | B; not the complete fallback profile |
| D — SAM 2 temporal masks | Per-actor adapter, mask review, identity checks, mask-assisted local tracking | Masks improve or preserve tested tracking without silent identity transfers | C |
| E — Video depth and fusion | Shared depth job, raw-array validation, relative-depth inspection/control | Aligned and useful relative-depth cue; independent quality flags | D with depth disabled |
| F — Certification | Manipulation trials, failures, timing, export and project round-trip | Explicit local or full completion profile with evidence | Last passing checkpoint |
| Optional after F | Separate local CoTracker benchmark | Measured benefit on the same takes | Certified pipeline unchanged |

Suggested engineering allocation: A 1–2 hours; B 2–3; C 3–4; D 2–3; E 2–3; F 1–2. Approximately 11–17 focused hours, subject to the first spike. This is a planning estimate, not a hackathon completion guarantee. If mask output needs a new deployment, re-estimate rather than hiding that work.

Timebox initial endpoint probing to about 30 minutes within A. If the documented contract cannot supply usable masks, stop adapter expansion and request sponsor clarification while continuing the local slice. Do not spend the event installing research models to conceal an unavailable API.

Keep coding iterations small; run relevant checks within approximately ten-minute interaction cycles. Never cut timestamp validation, uncertainty states or persistence to claim the larger profile.

## 4. Runtime and shared interfaces

Use React/TypeScript/Three.js for the UI and scene, Python/FastAPI for a loopback-only local service, OpenCV for capture and geometry, and FFmpeg/ffprobe for canonical video preparation and inspection. One process owns the physical camera. Heavy conversion and inference orchestration must not block its capture loop.

Proposed modules:

- `capture/`: camera ownership, bounded recording writer, timestamp index.
- `media/`: canonical proxy, source mapping, decoded output validation.
- `tracking/baseline`: features, optical flow, outlier rejection and planar control.
- `providers/sam2_video`, `providers/video_depth`: authenticated requests and strict artifact adapters.
- `fusion/`: mask-gated tracks, depth aggregation and quality decisions.
- `projects/`: immutable artifacts, manifests, candidate acceptance and compatibility.
- `scene/`: provider-independent playback, camera and reference export.
- `experiments/`: optional CoTracker; never imported on core startup.

There is one tracking-result interface. Models do not write directly to actor transforms or accepted performances. Placeholder shapes and a neutral stage always render without downloaded assets.

### Records to establish before model integration

| Record | Essential fields and invariants |
|---|---|
| StageFrame | Stable ID, origin, axes, aspect ratio, virtual units and revision; not implicitly metres |
| CaptureMapping | Stage ID, corner mapping, image dimensions/orientation, physical camera configuration and revision |
| CaptureTake | Immutable source reference/hash, actual dimensions, monotonic frame timestamps, duration and capture mapping |
| CanonicalProxy | Hash, codec, dimensions, exact frame count/rate, crop/resize transform and proxy-to-source timestamp/index map |
| Selection | Actor ID, proxy hash, prompt frame, prompts/manual region, asset and reference anchor |
| ProcessingJob | Input/config hashes, provider/model, external request IDs, status, attempt count, timings and local output paths |
| TrackCandidate | Take/actor IDs, adapter versions, per-sample controls, quality flags, source provenance and artifacts |
| Performance | Explicitly accepted actor candidate IDs and stage/time mapping; immutable revision |
| CameraTake | Independent camera candidate, fixed settings and intended performance revision |
| Composition | Compatible performance/camera references, scene clock and explicit offsets |
| ExportManifest | Composition revision, exact output times, camera/FOV/aspect, assets, control modes and file hashes |

Each sample stores time, planar position or null, heading or null, relative-depth cue or null, and independent validity/reason codes. Suggested states: VALID, DEGRADED, LOST, UNAVAILABLE. Geometric diagnostics are not calibrated confidence probabilities.

Store measured/estimated evidence separately from applied artistic controls. Fixed heading, look-at direction and depth-to-height mappings must remain distinguishable from tracked signals. Future trackers can add capabilities without changing the meaning of existing fields.

## 5. Capture and one canonical processing clip

Request 720p/30 fps initially, but persist actual capture timing and dimensions. Host receive timestamps are not claimed to be hardware exposure timestamps. Use a bounded writer queue; report dropped frames. If recording cannot keep up, fail that take visibly while preserving prior takes.

Create one immutable, constant-frame-rate proxy, initially 480p at 15 fps, from the saved source. Record every resampling decision. A 10-second proxy is roughly 150 frames, not assumed to equal the original capture count.

Both hosted services and proxy-based local solving use this exact clip. Point prompts refer to its pixel coordinates and frame indices. Never send independently trimmed, cropped or resampled clips to different providers.

After download, validate duration, frame count, dimensions, orientation and temporal correspondence before combining outputs. Record any supported output resize explicitly. Equal array lengths alone do not establish alignment: A includes a clip with recognizable timed visual changes to detect offsets/duplication. Reject unexplained truncation or shifting rather than “fixing” it by array indexing.

Keep original capture and proxy so future methods can reprocess the same performance without another physical take. Full source re-encoding or upsampling is not required merely to render playback at a higher display rate.

## 6. SAM 2 Video: primary temporal object masks

Target `fal-ai/sam2/video`. Its schema accepts video and frame-indexed point/box prompts; outputs list segmented video and an optional ZIP of bounding-box overlays. The documented prompts have no explicit object-ID field, and the ZIP is not documented as raw masks. [Official endpoint schema](https://fal.ai/models/fal-ai/sam2/video/api).

**First integration gate:** inspect actual sponsored results and determine whether a supported configuration yields usable per-frame masks. Probe `apply_mask` behavior; do not assume false means binary output. Validate foreground/background separation, black objects, compression artifacts and frame alignment. A color overlay or box overlay is not a numeric object mask contract.

If unavailable, request a raw-mask-compatible configuration/endpoint from fal and leave this adapter disabled. Any endpoint substitution must be recorded and agreed as a scope change; no silent SAM 3 or custom-deployment substitution.

Our implementation contract:

- Submit one job per actor initially, mapping each request to the app's stable actor ID. Two actors share the uploaded clip but not an assumed multi-object label encoding.
- Convert verified output into a local binary-mask sequence plus provenance; no undocumented color-based identity guessing.
- Review initial selection before accepting a full candidate. Additional prompts create a new selection revision.
- Evaluate mask overlap, abrupt area/appearance changes and feature ownership. If two actor masks merge or overlap ambiguously, mark the affected interval uncertain.
- Seed and refresh features inside eroded mask interiors; reject points that migrate outside supported object evidence.
- Never treat every mask pixel as a persistent surface correspondence. A moving mask centroid is not a stable physical anchor.
- Never assume a mask proves identity through hands, full occlusion or off-screen exits.

An API response succeeding does not satisfy this checkpoint; masks must work in the local solving tests.

## 7. Local geometric solving and the lightweight fallback

Implement the baseline before hosted integration: reviewed region → feature detection → pyramidal Lucas–Kanade flow → forward/backward checks → robust transform fitting. Use enough well-spread inliers and explicit residual/coverage gates. Initialize thresholds on fixture data; record their versions rather than presenting arbitrary constants as universal reliability.

Track a reference anchor through supported transforms. For tabletop mapping, use an explicit user-selected control anchor/plane assumption. Features on elevated object surfaces create parallax: a table homography does not turn a tall object's image centroid into accurate ground contact. Limit the supported demo to modest-height props/view angles that pass the position tests and label the result as a control trajectory.

Where a visible approximately planar surface provides sufficient support, estimate planar rotation in rectified coordinates. Do not equate image-plane rotation with arbitrary-object 3D yaw. Symmetric objects, poor feature spread, tipping or perspective changes can make heading unavailable while translation remains useful.

Heading policies are independent:

- Fixed heading.
- Tracked planar heading when valid.
- Explicit look-at target.

Velocity must not silently determine facing; backward motion must remain possible.

SAM masks constrain feature membership and help reject drift. They do not replace correspondence tracking or robust fitting. Use initial appearance/feature consistency as additional evidence against hand transfer; if evidence is insufficient, invalidate instead of following a smooth but wrong track.

Keep baseline-only and enhanced outputs as separate candidates. Refreshing features must preserve the reference frame and accumulated transform; it cannot silently reset the actor origin or recover lost identity.

During full occlusion, mark a gap. A display-only last-position ghost is allowed with an obvious LOST label; never export it as valid tracking. No smoothing across missing intervals. Reacquisition must be independently checked or require user re-selection and reprocessing.

## 8. Video Depth Anything and bounded fusion

Target `fal-ai/depth-anything-video`, initially VDA-Small with a fixed processing profile. Request `include_raw_depths: true`. The documented output includes an NPZ float32 depth tensor and metadata, separately from the visualization MP4. The schema does not promise metric metres. [Official endpoint schema](https://fal.ai/models/fal-ai/depth-anything-video/api).

Use one depth job per take, shared by both actors. Do not derive geometry from the colored or grayscale visualization video.

Our depth contract:

1. Load numeric arrays safely, without pickle; check finite values, shape, frame mapping and resource bounds.
2. Determine value direction and behavior empirically with known near/far movement and a stationary background. Do not assume whether larger means farther or whether scale stays stable.
3. Pool robust statistics over eroded, identity-valid object masks; inspect spatial spread and valid support. Exclude boundaries and suspected hand contamination.
4. Monitor several stationary background patches for drift. They are quality checks, not proof of absolute scale or a complete correction for monocular ambiguity.
5. Use a fixed per-take reference and normalization only after validation. Never independently min/max-normalize each frame and interpret those values as motion.
6. Store the raw statistic, derived relative cue, normalization parameters and quality flags separately.
7. Invalidate depth when mask identity, alignment or temporal behavior is suspect. Do not let a depth discontinuity repair a lost object track.

Core fusion keeps planar solving independent of depth. Depth adds a non-metric near/far cue; it does not overwrite supported table coordinates.

The user may enable a bounded artistic mapping of relative depth to one chosen virtual control, such as camera height offset. Show the range, sign and baseline, preview before acceptance, and label it “relative-depth control,” not physical height. Default mapping is off. A completed full profile must demonstrate at least one useful reviewed mapping on a declared fixture, not just display a heatmap.

Lifting or tipping may invalidate the planar assumptions. Do not simultaneously claim correct table X/Y and true lift from that interval. A projected artistic path can be shown as degraded, but reliable metric XYZ, roll/pitch and 6-DoF are out of scope.

### Failure ladder

| Available evidence | Behavior |
|---|---|
| Masks, geometry and depth pass | Planar track plus separately enabled relative-depth control |
| Depth fails | SAM-assisted planar track; depth unavailable |
| Masks fail | Reviewed manual region and baseline tracker; depth not attached to an unverified identity |
| Geometry fails | Gap and review/reprocess/re-record; no invented pose |
| Cloud unavailable | Local fallback and previously accepted playback/export remain usable |

Do not silently switch methods midway through an accepted track. Recompute/review a candidate or label its exact method transitions and gaps.

## 9. Camera, replay and output

Actor and camera passes use one named stage and scene clock. Record camera samples against the actor playback clock, with explicit lead-in/offset metadata. Processing can finish later without changing capture timing.

The initial virtual camera has configurable fixed height, a fixed lens (default 50-degree vertical FOV, 16:9), and look-at or supported planar-heading mode. Optional depth mapping uses the same review/quality rules; no recovered roll/pitch is implied.

Composition rejects incompatible stage IDs/mappings, absent actor revisions and unaccounted time offsets. A different capture mapping may be accepted only through an explicit tested mapping to the same stage, not merely because both records have version numbers.

Allow scrubbing, comparison of baseline/enhanced candidates, explicit acceptance and independent camera replacement. Playback interpolates only within valid intervals. It never calls a hosted model.

Required export: three user-chosen PNG frames plus JSON trajectory and shot manifest. Reproduce exact saved time, camera and aspect ratio; mark unavailable intervals and all artistic control mappings. Video animatic encoding and generator adapters are later enhancements, not disguised PNG deliverables.

## 10. Jobs, persistence, privacy and cost

Job lifecycle: CREATED → PREPARING → QUEUED → RUNNING → VALIDATING → READY, or FAILED/CANCELED. READY means reviewable, not accepted.

Persist external request IDs immediately. On restart, reconcile an existing job before resubmitting. Retry bounded transient failures only; do not automatically repeat invalid payloads or unauthorized requests. Cancellation stops local consumption and requests provider cancellation where available, but cannot promise an already-running remote job will not be billed.

Cache by proxy hash, selection/configuration hash and adapter/model identity. A two-actor take ordinarily needs two segmentation jobs and one depth job, not per-frame calls. Queue concurrency starts conservatively and increases only after account limits are verified. Download successful artifacts into the project; expiring URLs must not be authoritative storage.

Use atomic manifest writes. Save outputs under new IDs; never replace original capture, baseline results or accepted takes in place. Failed/canceled processing leaves the project usable.

Keep API keys in the local backend, out of frontend bundles, manifests and logs. Obtain explicit upload consent in the app, describe the footage being sent, avoid bystanders and record provider retention/deletion limitations. Validate external downloads, MIME/content, archive paths, sizes and NPZ allocation limits.

The user reports unlimited hackathon fal.ai, World Labs and Tavus access. Exact endpoint eligibility, expiry, rate limits, credits and billing remain unverified. A must confirm the two required endpoints before paid inference. World Labs and Tavus are not dependencies.

Default additional GPU rental: **$0**. Preserve the user's **under-$40** limit with a $30 operational ceiling and $10 reserve. Count paid API requests, compute, storage, taxes and egress together. Do not launch a paid job without known applicable coverage or a bounded cost estimate that fits the remaining allowance.

Optional GPU experiments require a current price check, explicit session cap and automatic shutdown. No assumption that sponsor access includes custom deployment. Budget policy is a planned guardrail, not a claim that resources have already been provisioned or capped.

## 11. Acceptance tests and realistic latency

These are proposed release gates, not measured results.

| Area | Required check |
|---|---|
| Endpoint contract | Actual selected-object masks and raw depth parse correctly; documented coverage and billing status recorded |
| Alignment | Timed-event fixture detects frame offsets, truncation, resize/crop and orientation mismatches; invalid artifacts rejected |
| Manipulation | Three distinct everyday props, five 10-second trials each; at least four successful trials per prop |
| Useful coverage | Successful trials have at least 95% valid position coverage during annotated observable movement, without re-selection |
| Identity | Two actors, crossings, partial hand occlusion and similar colors; no undetected actor/hand transfer on the test set |
| Loss | Full occlusion/off-screen exit invalidated within two proxy frames; no fabricated continuity |
| Position | On declared tabletop fixture, static jitter ≤1% stage width and median marked-path error ≤2% width |
| Heading | Directional prop turns, symmetry and backward movement tested; heading may be unavailable without invalidating position |
| Depth usefulness | Five controlled near/far trials: at least four show the correct signed trend; no metric-distance claim |
| Depth negative controls | Stationary object with moving hand/background does not create accepted false movement; inspect scale drift and mask contamination |
| Depth stability | On static fixture, false control excursion ≤5% of the locked test mapping range; never tune the range separately to hide each failure |
| Fusion failures | SAM-only, depth-only, no-cloud, corrupt artifact and unsupported lift paths produce the documented fallback/invalid states |
| Durability | Crash/cancel/restart and expired URL preserve original/accepted data; no duplicate blind submissions |
| Composition | Camera replacement preserves actor hash; shifted stage/clock rejected; save/reopen restores exact composition |
| Export | Three PNGs match saved time/FOV/aspect; manifest records source revisions, gaps and artistic controls |

Report deliberate unobservable intervals separately; do not inflate coverage by excluding ordinary difficult hand manipulation. Annotate selected source frames manually for initial ground truth. Report results per prop/view, not as universal accuracy.

Post-record processing target: roughly 30–90 seconds for a 5–10-second take, **unbenchmarked**. Measure preparation/upload, queue, inference, download, validation and solving separately. At 120 seconds show a slow-processing state with local fallback available; use a configurable five-minute local wait limit and retain remote request IDs for later reconciliation.

Benchmark at least five representative complete takes, distinguishing cold/warm conditions. Report all timings, median and worst observed; do not label five samples as a reliable p95. If hosted performance is slower, present the measured delay and keep asynchronous review rather than claiming real-time operation.

During development, run only directly relevant tests after narrow changes. Shared schemas, replay or build changes warrant broader checks. No model installation, GPU rental, implementation test or deployment is authorized merely by this planning document.

## 12. Deferred experiments and handoff

**CoTracker:** benchmark locally, separately, on the same saved fixtures after the core pipeline works. Compare usable coverage, identity failures, memory and total processing time against mask-assisted OpenCV. Promotion is earned; it is not a required replacement or blocker.

**SpatialTrackerV2 / OnePose++:** optional later GPU experiments. No install, custom deployment or 6-DoF milestone is required in Phase 1. Revisit only after sponsor deployment coverage and event time are known.

**World Labs / Tavus:** later optional environment/presentation layers. They never own capture, tracks or playback. Neutral stage and local playback remain available.

Handoff must include runnable setup instructions, environment-variable names without secrets, endpoint contract fixtures, test results, saved demo takes, schema/adapter versions, known unsupported interactions and the exact completion profile achieved.

The first coding task is checkpoint A: one real saved manipulation clip, baseline tracking and the two sponsored payload probes. Build around actual artifacts before expanding the UI.

Related documents: [overarching roadmap](PocketStage_Everyday_Object_Implementation_Plan.md), [historical adversarial review](PocketStage_Phase_1_Adversarial_Review.md), [broader RGB/3D research](PocketStage_RGB_3D_Tracking_Feasibility.md).
