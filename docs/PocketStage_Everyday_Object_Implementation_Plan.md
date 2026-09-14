# PocketStage — everyday-object directing roadmap

Revision: September 14, 2026. Active product direction. An [offline feasibility runner](../IMPLEMENTATION.md) now exists; the full application and capability ladder below remain implementation targets.

## Product and Phase 1 decision

**Move everyday objects to direct virtual actors and a camera. Record short performances, process them, and review the resulting shot.**

The [Phase 1 implementation specification](PocketStage_Phase_1_Implementation_Plan.md) controls the first build:

**SAM 2 Video masks + Video Depth Anything + local geometric solving, with an independent lightweight OpenCV fallback.**

Use a fixed RGB webcam and a Mac. Record 5–10-second takes and process after recording; neural inference need not be real-time. No DancingBox, special markers, LiDAR, scanning, measured-object enrollment or 6-DoF milestone.

Phase 1 transfers supported tabletop movement and observable planar heading to virtual actors. Relative depth is a separately validated artistic control, not metric distance or recovered physical height. “Local geometric solving” does not mean solvePnP or a free-space rigid pose.

Normal filmmakers get blocking, framing and shot references. AI filmmakers get the same references plus structured trajectories. Generator-specific control is a later tested adapter, not an initial promise.

## Phase 1 experience

1. Set a rectangular tabletop stage under a fixed camera.
2. Record up to two ordinary actor objects, then select them on clean saved frames.
3. Process temporal masks and one shared depth estimate from the same canonical clip.
4. Review mask-assisted local motion, gaps, heading availability and relative-depth evidence.
5. Accept a performance; record and process a separate camera-object pass against its playback clock.
6. Save/reopen and export three selected shot-reference PNGs with their trajectory/shot manifest.

The default camera has configured height and lens plus explicit look-at or supported heading. Relative-depth mapping is off until reviewed. Symmetric or partly hidden objects may retain position while losing heading. Full occlusion creates a gap, not an invented motion path.

The first integration gate verifies actual mask and raw-depth payloads on the sponsored endpoints. Public endpoint availability does not establish account coverage or suitable output. In particular, segmented/box-overlay video is not automatically a raw-mask contract.

## Capability ladder without rebuilding the foundation

These are later product phases. Phase 1's internal A–F implementation checkpoints are specified in its controlling document and are not additional product phases.

| Phase | New capability | Reused foundation | Fallback if the addition fails |
|---|---|---|---|
| 1 — Recorded directing | Two actors, independent camera pass, SAM 2/depth processing, local solving, reviewed playback and PNG/manifest export | Establish immutable capture, versioned stage/time records and adapter-independent tracks | Mask-assisted planar mode, then local-only tracking; accepted playback always survives |
| 2 — Better tracking and editing | Evaluate CoTracker locally; add bounded corrections, comparisons and certified video animatic export | Same original takes, selections, job interface, candidate records and scene renderer | Phase 1 adapters and PNG/manifest export |
| 3 — Richer scene presentation | Optional World Labs environments, asset replacement and deliberate animation behavior | Existing trajectories, actor IDs, stage coordinates, composition and camera | Neutral stage, placeholders and established actor motion |
| 4 — Advanced spatial experiments | Evaluate SpatialTrackerV2 or OnePose++; consider enrolled 6-DoF only if later approved and validated | Same source captures, provenance, candidate review and optional capability fields | Certified planar/relative-depth tracks; no forced enrollment or hardware change |
| 5 — Filmmaking integrations | Tested AI-video conditioning, richer camera handoff, optional presentation tools | Accepted composition and export contract | Local playback, reference images and portable trajectory data |

Each phase must ship independently. A model experiment can run earlier when time permits, but it cannot become an undeclared dependency. Phase 4 is exploratory, not a promise that RGB-only arbitrary-object 6-DoF will work.

World Labs and Tavus are available sponsor options according to the user, but neither is necessary for Phase 1. Custom model deployment eligibility remains unconfirmed.

## Non-negotiable reuse contracts

**Capture once, process repeatedly.** Original takes and their timestamps are immutable. A canonical proxy has a recorded map back to source frames. Every provider uses that same proxy or declares a validated transformation.

**One coordinate contract.** Stage origin, axes, scale and revision are explicit. Actor and camera takes compose only when stage and time mappings are compatible. Physical camera changes require revalidation.

**One track interface, optional capabilities.** Position, heading and relative depth have independent validity. Future full poses must be separate typed capabilities with explicit units/provenance, not a reinterpretation of Phase 1 depth.

**Candidates before acceptance.** New processing writes a new candidate. It cannot overwrite accepted performance, original evidence or earlier baseline output. Rerunning a camera never changes actor motion.

**Rendering does not know providers.** Playback reads normalized local records; it does not require fal, a GPU worker or a live API key. Assets and environments are replaceable without changing tracks.

**Export remains portable.** Manifests include composition revision, time, camera settings, source references, uncertainty and artistic mappings. Later adapters consume this contract instead of requiring recapture.

**Failure is visible.** Selection fallback does not solve lost identity. Missing evidence stays missing, and unavailable depth does not become zero-valued measured height.

## Phase 1 fallback and promotion policy

The desired full release includes both hosted models integrated with local geometry. A functioning baseline alone is labeled “local fallback complete,” not full Phase 1 completion.

Promote temporal masks only after verifying per-frame usability, alignment and identity behavior. Promote depth only after controlled near/far and static-background tests demonstrate a useful relative cue. If depth fails, retain mask-assisted planar tracking. If masks fail, use reviewed manual selection and local tracking. If local tracking fails, preserve the take for reprocessing/re-recording; do not claim a working tracker.

Test natural hand manipulation, two-object crossings, symmetry, full occlusion, camera changes, network failures, canceled jobs and save/reopen. Quality and timing thresholds live in the Phase 1 specification.

## Resources and scope discipline

Primary runtime: Mac UI/capture/OpenCV with sponsored fal inference. Default rented GPU cost is zero. Keep all incremental paid charges under a $30 operating ceiling, leaving $10 reserve within the user's approximately $40 maximum. Verify endpoint coverage, expiry and billing before launches.

CoTracker is a separate local benchmark. SpatialTrackerV2 and OnePose++ stay optional GPU experiments unless deployment access and budget are confirmed. No sponsored-service claim substitutes for an actual endpoint smoke test.

Protect data integrity and the full local directing loop before adding presentation polish. Every milestone should leave a demonstrable result and retained evidence, not only a model demo.

## Document status

The Phase 1 specification is authoritative for current scope. The [adversarial review](PocketStage_Phase_1_Adversarial_Review.md) and [RGB/3D feasibility assessment](PocketStage_RGB_3D_Tracking_Feasibility.md) retain historical analysis; their earlier recommendations do not reintroduce 6-DoF or a CoTracker-first pipeline.

The earlier roadmap is preserved in [the archive](archive/PocketStage_Overarching_before_API_video_revision.md).
