# PocketStage: RGB Tracking and 6-DoF Feasibility

Scope update — September 14, 2026: this document preserves broader research, not the current build order. The [active Phase 1 plan](PocketStage_Phase_1_Implementation_Plan.md) now specifies SAM 2 Video masks + Video Depth Anything + local geometric solving, with lightweight OpenCV fallback. Phase 1 excludes 6-DoF, PnP and object enrollment. CoTracker is a separate local benchmark; SpatialTrackerV2 and OnePose++ remain optional later experiments. Earlier recommendations below do not override this decision.

## Recommendation

Build around a recorded 5–10-second RGB take, then produce a reviewed trajectory. Do not require LiDAR, live neural inference, or a full object scan for the basic experience. Preserve the existing local tabletop preview and recording format as the fallback.

Use three clearly separated capability levels:

1. **Supported tabletop blocking:** local preview, with CoTracker3 evaluated as a post-take point-tracking upgrade.
2. **Experimental free-space motion:** SpatialTrackerV2 on the same saved clip, labeled inferred 3D rather than measured depth.
3. **Enrolled 6-DoF:** known physical geometry or a reference reconstruction, with explicit camera calibration and scale. Begin with a measured everyday object and PnP; evaluate OnePose++ for broader scanned-object support.

The most defensible hackathon route to metric 6-DoF is not “SAM plus more points.” It is a restricted, geometrically enrolled object whose tracked image features correspond to known 3D locations. That can still be an ordinary book, package, or rigid case—not a special proxy or printed fiducial.

This assessment uses public implementations and documentation available on September 14, 2026. No PocketStage-specific model latency, accuracy, installation, or GPU-memory benchmark has been executed. Runtime targets below are experiment criteria, not measured predictions.

## Comparison

The judgments in the last column concern hackathon integration risk, not a universal ranking of research quality.

| Method | Actual output / necessary information | Deployment and latency evidence | PocketStage decision |
|---|---|---|---|
| CoTracker3 | 2D point trajectories and visibility; RGB clip and queries | Offline and chunked interfaces; official demo selects MPS when available | First learned point-tracking experiment; not a depth or 6-DoF solver [^1][^2] |
| SpatialTrackerV2 | Inferred 3D points, camera motion, geometry; RGB or supplied geometry inputs | Released offline path is CUDA-oriented; full app latency unknown | Best first no-scan 3D experiment; no metric guarantee [^3][^4] |
| OnePose++ | Object pose from query RGB plus reconstructed reference object | Enrollment/reconstruction required; old CUDA environment | Bounded scanned-object experiment, not instant click-to-6D [^5][^6][^7] |
| FoundationPose | Object pose from RGB-D plus model/reference representation | Released demo uses depth and CUDA | Defer under the no-depth-sensor constraint [^8][^9] |
| BundleSDF | Joint object reconstruction and 6-DoF tracking from RGB-D | Custom-data path needs depth, intrinsics and mask sequence; compiled stack | Defer; too many missing inputs/integration steps [^10] |
| ARKit reference objects | Native object pose from an enrolled reference | New moving-object iOS path requires iOS 27; enrollment can take hours | Conditional future native route, not a basic iPhone feature assumption [^11][^12] |
| MegaPose RGB | 6-DoF using RGB, calibrated camera, matching mesh and detection | Explicit depth-optional implementation | Better fit than FoundationPose when a faithful mesh already exists [^13] |
| Known-geometry PnP | Rotation/translation from known 3D-to-2D correspondences | Lightweight geometry on Mac; feature quality dominates | First controlled metric 6-DoF test [^14] |
| Calibrated dual RGB views | Triangulated 3D correspondences, then rigid pose | Synchronization/calibration rather than model inference is the burden | Strong alternate if two existing cameras are available [^15] |

Numbers in brackets refer to the linked source notes at the end.

## What must change in the proposed layered approach

### Points, depth and object pose are different outputs

A mask identifies an image region. A 2D tracker follows selected image locations. A depth estimator estimates distance-related values across the image. A rigid 6-DoF solver estimates three translations and three rotations of a defined object frame. These functions can cooperate, but they are not interchangeable.

