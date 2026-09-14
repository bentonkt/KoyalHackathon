# PocketStage Phase 1 — adversarial review

Reviewed September 14, 2026 against the current Phase 1 specification and everyday-object roadmap. This is a specification review, not a code review or measured feasibility result. No implementation plans were modified, model jobs launched, or resources provisioned.

## Verdict

Proceed with the bounded tracking spike, but do not treat the full Phase 1 scope or its 6–12-hour estimate as validated. The architecture usefully separates hosted selection, local tracking, recorded trajectories, and optional environments. The remaining risks are primarily tracking usability and composition correctness—not GPU availability.

Three P1 gaps should be resolved before building beyond the spike. Three P2 gaps should be resolved before calling the result a certified, reusable filmmaking tool. P1 means a core behavior or data-integrity contract is missing; P2 means a material verification, handoff, or fallback weakness.

## R1 — P1: Selection fallback does not rescue the live tracking failure that matters

Evidence: [tracking stack, line 51](./PocketStage_Phase_1_Implementation_Plan.md:51), [failure behavior, line 122](./PocketStage_Phase_1_Implementation_Plan.md:122), [performance gates, line 292](./PocketStage_Phase_1_Implementation_Plan.md:292).

Both a perfect SAM mask and a manually reviewed region feed the same optical-flow tracker. When the user grips an object, features may disappear or transfer to the hand. Switching the selector does not address that failure. The plan acknowledges the identity limitation, but then requires never confidently following the hand without specifying an independent identity check or a measurable limit on failure.

OpenCV's feature status indicates that optical flow was found, not that the feature still belongs to the intended object. The inference that this cannot establish semantic object identity is the reviewer's; it is not a promised feature of the API. [OpenCV Lucas–Kanade documentation](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html).

The current gates also say to report valid coverage without setting a minimum. An overly conservative system can stay LOST through most useful movement and still look safe in the loss tests. An overly permissive one can track the wrong surface smoothly. Neither delivers directing.

Required change:

- Make natural hand manipulation the first fixture, not just clean object translation followed by an occlusion demonstration.
- Define a deliberately narrow supported interaction: compact textured objects, visible top features, edge pushing/gripping, fixed near-overhead camera. Do not require special markers or bases.
- Add a reference-appearance check to the spike, or explicitly narrow the support claim to the interaction that passes without it. Appearance checks are additional evidence, not a universal guarantee.
- Propose an initial usable-take gate: three different everyday objects, five 10-second trials each, at least four successful trials per object, at least 95% valid coverage during annotated observable movement, no re-selection within successful trials, and no undetected identity swap on the tested fixtures. These are suggested acceptance thresholds, not measured reliability claims.
- Test deliberate full occlusion separately and measure the time to invalidate. Keep those intentionally unobservable intervals out of the observable-coverage denominator, but include them in the report.

Fallback: use another ordinary object, improve lighting/view, or narrow the certified interaction. If that still fails, stop promotion at the spike. Replay of an earlier take remains useful, but is not a functioning live-tracking fallback. More cloud access does not change this gate.

## R2 — P1: Versioned takes can still be composed in incompatible coordinate systems

Evidence: [calibration, line 102](./PocketStage_Phase_1_Implementation_Plan.md:102), [camera pass and persistence, line 142](./PocketStage_Phase_1_Implementation_Plan.md:142), [composition operation, line 159](./PocketStage_Phase_1_Implementation_Plan.md:159).

Example: record actors, bump the physical camera, recalibrate with a different rectangle/origin/scale, then record a camera pass. Every take has valid version metadata, but their positions need not describe the same stage. The plan preserves versions without requiring composition compatibility checks. A saved camera move can therefore be spatially wrong while its timestamps are correct.

Required change: distinguish a persistent stage coordinate frame from a particular camera-to-stage calibration. Record stage-frame ID, axis convention, units/extent, capture-calibration ID, and the actor-performance reference for each camera take. Reject a composition unless its frames match or an explicit reviewed transform exists. For Phase 1, rejecting incompatible takes is sufficient; automatic reconciliation is unnecessary.

Reopening a project permits replay, not automatic reuse of a saved calibration for fresh capture. Require camera/setup validation before new recording. Environment alignment must remain separate from these recording coordinates.

Acceptance: change origin, aspect ratio, or virtual size between passes; the app rejects the incompatible composition and retains the original. Recalibration into the same reviewed persistent stage can be supported later without redesigning the records.

## R3 — P1: Re-selection and tracking loss have no complete recording lifecycle

Evidence: [re-click behavior, line 130](./PocketStage_Phase_1_Implementation_Plan.md:130), [recording, line 140](./PocketStage_Phase_1_Implementation_Plan.md:140), [T17, line 277](./PocketStage_Phase_1_Implementation_Plan.md:277).

Preserving a new segment and a gap does not answer whether scene time pauses while a mask request runs, whether the other actor continues recording, or whether actor replay continues during camera re-selection. A new clicked anchor can also change the controlled physical point. Keeping the same actor ID alone does not prevent a spatial jump.

Required change: specify the recording state machine and choose one policy. The smallest Phase 1 policy is no in-take re-selection or pause/resume splicing. A user may stop immediately or let a bounded take finish with missing intervals. After stop, reselect, review the anchor, and start a new complete take. Camera retry restarts actor playback at the beginning. Never auto-select an incomplete retake over the previous composition.

