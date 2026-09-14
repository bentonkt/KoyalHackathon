# PocketStage — everyday-object directing plan

This is the active PocketStage direction. It supersedes the DancingBox-dependent recommendation in the earlier feasibility assessment. This is an implementation plan; no application or tracking benchmark has been built yet.

The [Phase 1 implementation specification](./PocketStage_Phase_1_Implementation_Plan.md) now controls the first build: checkpoints A–F combine the one-object spike, two-actor stage, recording, camera pass, and bounded click-selection assistance. It uses sponsored fal.ai selection with local Mac tracking and adds an optional World Labs set checkpoint G after core certification. Tavus is deferred. The default needs no GPU rental; contingency spending retains a $30 operational ceiling and $10 margin below the requested $40 maximum. The P0–P5 table below is the earlier capability ladder, not a competing Phase 1 scope or schedule.

## Product decision

**Click an everyday object, assign it a virtual actor or camera, and move it to direct a shot.**

No DancingBox, motion diffusion, SMPL, Pi3 reconstruction, printed markers, or special proxy bases are required. Physical objects control blocking and camera movement—not inferred human joint motion. Virtual characters can be humanoids, creatures, vehicles, or simple shapes because their animation comes from deliberately selected assets or procedural behavior.

The initial promise is ordinary, visually trackable objects under a fixed camera. Do not promise reliable orientation from every object or exact tracking through full occlusion.

## First-release experience

1. **Set the stage.** Mount the camera above or steeply overlooking a tabletop. Select four ordered corners of a rectangular play area and its aspect ratio. Map this to a chosen virtual stage size.
2. **Cast objects.** Click an object and confirm the proposed mask. Additional positive/negative clicks or an outline/box can correct selection. Assign Hero, Villain, or Camera and a virtual asset.
3. **Check tracking.** Move each object briefly. Show selected pixels, tracked features, position quality, and orientation availability before recording.
4. **Direct actors.** Record a 5–10 second take with up to two actor objects. The virtual scene follows their ground-plane movement. Keep the tabletop visible and avoid lifting or rolling objects.
5. **Direct the camera.** Replay the saved actor take and record a camera-object pass against the same clock. A second operator may perform all three simultaneously, but this is not required.
6. **Review the shot.** Scrub both tracks, re-record the camera independently, and save the take. Start with a fixed lens and camera height.
7. **Use the result.** Save the scene/timing package and a viewport recording or rendered animatic after export is certified.

For camera filmmaking, this is a blocking and framing rehearsal, not a calibrated physical camera-control system. For AI filmmaking, it supplies an animatic and shot references; exact control of a particular video generator requires a later tested adapter.

## What physical movement controls

| Physical signal | Virtual effect | Boundary |
|---|---|---|
| Actor position on table | Character ground-plane position | Does not infer depth or body pose |
| Observable planar rotation | Character heading, when enabled | May be unavailable for symmetric or three-dimensional objects |
| Speed and pauses | Optional selected idle/walk/run animation blend | Rule-driven animation, not recovered performance |
| Camera-object position | Virtual camera ground-plane movement | Height and lens come from settings |
| Reliable camera-object heading | Camera yaw in heading mode | Explicit alternative is look-at-target mode |
| Recorded source time | Shared scene timing | Capture frame count is not a substitute for timestamps |

Offer fixed heading, tracked heading, and explicit look-at modes. A character retreating while facing another actor must not turn around merely because velocity reverses. Translation and facing are independent.

A knight or dragon may have a licensed animation clip selected by the filmmaker. Neither needs a humanoid motion model. Placeholder shapes and procedural motion remain the guaranteed rendering fallback.

## Tracking architecture

Keep three independent components:

- **ObjectSelector:** click/image → reviewed mask or manually outlined region.
- **PointTracker:** selected features + video frames → point positions, visibility/quality, and source timestamps.
- **PoseEstimator:** valid correspondences + calibration → bounded position/orientation estimates and status.

Hosted fal SAM3 is the first click-selection candidate; fal SAM2 is an alternate adapter. A single click proposes a mask requiring confirmation—not guaranteed object selection. Validate each endpoint's prompt schema and mask encoding before promotion. Selection runs only during setup/reselection, never per live frame. [SAM3 API](https://fal.ai/models/fal-ai/sam-3/image/api), [SAM2 API](https://fal.ai/models/fal-ai/sam2/image/api).