CoTracker3 alone cannot turn a table homography into lifting, pitch and roll. The current plan already fits a robust transform to OpenCV features; replacing the feature tracker changes the evidence quality, not the available geometric dimensions. More points do not by themselves supply missing 3D coordinates.

A table mapping is appropriate only while the tracked geometry satisfies the planar assumptions. Once a prop lifts, using that mapping as if it remained on the table can turn height into false sideways movement. An application may deliberately flatten motion for directing, but it must label that as a control policy rather than physical reconstruction.

### World-space predictions are not automatically metric measurements

A consistent reconstructed coordinate system can still have uncertain scale. Even knowing one physical dimension does not automatically remove local depth deformation or errors in camera/object-motion separation.

SpatialTrackerV2's paper evaluates some depth results after aligning scale and shift to ground truth. Therefore, those benchmark results do not establish out-of-the-box metric depth for arbitrary PocketStage clips. Its reported 5–10 seconds for 100 frames appears in a reconstruction comparison; it is not a measured turnaround promise for our complete multi-object pipeline. [^3]

For genuinely metric object pose, anchor scale using known physical dimensions, a calibrated stereo baseline, or a correctly scaled reference model. Do not fix each frame independently to make an inaccurate result look stable.

## CoTracker3

The released interfaces provide 2D trajectories and visibility, with both offline and chunked processing. The project recommends GPU use. Its online demonstration includes an MPS device route, making a Mac trial reasonable; that is not evidence of acceptable performance on the available 16 GB M4. Much of the repository is under CC-BY-NC terms. [^1][^2]

**Recommended use:** process the saved take, not the live rendering loop. Sample points well inside each reviewed object mask, retain application-owned identities, and evaluate the resulting trajectories against the lightweight baseline. Query points should be distributed across the visible surface rather than clustered near one corner.

Do not automatically trust predictions through occlusion as observations. Keep visibility, residuals, confidence and valid intervals separate. Retrospective tracking can improve recovery after an object reappears without making the hidden motion directly observable.

Begin with one object and a small query set. Measure wall time, maximum memory and coverage before adding the second object. If full-clip memory is excessive, test the released chunked interface on the recorded clip; “post-take” does not require loading an arbitrarily large tensor. Preserve source timestamps when subsampling.

A clean mask and visually smooth tracks are not sufficient acceptance evidence. The test must include fingers entering the selected surface, the object rotating, and another similar object approaching it.

## SpatialTrackerV2

This is the most relevant no-scan 3D experiment because its design jointly estimates geometry, camera motion and point trajectories. The public quick start supports RGB and RGB-D/camera inputs. Its README still marks the online release unfinished even though code references an online checkpoint; certify only a path that actually runs. [^3][^4]

The inference script explicitly uses CUDA. It exports numerical trajectories and related arrays, so it can feed PocketStage rather than merely return an annotated video. Two implementation traps matter: its argument named `fps` is used as a frame-stride operation, and the sample invokes the predictor with `fixed_cam=False`. Neither default should be copied into a fixed-camera, timestamp-sensitive workflow without validation. [^16]

**Recommended use:** a separate candidate reconstruction from the original clip—not an assumed refiner that takes CoTracker's trajectories as its standard input. It can share object masks, queries and timestamps, but its native contract must be respected.

For each object, a robust 3D rigid fit can be attempted between reference and current predicted points. Reject frames where the point set deforms, loses spread, changes identity, or has too few reliable correspondences. This additional fitting is PocketStage engineering, not a ready-made object-pose guarantee from the model.

Keep a distinct label: “inferred 3D, uncalibrated” unless metric validation has passed. A convincing lifted trajectory is useful for previsualization; it is not proof of centimetre accuracy. Do not force its output into the accepted scene until the filmmaker reviews it.

The public code license is CC-BY-NC 4.0. Sponsor API access does not remove restrictions on separately downloaded models. [^17]

## OnePose++ and enrollment-based RGB pose

