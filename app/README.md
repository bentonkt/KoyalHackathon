# PocketStage Capture Studio and Director's Desk

The browser now covers video import, first-frame object selection, real SAM 2 + Depth Anything processing, generated-video review, and the downstream Director's Desk.

Model credentials and hosted calls stay in the loopback-only Python service. The browser sends the selected clip to that local service only after per-run consent; the service creates the canonical proxy, uploads it once to fal.ai, runs one SAM 2 pass per object plus one shared Depth Anything pass, validates the artifacts, and returns the rendered motion preview and tracks.

## Run locally

Requires Node.js 20 or newer, the repository `.venv`, FFmpeg, and `FAL_KEY` in the ignored root `.env`.

```bash
cd app
npm install
npm run dev
```

`npm run dev` starts both the loopback processing API on port 8765 and Vite on port 5173. Open the local URL printed by Vite. The complete production and test checks are:

```bash
npm test
npm run build
```

## 60-second demo path

1. Start on **Shot** view and play the included mock composition once.
2. Click **Record actors**. Move the pencil case and small box on the tabletop; until live CV is connected, use **Drag to rehearse** or the explicit scripted mock.
3. Click **Record camera**. The actor take replays from scene time zero while a stapler controls only the virtual camera.
4. Click **Watch your shot**, then toggle **Stage** to reveal the physical blocking translated into the virtual set.
5. Import a real candidate to replace a mock role. Optionally attach the canonical `proxy.mp4`; the app verifies its SHA-256 before showing it beside playback.

The magic moment is step 3: the filmmaker moves only the camera object while the previously performed actors replay, creating a new shot without redoing the blocking.

## Current Python candidate integration

Use Benton's CLI with `--corners`, then open **Import real CV trajectory** and select the emitted `projects/<project>/candidates/<candidate-id>.json`.

Required candidate fields:

```json
{
  "schema_version": 1,
  "candidate_id": "uuid",
  "take_id": "uuid-shared-by-simultaneous-actor-tracks",
  "proxy_sha256": "hex digest",
  "samples": [
    {
      "time_s": 0.0,
      "position_stage": [0.25, 0.7],
      "position_status": "VALID",
      "heading_rad": null
    }
  ]
}
```

The adapter treats Python's `position_stage` as a reviewed top-left-origin `(u, v)` ground plane and maps it to centered Three.js `(X, Z)` on a right-handed, Y-up stage. The current Python geometry defaults to a 1 × 1 virtual plane. The review dialog asks for these source extents because schema v1 does not record them. This review is mandatory; matching corner numbers do not prove that two recordings used an unchanged physical setup.

The same dialog also accepts the current `motion-demo` output, `motion-tracks.json`. Choose one named source object, assign its virtual role, and review an artistic scale and origin. The adapter maps `position_relative` image offsets to X/Z while labeling every present sample `DEGRADED`; gaps remain lost. It preserves the complete export, including raw depth differences, as provenance but does not apply depth to height. Import multiple objects from the same export to give them a shared performance clock.

Import Actor A and Actor B candidates with the same `take_id` to compose one simultaneous performance. Import Camera from its separate take after selecting that actor performance. Camera offset is saved explicitly. Retakes create new versions; they never overwrite earlier accepted data.

Rules enforced at the boundary:

- Source timestamps must be finite and strictly increasing. Renderer FPS is never used as the recording clock.
- `VALID` and `DEGRADED` require finite stage positions.
- `LOST` and `UNAVAILABLE` require null positions. The renderer does not interpolate over them or over gaps longer than 250 ms.
- Actor tracks in one performance must share a clock/take ID, canonical proxy hash, and stage identity.
- A camera pass stores the exact actor-take ID it was performed against.
- Heading stays null unless measured. Actor facing is an independent fixed/look-at policy; retreating does not turn an actor around.
- Pixel-only candidates are rejected. Apparent scale is never promoted to height or depth.

## Live frame contract for the next integration

`src/recording/recorder.ts` is the clean live boundary. A transport owned by Benton's process can later send frames shaped like:

```json
{
  "schema": "pocketstage-motion/1",
  "stageId": "reviewed-calibration-version-id",
  "clockId": "capture-clock-id",
  "timeS": 1042.233,
  "objects": {
    "actor-a": { "position": [-2.1, 0.3], "status": "VALID", "yaw": null },
    "actor-b": { "position": [1.8, 0.1], "status": "DEGRADED", "yaw": null }
  }
}
```

The sender must provide stage-space positions and one authoritative monotonic source clock. Missing roles become explicit `UNAVAILABLE` observations. A stage or clock change fails the current recording closed. This contract is transport-agnostic: local WebSocket, server-sent events, or direct in-process delivery can be added without changing renderer or project records.

## What is intentionally not built

- webcam capture, metric calibration, or fal credentials in the browser
- automatic identity reassignment, yaw-from-velocity, elevation-from-scale, or silent gap filling
- generated environments, skeletal animation, physics, collision, or generic plugin infrastructure
- server/database/auth/deployment machinery

The built-in set, stylized stand-ins, local JSON save/reopen, PNG frame export, scrubber, and versioned take library are the reliable offline demo path.
