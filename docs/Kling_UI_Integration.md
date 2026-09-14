# Capture Studio → Kling Motion Brush

After SAM/depth analysis completes, the result page offers a real Kling generation panel.

1. Upload a clean PNG/JPEG starting image (300–3840 pixels per side, at most 9 MP and under 10 MB).
2. Select an extracted object ID and drag a rectangle around its corresponding character. Repeat for up to six subjects; unbound tracks are not sent.
3. Select a fully observed five-second source interval and motion scale. Each character-region center is the starting anchor. Its displacement comes from that object's absolute normalized coordinates, not coordinates relative to the reference object.
4. Enter a scene prompt, review the tracks/regions, and explicitly approve a paid or sponsored generation.
5. The backend uploads only the clean image and rectangular masks, submits dynamic_masks with eleven coordinate points per subject to fal-ai/kling-video/v1.5/pro/image-to-video, and exposes persisted status and a local generated-video URL.

FAL_KEY stays in the repository .env/backend environment. The cloud extra includes Pillow for bounded image-header inspection. No dependencies were installed during this integration.

POST /api/jobs/{analysis_id}/generations creates an explicit request ID with input fingerprinting. Reusing that ID does not submit again; mismatched inputs are rejected. GET /api/jobs/{analysis_id}/generations/{generation_id} polls/retrieves only. /video serves the result. Each generation is saved under the analysis job's generations directory. No fixed IMG_6374 paths, image anchors or three-object names are used by the UI compiler.

Tracking gaps and out-of-frame trajectory anchors fail closed. Rectangles are coarse manual character masks; there is no automatic character-image segmentation. Source segmentation remains the existing SAM pipeline. Exact timing, body articulation, 3D, depth control and faithful path adherence are not guaranteed. A completed result remains unaccepted pending user review.

Validation: tests, builds and live paid submissions were intentionally not run for this integration, at the user's request. The prior standalone Motion Brush experiment is not evidence that this UI integration has been tested end to end.