OnePose++ constructs a semi-dense reference representation and matches query-image evidence to it for object pose estimation. It avoids requiring a supplied CAD mesh, but does not avoid building an object representation. Its custom-data instructions rely on a capture workflow and a reconstruction pipeline. [^5][^6]

The published low-texture dataset used roughly 30-second video sequences and camera-pose information from ARKit, with additional offline optimization. That is evidence of an enrollment procedure, not a guarantee that any casual 30-second turntable clip succeeds. [^18]

For a first enrollment, keep the object stationary and move the camera around it with overlapping, well-lit views. Merely rotating it in front of a fixed camera while using camera poses for the stationary background is not equivalent. The object-relative motion and masks would need separate treatment.

The current environment specification pins Python 3.7, PyTorch 1.8.0 and CUDA 10.1. That increases installation risk on modern GPUs and makes a native M4 port an inappropriate hackathon dependency. The repository's memory note about disabling parallel evaluation below 6 GB is not a complete memory guarantee for reconstruction plus inference. [^7][^5]

**Decision:** retain OnePose++ as the first research experiment for a reusable RGB enrollment representation when no mesh exists. Run supplied data before custom capture. Timebox installation and checkpoint verification; do not spend the full event modernizing the stack. Core code is Apache 2.0, with dependencies/checkpoints reviewed separately. [^19]

Gen6D is a useful comparison, not another required implementation. Its custom workflow explicitly requires a static reference object, COLMAP camera recovery, manual point-cloud cropping and axis definition. This reinforces that CAD-free RGB pose still entails enrollment and coordinate work. [^20]

## More practical routes to restricted, reliable 6-DoF

### Measured everyday objects plus PnP

OpenCV's PnP tools estimate rotation and translation from known 3D points, their image observations, and camera calibration. Planar solvers can produce multiple pose hypotheses; low reprojection error alone is not a guarantee that the selected solution is correct. [^14]

A proposed PocketStage experiment is:

1. Choose a rigid ordinary package or case with distinctive natural texture; measure its dimensions.
2. Calibrate the capture camera's intrinsics and distortion. Four table-corner clicks alone are not an intrinsic calibration.
3. Enroll one or two visible surfaces. Review physical corners and map surface texture points into the corresponding object coordinates.
4. Track those identified surface points across the take, using the passing local or learned tracker.
5. Solve and refine pose with outlier rejection. Compare alternative hypotheses, visible faces, temporal continuity and depth positivity.
6. Export a full rigid pose only while its correspondence and geometry checks pass.

This is not a special dancing-box rig: the object is already an everyday item, with no attached marker. The trade-off is deliberate geometric enrollment and a restricted object profile.

Start with modest movement and continuously visible enrolled faces. A flat cover near fronto-parallel can have unstable tilt; two well-observed nonparallel surfaces are preferable when available. If the correspondence model fails, record a gap rather than generate a plausible orientation.

PnP gives the object's distance and pose, not a dense scene depth map. That distinction is beneficial: PocketStage needs a controller trajectory more urgently than it needs a reconstructed room.

### MegaPose when a matching mesh is available

MegaPose explicitly supports RGB-only inference. Its required inputs include camera intrinsics, an object mesh and an image detection. The documented RGB path is therefore better aligned with the no-LiDAR constraint than forcing guessed depth into FoundationPose. The project describes its main code as Apache 2.0, subject to component exceptions. [^13]

Use a genuine scan or dimensionally correct model of the particular prop. An AI-generated lookalike is not a metrological reference: geometry, scale and appearance mismatch can bias pose. Reserve generative 3D assets for the virtual character unless physical correspondence has been checked.

Mesh preparation and the rendering/inference stack can still dominate setup. For the event, test a few keyframes first, then decide whether complete-frame inference or tracked correspondence between accepted poses meets the turnaround target. The latter is an additional integration step, not a certified feature assumed from the single-image demo.

### Two ordinary RGB cameras

Two calibrated views provide geometric depth from corresponding image points. OpenCV documents triangulation using the camera projection matrices. A known baseline establishes metric scale. [^15]

With two already available phones/webcams, use simultaneous recordings, fixed mounts, calibration, and a visible synchronization event. Track matching physical surface points in both views, triangulate only valid correspondences, and estimate an object transform from several well-spread points.

