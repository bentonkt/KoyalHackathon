# PocketStage

**Turn everyday objects into physical controls for directing a virtual shot.**

PocketStage is a markerless tabletop previsualization tool for AI and traditional filmmaking. A filmmaker clicks ordinary desk objects, assigns them to virtual actors or a camera, performs a short scene, and replays the result as a virtual shot.

> Your desk becomes a film set.

## The idea

1. Point a fixed camera at a tabletop and calibrate the stage.
2. Click and confirm two everyday objects, then assign them to virtual actors.
3. Move the objects to record actor blocking and timing.
4. Replay that performance while using another object to record a camera pass.
5. Review, replace takes, save the scene, and export shot references.

PocketStage does not try to infer a human performance from a bottle or stapler. The objects directly control scene position, facing when observable, timing, and camera movement. Character animation can come from simple procedural motion or deliberately selected assets.

## Phase 1

The first release targets one fixed-camera scene, two actor bindings, one camera binding, and 5–10-second takes on an M4 Mac.

- fal.ai SAM 2 Video supplies reviewed object masks after a 5–10-second take; Video Depth Anything supplies separate, nonmetric depth signals.
- Local OpenCV tracking remains an independent offline fallback. Hosted processing uploads the canonical clip only with explicit consent.
- A simple Three.js stage is always available.
- World Labs can provide an optional generated virtual set after the core workflow works.
- Tavus is deferred; it is not a geometric tracking dependency.
- Sponsored API access is used first. GPU rental is a last resort with a $30 operating ceiling, preserving $10 below the $40 budget.

The guaranteed tracking profile is intentionally narrow: compact, textured objects; a near-overhead fixed camera; visible top surfaces; and movement primarily on the tabletop. Tracking loss is shown honestly rather than silently guessed.

## Tracking strategy

```text
recorded take + reviewed object prompts
          ↓
SAM 2 Video masks + shared Video Depth Anything
          ↓
approximate centroid motion + relative object positions
          ↓
JSON / CSV tracks + rendered motion preview
          ↓
reviewed stage mapping (integration still pending)
          ↓
Three.js replay and shot references
```

The reliable fallback is planar position with fixed or look-at facing. CoTracker3 is the first post-take tracking experiment. SpatialTrackerV2 is an experimental inferred-3D path, not measured depth.

For genuine metric 6-DoF, the most credible hackathon experiment uses an enrolled object with known geometry and calibrated RGB correspondences (PnP). OnePose++ is a later scanned-object candidate. LiDAR is not required, and SAM plus additional 2D points is not presented as full 6-DoF.

## Current status

The Python pipeline includes immutable import, canonical proxies, independent OpenCV tracking, explicit tabletop mapping, hosted SAM/depth jobs, shared-depth multi-object runs, approximate centroid motion, relative moving/static object positions, and JSON/CSV/video exports. SAM and depth have completed on supplied real clips. Raw footage, private cloud state, and credentials are deliberately not committed.

The [Director's Desk web app](app/README.md) provides mock-backed actor/camera recording, virtual playback, review, and import of reviewed stage-space candidates. It also accepts the approximate multi-object `motion-tracks.json` through an explicit artistic scale/origin review: image offsets remain labeled degraded controls, and raw depth is preserved as evidence rather than renamed height. The full integrated Phase 1 application and 6-DoF are not complete.

See [implementation setup and CLI usage](IMPLEMENTATION.md). The next integration is replacing file handoff with a local transport after Benton's capture protocol stabilizes; the renderer-facing trajectory contract already preserves source timing and tracking gaps.

## Documentation

- [Implementation setup and current capabilities](IMPLEMENTATION.md)
- [Everyday-object product and implementation roadmap](docs/PocketStage_Everyday_Object_Implementation_Plan.md)
- [Phase 1 implementation specification](docs/PocketStage_Phase_1_Implementation_Plan.md)
- [Phase 1 adversarial review](docs/PocketStage_Phase_1_Adversarial_Review.md)
- [RGB 3D tracking and 6-DoF feasibility](docs/PocketStage_RGB_3D_Tracking_Feasibility.md)

## Key product boundaries

- Everyday objects are controls, not motion-generation inputs.
- Scripted or inferred movement never replaces recorded trajectories without review.
- Complete occlusion creates a real tracking gap.
- Monocular RGB depth is inferred unless calibrated geometry establishes metric scale.
- Actor takes, camera takes, calibration, environments, and tracking outputs remain independently versioned so optional upgrades do not invalidate earlier work.
