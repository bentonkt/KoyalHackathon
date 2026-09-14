# PocketStage Phase 1 — markerless tabletop directing

Revision: September 14, 2026. Sponsor-first selection; local live tracking; optional generated sets. No implementation or inference benchmarks have been executed.

## 1. Outcome and scope

Phase 1 delivers one usable short-shot workflow on the existing M4 Mac with 16 GB RAM:

**Click and confirm two everyday objects → move them to direct virtual actors → record a separate camera-object pass → replay and save the shot.**

This specification consolidates the earlier roadmap's tracking spike, usable stage, camera pass, and bounded click-selection assistance into Phase 1 checkpoints A–F, with optional World Labs set enhancement G. Broader tracking robustness and richer filmmaking exports remain subsequent phases.

The first release supports one fixed-camera tabletop scene, two actor bindings, one camera binding, and 5–10-second performances. Compact, textured everyday objects are the initial certified profile; no printed markers or special bases. Position is required. Rotation is enabled only when observable; fixed/look-at heading remains available.

No DancingBox, human-motion generation, SMPL, Pi3, reconstruction of the physical tabletop, inferred actions, scripts, contact simulation, or video-generation service. An optional generated 3D environment is a virtual set, not recovered physical geometry. Two simple colored virtual characters are sufficient. Optional walk/idle animation is procedural or asset-based and labeled as such.

**Budget:** target $0 incremental API/GPU spending using the user's stated unlimited hackathon access to fal.ai, World Labs, and Tavus. Verify endpoint eligibility, expiry, rate limits, and ancillary charges before jobs run; sponsor access is not an assumed billing cap. Do not rent a GPU initially. Operational spending ceiling is $30, leaving $10 untouched below the requested $40 maximum. Include setup, idle time, storage, taxes, and fees. This plan does not provision or pay for anything.

All timing, quality, and cost estimates below are proposed targets, not executed benchmarks.

## 2. Completion levels and demo

Phase 1 has a certified core fallback and a full click-first target:

| Profile | Required behavior | What it may claim |
|---|---|---|
| Core fallback | Reviewed outline/box selection, two local object tracks, camera pass, replay/save | Markerless region-selected tabletop directing |
| Full Phase 1 | Core plus working click-prompted mask selection and correction | Click-to-select everyday-object directing |
| Optional enhancement | World Labs virtual set; better tracked yaw or fitted assets if tested | Only the specific tested capability; core remains usable without it |

An unavailable segmenter must not silently convert a manual-selection demo into a claimed click-first success. Camera-pass failure leaves a usable actor-blocking checkpoint but does not satisfy the full Phase 1 gate.

Demo sequence:

1. Place a textured case and small box on the table; keep objects still during selection.
2. Click each, confirm its mask/anchor, and assign Actor A or B.
3. Record A approaching B, both pausing, and B moving away. Use fixed facing where rotation is ambiguous.
4. Replay the actors while moving a stapler or flat object as the camera controller.
5. Watch the virtual shot; re-record only the camera pass.
6. Save/reopen, then cover an object in a new take and demonstrate an honest tracking-loss state.

For normal filmmaking, this is a previsualization rehearsal. For AI filmmaking, it provides shot references and a saved scene trajectory; exact conditioning of a specific generator is not part of Phase 1.

## 3. Sponsor-assisted setup, local live runtime

| Component | Initial implementation | Fallback / boundary |
|---|---|---|
| UI/rendering | TypeScript, React, Three.js; source, stage, timeline | Simple floor and colored characters always available |
| Capture/orchestration | Local Python, FastAPI/WebSocket, OpenCV camera access | Imported short video for fixtures |
| Click selection | fal `fal-ai/sam-3/image`, subject to endpoint smoke test | Hosted `fal-ai/sam2/image` adapter, then reviewed manual region |
| Live point tracking | OpenCV good features + pyramidal Lucas–Kanade on Mac | Re-click/manual region; no network dependency |
| Planar pose | Robust fit, stable anchor, calibrated stage mapping | Position-only when yaw is unsupported |
| Virtual environment | Simple local stage | Optional World Labs environment through Spark/Three.js |
| Storage/export | Versioned JSON, immutable evidence and tracks, reopenable local package | No database; viewport video only if time remains |
| Tavus | Deferred | No conversational avatar or perception service required |
| Rented GPU / learned tracker | Deferred | Only a bounded, justified experiment under §8 |