Three non-collinear, accurately matched 3D points theoretically constrain a rigid transform; practical tracking needs redundancy and quality checks. Mask centres from two different viewpoints generally do not identify the same physical surface point, so triangulating them is not a reliable shortcut.

Post-take processing helps align recordings, but residual offset, clock drift and rolling shutter still matter. Validate synchronization against object speed; an apparently small offset can become a substantial spatial error. If one view fails, stereo depth is unavailable unless another independently validated estimator remains applicable.

This is a stronger observation-based alternative to monocular guessed depth, but adds hardware and calibration work. Do not purchase a stereo/depth camera within the existing compute allowance.

## Apple paths without making LiDAR a dependency

### Native object tracking has changed

Current Apple documentation introduces `trackingObjects` for moving/handheld reference objects on iOS 27, whereas `detectionObjects` is aimed at mostly stationary objects. The new path uses `.referenceobject` assets, not the older `.arobject` scan format. The property is marked beta in the documentation checked here. [^11][^21]

Enrollment requires a faithful USDZ model and Create ML training. Apple warns that training can take a few hours and recommends the heavier extended mode for moving-object tracking. This is a potentially strong native path, but not instant scan-and-track enrollment. Confirm device, SDK and OS availability before committing; do not upgrade a primary device or assume release status from an API page. [^12]

LiDAR is not listed as the prerequisite for that reference-object workflow in the cited instructions. It should not be conflated with the separate scene-depth API. Native tracking still needs tests for similar props, occlusion and small objects.

### Flat natural images and the virtual camera

Apple also documents 6-DoF tracking of known 2D images. A book cover or flat printed package face may be an ordinary-object reference rather than an added fiducial. This is a restricted flat-surface mode; covering the image or turning to an unenrolled side remains a limitation. It requires a phone implementation, so it is an alternative to the Mac PnP spike rather than a free addition. [^22]

For camera directing, ARKit device world tracking already estimates the phone's six-axis motion. A phone can therefore serve directly as the virtual camera controller without recognizing a separate camera prop or using LiDAR scene depth. Align its session frame and time to the actor composition, preserve tracking-loss states, and map its physical motion through an explicit artistic scale. This solves camera movement only, not actor-object pose. [^23]

### LiDAR and RGB-D: considered, not required

ARKit scene depth supplies depth and confidence associated with the image on supported LiDAR devices. A point-cloud sample demonstrates projection into 3D, but hidden surfaces still have no observations. Scene depth is not an object-identity or full rigid-pose API. [^24][^25]

If depth hardware is added later, record synchronized raw depth, confidence, RGB, intrinsics, camera pose and units. Do not substitute an exported static room mesh for moving-object depth. Sensor noise, mixed hand/object pixels and sparse support on small objects still require measurement.

FoundationPose's released demo registers an object using RGB, depth, intrinsics and an initial mask, then tracks using RGB-D. Its model-free path adds reconstruction work. BundleSDF likewise needs an RGB-D sequence; its custom-data release expects masks, and its segmentation wrapper is not completely bundled. Neither belongs on the RGB-only critical path. [^8][^9][^10]

Feeding learned monocular depth to these models is a research experiment, not an equivalent replacement for their validated sensor input. FoundationPose's published license also limits use to noncommercial research/evaluation. [^26]

## Sponsored services

fal documents `fal-ai/depth-anything-video`, including optional raw float32 depth arrays in an NPZ output. That makes a bounded depth experiment possible without a custom worker. However, its schema does not promise metric units or expose a clearly documented metric-model switch. Use raw arrays, not pixel values decoded from the visualization MP4. Verify scaling, frame count and source-time mapping before combining them with tracks. [^27]

A separate video-depth model plus CoTracker is worth comparing, but two independent predictions may disagree geometrically. Test it as an alternate pipeline, not as another mandatory layer after SpatialTrackerV2.

No callable sponsored endpoint for CoTracker3, SpatialTrackerV2, OnePose++ or FoundationPose was established in this review. Verify the actual sponsor catalog before deployment. Do not interpret unlimited fal access as unlimited custom GPU hosting or automatic access to every research repository.