CoTracker3 Online is a candidate learned tracker, not a mandatory runtime dependency. Its documented online interface processes chunks and returns tracks/visibility; “online” alone does not prove low end-to-end latency on the available hardware. [CoTracker official implementation](https://github.com/facebookresearch/co-tracker).

For the currently available M4 Mac, first establish a lightweight local tracking baseline with selected features and pyramidal Lucas–Kanade optical flow. OpenCV provides that tracking primitive. This is a fallback implementation of the same tracker interface, not a different product. Compare CoTracker against it on the actual object/occlusion fixtures before promoting the learned path. [OpenCV optical flow](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html).

If hosted selection cannot be validated quickly, use a reviewed outline/box and visible feature selection. That mode must say “Select region,” not pretend one-click segmentation worked. Promote click-to-select only after its end-to-end gate passes.

Use the user's stated hackathon API access first, after verifying endpoint coverage and expiry. Do not install local neural models or rent a GPU before the lightweight core works. A justified rental experiment remains subject to the Phase 1 budget and shutdown controls. No service has been provisioned. Remote selection/refinement must disclose media transfer; live Phase 1 tracking remains local.

World Labs is an optional virtual-set provider after the core workflow is certified. Validate the Three.js/Spark import path with a bounded splat asset; review floor/scale/alignment and preserve a built-in-stage switch. This does not reconstruct the tabletop or infer collisions. Provider failure cannot alter existing actor or camera takes. [World Labs API](https://docs.worldlabs.ai/api), [renderer examples](https://docs.worldlabs.ai/api/examples).

Tavus is deferred: conversational video and visual awareness are not a demonstrated geometric tracking substitute. A later voice-director interface would be a separate feature, not a dependency. [Tavus documentation](https://docs.tavus.io/sections/conversational-video-interface/faq).

## Geometry and reliability corrections

### Fit in the intended coordinate system

OpenCV's `estimateAffinePartial2D` estimates a limited affine/similarity transform from point correspondences and supports robust estimation. That mathematical model is useful, but an arbitrary three-dimensional object under perspective does not necessarily satisfy it. [OpenCV calibration and transformation API](https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html).

Do not fit image rotation and reuse its angle unchanged as tabletop yaw. For approximately coplanar features, transform matched points through the calibrated table mapping and fit the planar motion there. Alternatively, map an estimated anchor and a second orientation point into stage coordinates before deriving a stage heading. Both approaches remain approximate when feature heights differ.

Keep a stable user-reviewed anchor; transform that anchor rather than averaging only the currently visible points. Otherwise a hand covering one side of an object can shift the apparent center without any real translation.

Four corner clicks define a planar mapping, not camera intrinsics, object height, or metric scale. Preserve the intended rectangle's aspect ratio; mapping any rectangle to a square and later assuming metric angles introduces distortion. Known dimensions are needed only if physical measurements are promised. [OpenCV homography concepts](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html).

Tall objects introduce parallax even when their bases remain on the table. Start with a near-overhead view and compact objects with visible top surfaces. A tall can can still be tested as a position controller, but precision and yaw must be measured rather than assumed.

### Rotation is optional per object

A textured flat case or card is a better initial orientation controller than a smooth cylinder. Rotation around a three-dimensional object's vertical axis can change visible surfaces rather than merely rotate the image. Rolling, tipping, lifting, and deforming fall outside the initial planar contract.

At initialization, let the filmmaker specify “forward” using the object's visible geometry or choose a fixed/look-at heading. Track rotation only while its estimate remains supported. When yaw is uncertain, retain a visibly held heading or disable yaw; do not sacrifice an otherwise usable position track.

Scale change is a diagnostic signal, not measured elevation. Do not turn apparent size changes into jumps or flying motion.

### RANSAC is not an identity guarantee

RANSAC can reject inconsistent correspondences. It cannot identify which rigidly moving group is the intended object if most features have moved onto a hand or background. Use several checks together:

- Good-feature distribution inside the reviewed object region, avoiding boundaries where practical.
- Track visibility or forward–backward consistency, depending on the producer.
- Minimum inlier count, inlier ratio, spatial spread, and residual.
- Bounds on sudden translation, rotation, and scale changes.
- Periodic appearance/region checks when confidence degrades.
- Explicit re-click/review after prolonged loss rather than automatic identity reassignment.

Twenty points is a starting sample budget, not a universal sufficient condition. Require points spread across the object, not twenty points clustered on one corner.

Track status is `TRACKING`, `DEGRADED`, or `LOST`. Position and yaw have separate validity. Full occlusion makes observed pose unavailable. A short visual hold may keep playback understandable, but must be labeled held and stored as missing evidence—not recorded as stationary truth.

Reacquisition starts a new tracking segment with a reviewed actor identity and transform. Preserve gaps and prior tracks. Do not bridge a long occlusion with an invented path.

## Minimal data contracts

| Record | Required content |
|---|---|
| StageCalibration | Version, ordered corners, aspect ratio, stage units/size, image transform and camera configuration |
| CastBinding | Stable actor ID, physical selection/mask, virtual asset, anchor, forward direction and heading mode |
| CaptureTake | Immutable video reference, timestamps, cast/calibration versions |
| TrackSegment | Actor ID, producer version, source frame times, raw point tracks, estimated pose, position/yaw validity, loss intervals |
| PerformanceTake | Selected actor tracks and explicit animation/heading policies |
| CameraTake | Track, timing alignment, lens, height, target/heading policy |
| EnvironmentVersion | Built-in/generated kind, provider reference, local asset hashes, reviewed transform/play area |
| ProviderJob | Purpose, input hash, request ID/state/deadline, sponsor eligibility; no credentials |
| SceneComposition | Selected performance and camera takes, asset/environment versions, common coordinate convention |
| ExportArtifact | Composition hash, frame rate/time mapping, output type and status |

Use one clock for all actors. Camera passes explicitly align to that clock. Store raw observations separately from smoothed paths so filtering can be changed without re-recording. Changing calibration or selections creates a version, not an overwrite of historical takes.

Use bounded frame queues. If processing falls behind, expose actual delay and apply a documented frame-dropping/resampling policy. Preserve source timestamps and flush final buffered frames on stop. Never call a smooth but several-seconds-delayed preview “real time.”

## Build ladder and fallbacks

| Stage | Deliverable | Gate | Fallback |
|---|---|---|---|
| P0 — Tracking spike | One selected everyday object → visible points → stable position; yaw when supported | Translation, pause, rotation, partial occlusion, loss/re-click tested | Reviewed manual region; no markers |
| P1 — Usable stage | Two actor bindings, shared coordinates, record/replay, simple Three.js scene | No identity swaps, correct timing, save/reload | One actor or manual correction of a visibly marked track |
| P2 — Camera direction | Everyday camera object, separate timed pass, fixed lens/height | Correct camera motion and independently replaceable camera take | Fixed camera or manual camera keys |
| P3 — Click-first assistance | Certified hosted segmentation; tracker upgrade only if it beats baseline | Actual latency and recovery measured on supported hardware | Manual region and local optical flow |
| P4 — Filmmaking output | Selected assets/environments, animation blending, animatic and scene export | Export preserves timing, axes, and framing | Simple assets and in-app replay |
| P5 — Broader object support | More difficult views, surfaces, occlusion recovery | Same fixture suite plus new failure cases | Earlier certified object/view profile |

The current Phase 1 schedule probes fal selection in checkpoint A and hardens it in E; World Labs is optional G. This older capability ladder is conceptual, not an execution order. The stable contracts do not depend on provider availability. CoTracker is promoted only if quality, latency, deployment, and licensing are acceptable. Failure of either learned component must preserve tracking/replay already recorded.

The first implementation task is Phase 1 checkpoint A: a bounded sponsor-access/mask probe followed by the local one-object spike. A four-hour build should target A–D on controlled objects, retaining click assistance if its probe passes. The reliable core is estimated at 6–12 focused hours; optional generated-set integration adds roughly 2–4. These are planning estimates, not guarantees.

## Acceptance fixtures

These are proposed tests, not measured results or reliability percentages.

1. Textured case: translation, stop, and in-plane turn with a stable anchor.
2. Tall can: quantify position distortion; reject unsupported yaw rather than report false precision.
3. Smooth/symmetric object: allow position-only use or explain that selection lacks reliable features.
4. Partial hand cover: position does not jump to the visible-point centroid.
5. Full hand cover: enter LOST; do not move the virtual actor with the hand.
6. Two objects approach/cross: no silent actor swap; ambiguous segments remain invalid.
7. Stationary object: bounded jitter and stable fixed heading.
8. Camera bump: invalidate calibration or request recalibration.
9. Object lift/tip: flag model inconsistency where detectable; never claim recovered height.
10. Re-click after loss: new segment, same confirmed actor, retained gap and history.
11. Record/replay: all objects and camera preserve timing; no delayed tail silently omitted.
12. Tracker/segmenter unavailable: manual-region/local-tracker path remains usable.
13. Camera pass replacement: actor paths and existing takes remain unchanged.
14. Heading versus velocity: a backward-moving actor may keep facing forward.
15. Asset change: a creature or vehicle uses the same control track without human-motion inference.

Proposed initial preview target: at least 15 pose updates per second with p95 capture-to-render delay below 200 ms on the selected setup. Measure actual latency separately from display frame rate. These targets are development gates, not promises about CoTracker or this Mac.

Before promoting a stage, test normal operation and its fallback. During iteration run only the directly affected tests; run the applicable small regression pack once for shared timing/calibration/schema changes or release certification.

## Scope and licensing

Keep scripts, dialogue, inferred actions, realistic contact, automatic editing, depth recovery, full six-degree-of-freedom tracking, and photorealistic video generation out of the first build. An optional generated 3D set is a separate visual enhancement, never a core completion requirement.

Removing DancingBox also removes the need for its motion checkpoint and the prior SMPL/Pi3 pipeline. It does **not** remove CoTracker's separate noncommercial restriction. Treat CoTracker as an optional research dependency until the intended use is cleared. For hosted models, verify endpoint-specific terms and sponsor eligibility separately from upstream code licenses. Local SAM2's core code/checkpoints have Apache 2.0 terms; also review renderer and generated/selected asset rights before distribution. Sponsor access is not blanket redistribution permission. [CoTracker license](https://github.com/facebookresearch/co-tracker#license), [SAM2 license](https://github.com/facebookresearch/sam2#license).

The product is markerless. Printed markers or tagged bases are not a fallback requirement. Its honest limits are supported objects, supported views, visible confidence, and recoverable tracking.

**First demo:** a case controls one character, a small textured box controls another, and a stapler or card controls the camera in a second pass. The same ordinary objects drive a newly recorded shot. If character animation is procedural or library-based, label it accurately.

**Positioning:** “Your everyday objects become actors and camera controls.” Avoid “any object, perfectly tracked with one click” until evidence supports it.