fal documents point-prompted image segmentation for both endpoints. They have different schemas, so implement separate decoders behind one selector contract. SAM3 is the first candidate, not a claim that it outperforms SAM2 on our objects. [SAM3 API](https://fal.ai/models/fal-ai/sam-3/image/api), [SAM2 API](https://fal.ai/models/fal-ai/sam2/image/api).

The cloud only assists deliberate selection/reselection and optional set creation. It is never called for every camera frame. Neither a “real-time” API label nor an annotated video demonstrates suitable persistent numeric tracks for this application. There is no verified hosted CoTracker dependency in this plan.

Local SAM2 is a later offline-click option, not a prerequisite or installation task for the first build. Its MPS support is preliminary. CoTracker's MPS demo is not a latency benchmark, and its noncommercial license requires separate review. [SAM2 MPS implementation](https://github.com/facebookresearch/sam2/blob/main/demo/backend/server/inference/predictor.py), [CoTracker demo](https://github.com/facebookresearch/co-tracker/blob/main/online_demo.py), [license](https://github.com/facebookresearch/co-tracker#license).

Tavus provides conversational video and visual-awareness capabilities. That does not establish accurate tabletop coordinates, object identity, or pose timing. A voice-director interface may be considered later, but is not Phase 1 work merely because access is available. [Tavus CVI documentation](https://docs.tavus.io/sections/conversational-video-interface/faq).

### Stable boundaries that prevent rework

Keep ObjectSelector, PointTracker, PoseEstimator, Recorder, SceneRenderer, and EnvironmentProvider separate. The renderer consumes local versioned trajectories, never provider response objects. Replacing a selector/tracker changes its producer metadata, not actor IDs or old takes.

| Record | Required additions from the start |
|---|---|
| SelectionProposal | Source frame/hash/dimensions, calibration/cast versions, pixel transform, prompts, provider/endpoint/configuration, request ID, normalized candidate masks |
| ConfirmedBinding | Application-owned actor ID, reviewed mask and anchor, heading policy; provider IDs are request-local only |
| ProviderJob | Purpose, input hash, request ID when known, state/deadline, sponsor eligibility, result references; no secrets |
| EnvironmentVersion | Built-in or generated kind, provider/world ID, asset format/local checksum, reviewed stage-to-environment transform and play area |
| SceneComposition | Immutable performance/camera references plus selected environment version; never embed tracking in environment coordinates |

A built-in environment record ships with A; the remote adapter arrives only in G. Do not build a generic plugin framework. These small records are enough to preserve portability.

Suggested future repository paths: `app/src/stage/`, `capture/`, `review/`; `backend/capture.py`, `selection/`, `tracking/`, `geometry/`, `recording/`, `providers/`, `schemas/`; and `tests/fixtures/`. GPU lifecycle scripts are added only if rental is approved and needed. None of these application files exist yet.

## 4. Capture, selection, and coordinate contract

The Python service owns the camera and timestamps decoded frames on one monotonic clock. Request 720p/30 fps as an initial configuration, but record actual dimensions and cadence. Process tracking at a lower resolution where useful, preserving the exact pixel transform. Expose a preview and frame IDs to the browser; do not independently open a second browser camera stream with different timing.

Bind every selection to an immutable frame ID, image hash, cast version, and calibration version. Freeze the displayed selection image while the request runs. A late mask cannot initialize points against a newer frame: either require the objects to remain still and validate that assumption or reselect on a current frame. Resizing, cropping, rotation, and mirrored display all need explicit coordinate mappings.

### Hosted selection adapter

1. Capture one immutable frame and require the objects to stay still through confirmation. Upload only after explicit cloud-selection action and disclosure.
2. Submit one object proposal at a time. Convert display clicks to source-pixel coordinates before provider serialization.
3. For SAM3 use `point_prompts`; its schema defaults text `prompt` to “wheel.” Verify point-only behavior explicitly; never silently inherit that text. If a supplied object label is needed, expose it. SAM2 instead uses `prompts`. [SAM3 schema](https://fal.ai/models/fal-ai/sam-3/image/api), [SAM2 schema](https://fal.ai/models/fal-ai/sam2/image/api).
4. Test PNG output with `apply_mask: false`. SAM3 returns `masks`; SAM2 documents an `image` result. Validate actual pixel/alpha encoding, foreground polarity, dimensions, and alignment against a fixture. An attractive overlay is not a usable binary mask. If the decoder cannot prove the mapping, reject it.
5. Normalize a selected candidate to an application-owned source-size binary mask. Never equate model confidence with tracking confidence. Multiple candidates do not automatically create multiple actors.
6. Show the candidate for confirmation and corrective positive/negative clicks. Validate current-frame consistency before initializing local points; moved objects require a fresh proposal.
7. Cache the confirmed mask and provenance locally. Reopening a project must not require the provider URL to remain alive.

**Immediate fallback is manual selection**, not a chain of automatic model calls. Offer SAM2 explicitly if SAM3 fails its gate; never silently retry against a billable endpoint. Local SAM2 remains optional later.

### Calibration and anchor

Calibration requires four correctly ordered, non-self-intersecting corners of a rectangle plus its aspect ratio. Reject degenerate quadrilaterals. Map to a chosen virtual width/depth; this is a directing coordinate system, not surveyed measurements. Define stage coordinates as right-handed, Y-up, with a documented image-to-ground mapping.

Use a near-overhead fixed camera and compact objects. Table homography does not remove height parallax; tall objects and non-planar turns receive lower-confidence support. Camera repositioning invalidates calibration; provide an explicit reset and check static table/background features for large disturbances where feasible. [OpenCV homography documentation](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html).

Ask for a reviewed actor anchor and optionally a forward direction. Track the anchor under the fitted transform instead of averaging the remaining visible points. Derive yaw in stage coordinates, not directly from image angle. Do not convert apparent scale changes into elevation.

## 5. Live tracking and failure behavior

Initialize approximately 20–40 spatially distributed good features inside a slightly eroded reviewed mask. This is a tuning range, not a sufficiency guarantee. A bounding box fallback needs user review because it may include background.

For each processed frame:

1. Track features with Lucas–Kanade.
2. Reject failed or inconsistent tracks using forward–backward checks.
3. Fit a robust transform from correspondences in the intended planar coordinate convention.
4. Check inlier count/ratio, residual, spatial spread, and implausible motion/scale.
5. Update position and yaw validity independently.
6. Apply causal smoothing only to valid observations.
7. Emit frame/time, pose, quality metrics, status, and held/missing flags.

OpenCV provides the optical-flow and robust fitting primitives; thresholds and object-identity checks are application work. RANSAC cannot guarantee identity when a hand becomes the dominant tracked group. [Optical-flow API](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html), [transform API](https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html).

Use three states:

- TRACKING: valid supported position; yaw may independently be unavailable.
- DEGRADED: limited evidence; visibly reduce trust and avoid unstable rotation.
- LOST: no supported new pose; freeze/ghost the actor with a warning, preserving a missing interval.

A display hold is not a recorded measurement. Never follow the hand confidently, bridge a long gap silently, or auto-reassign Actor A to Actor B. Re-clicking creates a new reviewed tracking segment. Retain the last segment and its gap.

Bound the frame queue to prevent latency accumulation. Rendering may interpolate between valid estimates, but record processed and skipped frame IDs. When the queue overflows, drop stale work explicitly rather than showing an increasingly delayed “live” scene.

On initial selection failure, offer additional clicks, an outline/box, or another object. Do not repeatedly invoke a remote model without a deadline and retry limit.

## 6. Recording, camera pass, and persistence

Record the original decoded frame sequence or an encoded equivalent with an authoritative frame-ID/timestamp index. For the first bounded 10-second implementation, timestamped JPEG frames are an acceptable simple source format; add video encoding later without changing timing. Avoid labeling a fixed-frame-rate preview as exact capture timing unless it has been resampled deliberately.

Store raw tracks, quality/loss intervals, and smoothing configuration separately. Write new takes to a temporary task-owned directory, finalize its manifest atomically, and select takes through explicit composition metadata. A failed write must preserve the prior selected composition. Partial recordings can be recovered as incomplete; no silent overwrite.

A camera take records against the actor performance's clock after a countdown. Store the alignment offset. Playback uses scene time, not the moment each asynchronous message arrived. Short camera takes leave explicit missing coverage; never silently stretch time to fill the actor take.

Camera defaults: fixed height, fixed field of view, zero roll, position tracking plus explicit look-at target. Tracked-yaw mode is optional until stable. Heading and velocity remain separate for both camera and actors.

A saved project contains calibration, cast bindings, original evidence, raw/filtered tracks, performance take, camera take, selected composition, environment selection, and schema/producer versions. Reject unsupported future schemas safely. Changing calibration, masks, or assets creates new versions.

## 7. Minimal service surface

| Operation | Contract |
|---|---|
| Start/stop preview | Camera identity, dimensions, monotonic epoch, permission/error status |
| Create calibration | Exact source/configuration and reviewed corner/aspect data |
| Propose selection | Frozen frame/hash, prompt points/box, producer and request ID |
| Confirm cast binding | Reviewed mask, anchor, role, heading policy; reject stale frame/version |
| Start/stop take | Cast/calibration versions, take kind, explicit lifecycle and timestamps |
| Pose stream | Actor, segment, frame/time, position/yaw validity, quality and mode |
| Reselect actor | New bound segment; preserve loss interval and actor identity |
| Select composition | Exact performance/camera take versions |
| Save/load/export | Versioned manifest and integrity checks |
| Provider job status/cancel | Bounded selection/setup jobs; ignore superseded results |
| Generate/review/select environment | Optional G only; new version committed after validation |
| Remote benchmark | Explicit bounded fixture job; never automatic background upload |

Bind the local service to loopback, restrict allowed UI origins, validate message sizes, and reject arbitrary filesystem paths. Keep credentials outside frontend code and project exports.

## 8. Sponsor access, remote jobs, and spending controls

### Default: no rental

Timebox the initial fal integration probe to 30 minutes: confirm sponsored endpoint access, submit a representative frozen-frame click, inspect the returned mask, and try one correction. If blocked, continue with the manual-region local spike; do not spend the hackathon debugging model installation.

Before any model job, record covered endpoint/model, grant expiry, relevant rate/concurrency limits, and whether storage/egress are covered. Use server-side secrets only, outside exports and logs. Missing/expired access or billing-required responses disable that provider; they do not authorize paid fallback. Normal recording and replay continue offline.

Use one in-flight selection job, bounded image size, and an initial 15-second interactive deadline. Show progress immediately and allow manual selection without waiting. Persist a returned request ID and poll that job with bounded backoff. Permit at most one deliberate retry after a confirmed failure; an ambiguous submit must not trigger blind resubmission. Cancellation is best effort: a late result cannot alter a newer selection, and a UI timeout does not prove the provider stopped work. Handle rate limits without a retry storm.

Provider-created URLs may be public or temporary. Avoid sensitive tabletop content, minimize uploads, document actual retention/deletion controls, and remove task-owned uploads where supported. Do not promise deletion from provider systems without verification. Restrict remote downloads to expected HTTPS assets, bound sizes/timeouts, and block local/private-network targets.

### When renting could be justified

Only after hosted selection has been evaluated and the local core is usable, consider one GPU for a specific unsupported experiment or a bounded offline tracker comparison. Manual selection remains the operational fallback; rental is not required to complete the core. Confirm the proposed rental scope before provisioning.

Do not move live tracking to the network. Remote tracking experiments use reviewed fixture clips only. A GPU cannot fix unobservable yaw, full occlusion, or incorrect calibration.

Suggested rental: one on-demand Runpod RTX 4090, 24 GB, subject to availability and an actual quote at or below $1/hour for compute. The public page currently lists $0.74/hour. Eight hours at that rate is $5.92; ten is $7.40. This is listed compute pricing, not a booked quote or proof of workload memory requirements. [Runpod pricing, checked September 14, 2026](https://www.runpod.io/pricing).

### Budget envelope

| Item | Planning allowance |
|---|---:|
| Compute, including startup, downloads, debugging, idle and retries | $12 |
| Temporary disks and cleanup lag | $3 |
| Taxes, payment fees and price uncertainty | $5 |
| Incident/reconciliation buffer; not routine spending | $10 |
| Operational ceiling | **$30** |
| Untouched margin below requested maximum | **$10** |

The expected sponsored/local path incurs no GPU rental charge. A contingency session may land near $10–15 total, but taxes and provider checkout terms are not verified. Any uncovered API costs share this same budget; they are not a separate allowance. Do not buy assets, domains, subscriptions, savings plans, or unrelated services from this budget.

Runpod bills stopped volume storage, and stopping is not equivalent to terminating a Pod. Current documentation lists container/running-volume storage at $0.10/GB/month and stopped-volume storage at $0.20/GB/month. Its default $80/hour account limit is not a $40 project cap. [Pod billing documentation](https://docs.runpod.io/pods/pricing).

Before provisioning, the implementation must:

1. Record the final quote, tax/fee treatment, storage allocation, balance, and project budget baseline.
2. Use one instance and no autoscaling. Cap cumulative compute at 12 hours at the accepted rate; initial session limit two hours.
3. Disable automatic recharge for a dedicated project billing context where possible. Do not alter shared billing settings or rely on another project's balance as the budget control.
4. Use a small initial prepaid amount where available, keeping cumulative payments including fees under $30. Minimum funding and unused-credit treatment must be checked before paying.
5. Arm a bounded-session shutdown mechanism before useful work begins. A local reminder alone is insufficient because the Mac can sleep. Validate an independent watchdog/provider control path; do not assume a provider-native lifetime cap exists.
6. Maintain a conservative local cost estimate alongside provider billing, including idle/storage. At $15 warn; at $20 stop new paid work and clean up. Reserve remaining allowance for billing lag and safe termination.
7. Refuse renewal or additional funding when the next session plus known liabilities could exceed $30. If account isolation or reliable stopping cannot be established, use the local fallback.
8. Copy results locally and validate the manifest before terminating the specific task-owned Pod. Then confirm no task-owned persistent volumes/endpoints remain billed. Never delete unrelated account resources.

Termination can destroy remote files; the rented worker must never hold the only copy of project data. [Pod lifecycle documentation](https://docs.runpod.io/pods/manage-pods).

These are required controls to implement and verify, not a claim that a hard dollar cap has already been configured. No resource is being rented in this planning turn.

### Rented-worker isolation

Expose no unauthenticated inference server. Use an authenticated encrypted connection, bounded uploads and deadlines. The worker follows the same request/provenance contract as hosted selection. Pin model/code versions, retain license notices, and display when an image leaves the Mac. Benchmarking CoTracker does not clear its licensing for a commercial release.

## 9. Implementation checkpoints

Each task is small enough to run as a separate iteration; estimates describe implementation time, not the duration of a single assistant turn.

| Checkpoint | Work | Gate and fallback |
|---|---|---|
| A — Access + one-object spike | 30-minute fal probe, then local capture, reviewed selection, features, transform and quality overlay | Mask semantics verified or explicit manual mode; position/pause/loss/re-click must work before expansion |
| B — Two-actor stage | Calibration, stable bindings, Three.js characters, independent heading, built-in environment record | Correct shared coordinates and no silent swaps; fallback A |
| C — Durable takes | Timestamped evidence, raw tracks, save/reload and explicit composition | Reopened take preserves timing/gaps; fallback B with session-only label |
| D — Camera pass | Countdown, actor playback, separate camera take, replace/scrub | Camera replacement leaves actors unchanged; fallback C fixed camera |
| E — Click-first hardening | Promote passing fal adapter, correction UI, stale-response protection, sponsored-access and outage handling; SAM2 only if needed | Correct mask-to-frame binding and measured setup delay; fallback manual selection |
| F — Core certification | Mixed objects, failure injection, 60-second performance run, package handoff, cost/resource check | Full click-first profile or accurately labeled last passing checkpoint |
| G — Optional generated set | World Labs job, bounded asset import, alignment/review, environment selection and offline reload | Same saved shot works in generated and built-in sets; any failure returns to F |

Suggested effort: A 1–2 hours; B 1–2; C 1–2; D 1–2; E 1–2; F 1–2. Plan roughly 6–12 focused hours for the reliable core, not a cold-start four-hour guarantee. G adds approximately 2–4 hours if its formats work as documented; cut it after a one-hour import/performance spike fails. These are implementation estimates, not measured results or promises of parallel work.

For a four-hour event, use the early fal probe to capture a working click path if available, target A–D, and freeze at the last passing gate. Do not sacrifice identity, loss states, timestamps, or persistence to add a generated set. All checkpoints reuse existing records; feature flags select certified adapters, never rewrite saved takes.

### G — World Labs set enhancement

World Labs documents asynchronous world generation and output assets including SPZ splats, a GLB collider mesh, and a panorama. Its examples recommend Spark, a Three.js-compatible splat renderer. These are useful set assets, not guaranteed rigged characters or an editable semantic scene. [World Labs API](https://docs.worldlabs.ai/api), [renderer examples](https://docs.worldlabs.ai/api/examples).

Implementation design:

1. Generate one text-described environment outside recording. Avoid sending the tabletop image: the goal is a virtual set, not reconstruction. Pin the tested model/configuration and record the operation ID.
2. Use one job at a time, bounded polling, and a ten-minute foreground wait limit. This is an application patience budget, not a generation-latency claim. The user may continue locally; timeout must not auto-submit another world.
3. Start with the documented 100k splat asset; set a download/memory budget during the import spike. A collider GLB is not assumed to be a textured visual replacement. A panorama, if offered as fallback, is explicitly a backdrop without translational parallax.
4. Review orientation, translation, uniform scale, floor height, and usable play area. Transform the environment around the existing stage coordinates, not stored actor/camera paths.
5. Test characters against splat depth/occlusion and camera movement. No automatic collision, navigation, grounding, or realistic contact claim. Use the simple stage if artifacts obscure the demonstration.
6. Commit the environment version only after asset validation and preview confirmation. Superseded jobs cannot replace the selected set. Cache permitted assets locally with hashes; save/load must work without generation access.
7. Provide a one-click built-in-stage switch. Renderer incompatibility, missing assets, poor performance, or provider failure must leave the composition and original takes intact.

Free generation does not remove browser memory limits or integration work. The generated-set profile must pass the same live latency gate and its own rendering test before being demonstrated as live.

## 10. Acceptance tests and performance gates

Tests are specified here but remain unexecuted. Use synthetic transforms for geometry, recorded real-object fixtures for tracking, and a small UI smoke test for the complete workflow. Exercise provider failures with mocked responses. Live sponsor smoke tests require verified access; rental-specific T14 controls apply only if rental is pursued, and W01–W04 apply only to G. The core must pass without cloud connectivity once selection is confirmed.

| ID | Scenario | Required result |
|---|---|---|
| T01 | Known translation/rotation in a rectangular stage | Correct axes, anchor and yaw; no square-aspect distortion |
| T02 | Mirrored/resized preview selection | Prompt maps to the exact source object |
| T03 | Partial cover removes one side's points | Anchor does not jump to the remaining-point centroid |
| T04 | Full cover or dominant hand features | LOST/invalid rather than confidently tracking the hand |
| T05 | Symmetric or low-texture object | Position-only or explicit unsupported selection; no invented yaw |
| T06 | Two objects approach/cross | No silent identity swap; ambiguity becomes a gap |
| T07 | Backward movement | Fixed/target-facing actor need not face velocity |
| T08 | Late mask after source/cast change | Stale result rejected; no wrong-frame initialization |
| T09 | Camera bump/calibration edit | Existing takes preserved; new run requires current calibration |
| T10 | Stop with queued frames or uneven capture | Consistent end time; no silent tail loss or frame-count timing |
| T11 | Save/reload and failed write | Same selected takes, timestamps and gaps; prior project intact |
| T12 | Camera retake | Actor paths unchanged; camera replacement explicit |
| T13 | Remote timeout/segmenter failure | Manual/local selection remains usable; no background retries |
| T14 | Budget warning/expiry/network loss | No new paid jobs; shutdown verification or visible failure escalation |
| T15 | Export/project package round-trip | Version, assets, coordinates and duration preserved |
| T16 | Lift/tip | No fabricated height; detectable model failures lower validity |
| T17 | Re-click after occlusion | New segment retains confirmed actor ID and old missing interval |
| T18 | Take with invalid tracking ranges | Timeline/export identifies gaps; held samples never become observations |
| T19 | SAM3/SAM2 payload fixtures | Provider-specific decoder produces correctly aligned binary mask; overlays/unknown encoding rejected |
| T20 | Point-only and correction requests | No unintended default text; correct foreground/background prompts; confirmed actor IDs stay application-owned |
| T21 | Sponsor expiry, billing-required response, or rate limit | No paid fallback or retry storm; manual/local operation continues |
| T22 | Timeout, ambiguous submission, late/duplicate result | Reconcile known request ID; no blind duplicate submission or mutation of newer state |
| T23 | Offline reopen after cloud selection | Local mask/evidence sufficient; no provider call or credentials in package |
| T24 | Invalid remote asset URL or oversized payload | Safe rejection; no private-network fetch, unbounded download, or lost prior selection |
| W01 | Generated set selected, scaled, then reverted | Actor/camera trajectories and timing unchanged; original stage always available |
| W02 | Failed/superseded world generation | Previous environment retained; no accidental replacement or duplicate job |
| W03 | Cached set reload, missing asset, renderer failure | Local asset works offline when present; explicit built-in fallback otherwise |
| W04 | Splats plus characters during live camera pass | Measured performance acceptable and occlusion reviewed; no invented collision/contact |

Proposed performance gates on the selected Mac/setup:

- At least 15 valid pose updates/second on the controlled fixture while observable.
- p95 capture-to-render delay below 200 ms over a 60-second run; report valid coverage and dropped frames alongside latency.
- A target of at least 30 rendered frames/second for the simple stage, measured independently from tracking.
- Stationary anchor jitter below 1% of stage width; known-motion position error below 2% of width on the near-planar fixture.
- Click response aspiration: warm p95 below two seconds end-to-end including upload/queue/download. Measure at least 20 prompts if reporting p95, with cold and warm results separated. Slower successful setup may ship with an explicit loading state and measured delay; it is not a live-tracking failure. Requests beyond the 15-second deadline fall back without blocking capture.
- Replay event and camera alignment within 100 ms against the source timeline.

Use frame IDs and an explicit browser/backend clock-offset handshake for latency measurement; synchronize clocks rather than subtracting unrelated timestamps. Supplement with a simple filmed movement-to-display check if needed. Performance cannot be “passed” by suppressing difficult frames; invalid coverage remains part of the report.

Run targeted tests during changes. Run the applicable full small suite once for calibration/timing/schema changes or release certification. Promote an individual checkpoint with its relevant tests and fallback checks; run the full applicable pack at F, and the environment plus shared rendering/persistence tests at G. No duplicate builds/tests, unnecessary dependency reinstallations, or repeated passing checks.

## 11. Handoff and later phases

Phase 1 handoff includes a launch command, pinned dependencies, tested object/view profile, local/manual fallback instructions, one saved demo project, fixture/test results, measured performance, known limitations, provider schema fixtures, verified sponsor limits/expiry, and a GPU cost/cleanup receipt if rental was used. Include environment assets/transforms only if G passes. Clearly distinguish provider-documented capabilities from behavior actually tested on this Mac.

Later work builds on the same tracks and composition records:

- Phase 2: stronger object/occlusion handling and optional measured tracker replacement.
- Phase 3: richer assets/animation, clean video/scene exports and shot-reference workflows; extend the same environment adapter if G was implemented.
- Phase 4: separately validated richer physical control or generator integrations; optionally evaluate Tavus for an explicitly requested conversational directing interface.

The earlier roadmap remains the product overview; this document controls Phase 1 scope and budget. The first coding task is checkpoint A. The first demo claim is newly recorded markerless blocking—not inferred acting, perfect arbitrary-object tracking, or generated photorealistic footage.