Keep sponsored SAM selection for reviewed object regions. World Labs remains a virtual-set provider, not evidence of physical prop geometry; Tavus is unnecessary to the tracking evaluation. No model jobs were submitted in preparing this assessment.

## Latency and compute experiment

The intended interaction is **record → process → review**, not a delayed scene that pretends to be live. Retain an optional lightweight preview during recording and clearly distinguish it from the refined result.

Proposed acceptance budgets for a 10-second take:

| Measurement | Proposed gate | Interpretation |
|---|---|---|
| Capture completion | Immediate acknowledgement; evidence durable before processing | Model failure cannot lose the take |
| Warm refined-result turnaround | Target 30 seconds; acceptable experiment ceiling 90 seconds | Includes upload, queue, inference, pose fitting and retrieval |
| Cold setup | Report separately; never hide it in a warm benchmark | Includes weights and compilation |
| Initial benchmark size | 50–100 selected frames; retain originals | Increase sampling only after success |
| Tracking sample cadence | Try 10–15 Hz for slow gestures; compare faster motions | Interpolating to 30 fps does not create observations |
| Memory fit | Measure on chosen GPU / M4 | No unverified assumption that a full 300-frame pipeline fits |

These are product gates to test, not published runtime claims for individual models. If every take requires several minutes, keep the model as optional offline analysis rather than the default directing interaction.

One bounded NVIDIA worker can be affordable. Runpod's pricing page lists an RTX 4090 Pod rate of $0.74/hour; it also lists different serverless rates, which must not be confused with the Pod quote. Eight compute hours at $0.74 are $5.92, before ancillary charges. [^28]

Preserve the existing $30 operational ceiling and $10 reserve: at most $12 compute, $3 storage/cleanup, $5 fees/uncertainty, and $10 incident buffer. Use a single worker, an independent expiry mechanism, conservative cost accounting, and no automatic paid fallback. A 24 GB worker is a candidate to benchmark, not a guarantee that every model/resolution fits. Reduce input size or abandon the experiment before increasing cost or scope.

## Minimal proof sequence

Do not install every model or train a new general-purpose tracker. Reuse the same source clips and compare candidates.

**A. Capture and correspondence:** one textured package, one irregular rigid prop and one smooth/symmetric challenge object. Record translation, depth movement, yaw, tilt, hand cover, full occlusion, reappearance and a second similar object. Keep an unambiguous reference clip with pauses at known positions.

**B. Post-take tracking:** compare OpenCV and CoTracker on the same prompts. Promote the learned path only if usable coverage improves without silently following the hand. Preserve the last accepted trajectory.

**C. One 6-DoF proof:** choose a measured rigid prop, review its geometry/correspondences, and test PnP. This establishes whether actual depth and orientation are useful before investing in generic enrollment. An independently observed ruler/angle fixture or second view should validate selected poses; training-fit reprojection error alone is insufficient.

**D. One inference-only 3D comparison:** run SpatialTrackerV2 on that take. Compare lift direction, rotation consistency, object rigidity and camera stability against the constrained reference. Mark scale status and reject unsupported orientations.

**E. Broader enrollment only if necessary:** test OnePose++ supplied data, then one custom reference capture. If a faithful mesh already exists, test MegaPose instead. Do not implement both just to complete a model checklist.

Suggested first-demo accuracy gates, requiring agreement before promotion: median translation error within 2 cm over the declared tabletop workspace, median orientation error within 10 degrees on an asymmetric enrolled object, at least 95% valid coverage during annotated visible movement, and no undetected identity swap on the fixture set. Report p95/worst errors and deliberate occlusion gaps as well. These thresholds are planning proposals, not guaranteed model performance.

A symmetric object may never support a unique orientation. A system that marks that axis unknown is more trustworthy than one that outputs a smooth arbitrary angle.

## Architecture implications and fallbacks

Retain immutable RGB evidence and timestamp indexes. Add optional calibration, enrollment and geometry records without requiring them for the tabletop mode.