Keep the segment schema for future repair, but do not imply that arbitrary segments can already be stitched into a seamless performance. If in-take repair is retained, its scene-clock, anchor-offset, and multi-actor rules must be designed and tested explicitly.

Acceptance: lose one actor while the other moves; lose the camera controller during replay; click reselect during recording; stop while a cloud proposal is pending. Each produces a deterministic timeline and leaves the prior selected shot intact.

## R4 — P2: The latency measurement can exclude camera delay

Evidence: [capture timestamps, line 84](./PocketStage_Phase_1_Implementation_Plan.md:84), [latency verification, line 299](./PocketStage_Phase_1_Implementation_Plan.md:299).

Timestamping after a decoded frame reaches Python measures downstream software delay. It does not establish when the sensor saw the movement. A camera/backend buffer can deliver old frames that then pass a fast software-latency test. Browser/backend clock synchronization cannot recover time already spent before that timestamp. OpenCV warns that capture-property behavior depends on hardware, drivers, and backend; an assumed buffer setting is not sufficient evidence. [OpenCV video-I/O properties](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html).

Required change: distinguish backend-receipt-to-render latency from physical-motion-to-display latency. Make the filmed physical/display check required for the live-demo claim, rather than optional. Store hardware capture timestamps only where actually available and verified; do not relabel receipt timestamps as sensor timestamps.

Acceptance: a filmed series of motions is compared with displayed motion. Run it while recording evidence, rendering the stage, and simulating a slow provider request. Acquisition and recording must not block behind inference, disk encoding, or an unbounded preview queue. Report measurement resolution and jitter, not a falsely precise number.

## R5 — P2: The AI/camera-filmmaking promise lacks a required portable visual output

Evidence: [filmmaking promise, line 42](./PocketStage_Phase_1_Implementation_Plan.md:42), [export boundary, line 54](./PocketStage_Phase_1_Implementation_Plan.md:54), [later exports, line 310](./PocketStage_Phase_1_Implementation_Plan.md:310).

The core guarantees an application-specific scene package and replay, while calling the result useful shot references for AI filmmaking. That can be adequate for in-app rehearsal, but there is no required image or video artifact usable by a collaborator or another filmmaking tool. This is a product-scope mismatch, not a reason to add video generation.

Required decision: either describe Phase 1 strictly as in-app previsualization for both audiences, or add a minimal shot-reference export before generated environments. A small option is three user-selected viewport PNGs plus a manifest recording scene times, aspect ratio, camera settings, stage units, composition hash, and validity warnings. Any wider lens-control claim also needs an explicit vertical/horizontal FOV convention. MP4 and generator-specific adapters can stay deferred.

Acceptance: open the exported images outside PocketStage and match them to saved replay times. The package must distinguish reference imagery from proven generator conditioning.

## R6 — P2: Optional environments can break the supposedly independent core at startup

Evidence: [adapter boundary, line 78](./PocketStage_Phase_1_Implementation_Plan.md:78), [fallback promise, line 251](./PocketStage_Phase_1_Implementation_Plan.md:251), [W03, line 287](./PocketStage_Phase_1_Implementation_Plan.md:287).

A scene-switch button cannot recover from an optional renderer import failure that prevents the app from starting. Likewise, “unsupported future schemas are rejected” does not establish that a newer generated-set project remains usable after disabling that feature. Interface separation helps, but is not an executable rollback guarantee.

Required change: keep the built-in renderer on an independently loadable path; load the generated-set renderer only when requested and contain load/runtime errors. A supported project with an unavailable environment must preserve its unresolved environment record, load actor/camera data, and use a built-in preview fallback without destructively rewriting the project. Define rollback as runtime feature fallback; do not imply older binaries can read arbitrary newer schemas.

Acceptance: launch with the optional renderer import forced to fail, network disabled, no sponsor credentials, and a saved generated-set composition. Actors, camera, and ordinary-stage replay must still work. Preserve a known-good F fixture/build before adding G; no duplicate builds are needed during routine edits.

## Scope and sequencing recommendation

Keep fal-assisted selection, local OpenCV tracking, separate actor/camera passes, and durable raw evidence. Keep Tavus and rented GPUs off the initial dependency path. Do not add another learned tracker merely to avoid deciding whether the first interaction works.

The first spike must also confirm the actual capture source, stable mounting, permissions, usable lighting, and screen visibility while manipulating the objects. The Mac's processor specification is not a complete tabletop capture setup. Any missing hardware cost needs an explicit decision, not an assumption that sponsor credits cover it.

Recommended order: physical capture and natural-manipulation gate → coordinate/lifecycle contracts → two actors and durable takes → camera pass → click-path certification → minimal portable references if desired → optional generated set.

Treat 6–12 hours as provisional until the capture/tracking and hosted-mask probes pass. The plan currently includes two runtimes, multiple interfaces, crash-safe persistence, correction UI, timing instrumentation, and 28 acceptance scenarios. Free inference reduces service cost, not that engineering work. Implement only the passing selector; keep an alternate as a narrow adapter contract rather than building both eagerly.

## Completion recommendation

Resolve R1–R3 before expanding past the spike. Resolve R4 before claiming live latency. Resolve R5 through an explicit deliverable decision. Resolve R6 before adding G. Then promote the last passing capability with its relevant tests and fallback checks.

This review does not prove the product infeasible. It identifies the decisions and evidence needed before claiming the core is reliable or later phases can always fall back without rework.
