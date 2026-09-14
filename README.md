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

- fal.ai SAM3 proposes a mask from a click; SAM2 and reviewed manual regions are fallbacks.
- Local OpenCV tracking keeps continuous video off the network.
- A simple Three.js stage is always available.
- World Labs can provide an optional generated virtual set after the core workflow works.
- Tavus is deferred; it is not a geometric tracking dependency.
- Sponsored API access is used first. GPU rental is a last resort with a $30 operating ceiling, preserving $10 below the $40 budget.

The guaranteed tracking profile is intentionally narrow: compact, textured objects; a near-overhead fixed camera; visible top surfaces; and movement primarily on the tabletop. Tracking loss is shown honestly rather than silently guessed.

## Tracking strategy

```text
click or reviewed region
          ↓
initial object mask
          ↓
local feature/point tracking
          ↓
robust planar pose estimate
          ↓
versioned actor and camera trajectories
          ↓
Three.js replay and shot references
```

The reliable fallback is planar position with fixed or look-at facing. CoTracker3 is the first post-take tracking experiment. SpatialTrackerV2 is an experimental inferred-3D path, not measured depth.

For genuine metric 6-DoF, the most credible hackathon experiment uses an enrolled object with known geometry and calibrated RGB correspondences (PnP). OnePose++ is a later scanned-object candidate. LiDAR is not required, and SAM plus additional 2D points is not presented as full 6-DoF.

## Current status

This repository now includes the first offline implementation slice: immutable video import, a canonical 15-fps proxy, reviewed rectangular selection, local OpenCV feature tracking, fail-closed tracking loss, tabletop coordinate mapping, versioned trajectory candidates, provider request/response validation, a CLI, and deterministic tests.

It is checkpoint A, not the completed Phase 1 app. Hosted inference, webcam capture, the review UI, two-actor composition, the camera pass, 6-DoF, and optional environments are not implemented yet. No inference job, GPU rental, or provider resource has been created.

See [implementation setup and CLI usage](IMPLEMENTATION.md) to run the current slice. The next proof is one ordinary object surviving natural hand manipulation in a recorded 5–10-second take.

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