Each trajectory should specify producer/checkpoint/configuration, source frames, coordinate frame, scale status, object origin, pose validity, visibility, and whether samples are observed estimates, interpolated, or predictions across hidden intervals. Full pose should use an explicit rotation convention; do not overload the existing yaw field.

Use separate candidate outputs for local tabletop, learned tabletop, inferred 3D, and calibrated 6-DoF. A failed job cannot overwrite the selected take. A refined trajectory should become active only after review. Store enrollment geometry independently from the virtual actor asset.

Fallbacks must respect changed assumptions. If a free-space pose fails while the prop is lifted, the table homography cannot silently replace it as a physical estimate. Offer the earlier accepted take, a gap, an explicitly flattened artistic path, or a planar retake. “OpenCV fallback” is not automatic recovery of missing 3D information.

The recommended hackathon promise is therefore: **record everyday-object motion, review improved tracking, and enable full 6-DoF for a small enrolled set of supported objects.** Freeform no-enrollment 3D remains an experimental mode until validated.

## Source notes

All links below are primary project, implementation, or vendor sources consulted September 14, 2026. Repository branches and beta documentation may change; pin the tested versions during implementation.

[1]: https://github.com/facebookresearch/co-tracker
[2]: https://raw.githubusercontent.com/facebookresearch/co-tracker/main/online_demo.py
[3]: https://arxiv.org/html/2507.12462v1
[4]: https://raw.githubusercontent.com/henry123-boy/SpaTrackerV2/main/README.md
[5]: https://github.com/zju3dv/OnePose_Plus_Plus
[6]: https://github.com/zju3dv/OnePose_Plus_Plus/blob/main/doc/demo.md
[7]: https://raw.githubusercontent.com/zju3dv/OnePose_Plus_Plus/main/environment.yaml
[8]: https://github.com/NVlabs/FoundationPose
[9]: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/run_demo.py
[10]: https://raw.githubusercontent.com/NVlabs/BundleSDF/master/readme.md
[11]: https://developer.apple.com/documentation/visionos/using-a-reference-object-with-arkit-in-ios?changes=_6_7
[12]: https://developer.apple.com/documentation/visionos/implementing-object-tracking-in-your-app?changes=_8_7
[13]: https://github.com/megapose6d/megapose6d
[14]: https://docs.opencv.org/4.13.0/d5/d1f/calib3d_solvePnP.html
[15]: https://docs.opencv.org/doc/doxygen/html/d2/d48/group__d__projection.html
[16]: https://raw.githubusercontent.com/henry123-boy/SpaTrackerV2/main/inference.py
[17]: https://raw.githubusercontent.com/henry123-boy/SpaTrackerV2/main/LICENSE.txt
[18]: https://zju3dv.github.io/onepose_plus_plus/files/supp.pdf
[19]: https://raw.githubusercontent.com/zju3dv/OnePose_Plus_Plus/main/LICENSE
[20]: https://github.com/liuyuan-pal/Gen6D/blob/main/custom_object.md
[21]: https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration/trackingobjects?changes=__2
[22]: https://developer.apple.com/documentation/arkit/arimagetrackingconfiguration?language=objc
[23]: https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration?changes=_2__1&language=objc
[24]: https://developer.apple.com/documentation/arkit/ardepthdata
[25]: https://developer.apple.com/documentation/arkit/displaying-a-point-cloud-using-scene-depth
[26]: https://raw.githubusercontent.com/NVlabs/FoundationPose/main/LICENSE
[27]: https://fal.ai/models/fal-ai/depth-anything-video/api
[28]: https://www.runpod.io/pricing

1. Meta / Oxford. [CoTracker3 repository and license summary][1], research release 2024.
2. Meta. [CoTracker online demo implementation][2], current branch.
3. Xiao et al. [SpatialTrackerV2, arXiv version 1][3], 2025. Timing discussed in its reconstruction comparison; not a PocketStage benchmark.
4. SpatialTrackerV2 authors. [Setup, release checklist and quick start][4].
5. He et al. [OnePose++ repository][5], NeurIPS 2022.
6. OnePose++ authors. [Custom-data demo instructions][6].
7. OnePose++ authors. [Pinned environment][7].
8. NVIDIA. [FoundationPose implementation][8], CVPR 2024.
9. NVIDIA. [FoundationPose model-based demo source][9].
10. NVIDIA. [BundleSDF custom-data instructions][10], CVPR 2023 implementation.
11. Apple. [Using a reference object with ARKit in iOS][11], current documentation.
12. Apple. [Implementing object tracking and Create ML enrollment][12], current documentation.
13. Labbé et al. [MegaPose RGB/RGB-D implementation][13], CoRL 2022.
14. OpenCV. [Perspective-n-Point pose computation][14], version 4.13.
15. OpenCV. [3D projection and triangulation documentation][15].
16. SpatialTrackerV2 authors. [Inference code and numerical export][16].
17. SpatialTrackerV2 authors. [CC-BY-NC 4.0 license][17].
18. He et al. [OnePose++ supplementary material][18], dataset and capture methodology.
19. OnePose++ authors. [Apache 2.0 license][19].
20. Liu et al. [Gen6D custom-object enrollment][20], ECCV 2022 implementation.
21. Apple. [Moving-object tracking property and beta status][21].
22. Apple. [ARImageTrackingConfiguration][22].
23. Apple. [ARWorldTrackingConfiguration and device 6-DoF][23].
24. Apple. [ARDepthData][24].
25. Apple. [Depth point-cloud sample][25].
26. NVIDIA. [FoundationPose license][26].
27. fal. [Depth Anything Video API schema][27].
28. Runpod. [Public GPU pricing][28]; recheck actual resource type and checkout quote.

License observations are implementation due diligence, not legal clearance. Review model weights, submodules, assets and intended hackathon/distribution use separately.

[^1]: Meta / Oxford. [CoTracker3 repository and license summary][1], research release 2024.
[^2]: Meta. [CoTracker online demo implementation][2], current branch.
[^3]: Xiao et al. [SpatialTrackerV2, arXiv version 1][3], 2025. Timing discussed in its reconstruction comparison; not a PocketStage benchmark.
[^4]: SpatialTrackerV2 authors. [Setup, release checklist and quick start][4].
[^5]: He et al. [OnePose++ repository][5], NeurIPS 2022.
[^6]: OnePose++ authors. [Custom-data demo instructions][6].
[^7]: OnePose++ authors. [Pinned environment][7].
[^8]: NVIDIA. [FoundationPose implementation][8], CVPR 2024.
[^9]: NVIDIA. [FoundationPose model-based demo source][9].
[^10]: NVIDIA. [BundleSDF custom-data instructions][10], CVPR 2023 implementation.
[^11]: Apple. [Using a reference object with ARKit in iOS][11], current documentation.
[^12]: Apple. [Implementing object tracking and Create ML enrollment][12], current documentation.
[^13]: Labbé et al. [MegaPose RGB/RGB-D implementation][13], CoRL 2022.
[^14]: OpenCV. [Perspective-n-Point pose computation][14], version 4.13.
[^15]: OpenCV. [3D projection and triangulation documentation][15].
[^16]: SpatialTrackerV2 authors. [Inference code and numerical export][16].
[^17]: SpatialTrackerV2 authors. [CC-BY-NC 4.0 license][17].
[^18]: He et al. [OnePose++ supplementary material][18], dataset and capture methodology.
[^19]: OnePose++ authors. [Apache 2.0 license][19].
[^20]: Liu et al. [Gen6D custom-object enrollment][20], ECCV 2022 implementation.
[^21]: Apple. [Moving-object tracking property and beta status][21].
[^22]: Apple. [ARImageTrackingConfiguration][22].
[^23]: Apple. [ARWorldTrackingConfiguration and device 6-DoF][23].
[^24]: Apple. [ARDepthData][24].
[^25]: Apple. [Depth point-cloud sample][25].
[^26]: NVIDIA. [FoundationPose license][26].
[^27]: fal. [Depth Anything Video API schema][27].
[^28]: Runpod. [Public GPU pricing][28]; recheck actual resource type and checkout quote.
