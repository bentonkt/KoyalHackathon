// Renderer-facing trajectories. No pixels, masks, providers, or CV logic here.
export const ROLES = ['actor-a', 'actor-b', 'camera'] as const;
export type Role = typeof ROLES[number];
export type Vec2 = [number, number];
export type Status = 'VALID' | 'DEGRADED' | 'LOST' | 'UNAVAILABLE';
export type Heading = 'fixed' | 'look-at';
export interface Sample { t: number; position: Vec2 | null; status: Status; yaw: number | null }
export interface Track {
  id: string; role: Role; stageId: string; clockId: string; source: 'mock' | 'cv';
  samples: Sample[]; provenance?: { candidateId: string; takeId: string; proxySha256: string; original: unknown; mapping?: unknown };
}
export interface Take { id: string; name: string; kind: 'actors' | 'camera'; tracks: Track[]; duration: number; offset: number; actorTakeId?: string }
export interface Project {
  schema: 'pocketstage-director/1'; stage: { id: string; width: number; depth: number };
  takes: Take[]; selectedActors: string | null; selectedCamera: string | null;
  heading: Heading; camera: { height: number; fov: number; target: 'midpoint' | 'actor-a' | 'actor-b' };
}
export const uid = () => crypto.randomUUID();
export const durationOf = (tracks: Track[]) => Math.max(0, ...tracks.map(t => t.samples.at(-1)?.t ?? 0));
export const selectedTake = (p: Project, kind: Take['kind']) => p.takes.find(t => t.id === (kind === 'actors' ? p.selectedActors : p.selectedCamera));

/** No extrapolation, no interpolation over loss or gaps; raw samples are never changed. */
export function sampleAt(track: Track | undefined, t: number): Sample {
  const missing: Sample = { t, position: null, status: 'UNAVAILABLE', yaw: null };
  if (!track || !track.samples.length || t < track.samples[0].t || t > track.samples.at(-1)!.t + 1e-6) return missing;
  const s = track.samples;
  let lo = 0, hi = s.length - 1;
  while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (s[mid].t <= t) lo = mid; else hi = mid - 1; }
  const a = s[lo], b = s[lo + 1];
  if (Math.abs(t - a.t) < 1e-6 || !b) return { ...a, t };
  if (!a.position || !b.position || !['VALID', 'DEGRADED'].includes(a.status) || !['VALID', 'DEGRADED'].includes(b.status) || b.t - a.t > 0.25) return missing;
  const k = (t - a.t) / (b.t - a.t);
  const dy = a.yaw !== null && b.yaw !== null ? Math.atan2(Math.sin(b.yaw - a.yaw), Math.cos(b.yaw - a.yaw)) : null;
  return { t, position: [a.position[0] + (b.position[0] - a.position[0]) * k, a.position[1] + (b.position[1] - a.position[1]) * k], status: a.status === 'DEGRADED' || b.status === 'DEGRADED' ? 'DEGRADED' : 'VALID', yaw: dy === null ? null : a.yaw! + dy * k };
}

export function commitTake(p: Project, take: Take): Project {
  if (!take.tracks.length || take.tracks.some(t => t.stageId !== p.stage.id)) throw new Error('Stage mismatch. Review the physical stage before combining takes.');
  if (take.kind === 'actors' && new Set(take.tracks.map(t => t.clockId)).size !== 1) throw new Error('Actor candidates must come from the same source take / clock.');
  if (take.kind === 'camera') {
    if (!p.selectedActors) throw new Error('A camera pass requires an actor performance.');
    take = { ...take, actorTakeId: p.selectedActors };
  }
  // Every accepted take is a new version. Replacing actors invalidates only the camera selection, never its data.
  return { ...p, takes: [...p.takes, take], ...(take.kind === 'actors' ? { selectedActors: take.id, selectedCamera: null } : { selectedCamera: take.id }) };
}

export function blankProject(stageId = 'rehearsal-stage'): Project {
  return { schema: 'pocketstage-director/1', stage: { id: stageId, width: 12, depth: 12 }, takes: [], selectedActors: null, selectedCamera: null, heading: 'look-at', camera: { height: 2.2, fov: 48, target: 'midpoint' } };
}

export function validateTrack(x: unknown): asserts x is Track {
  const t = x as Track;
  if (!t || !ROLES.includes(t.role) || !t.id || !t.stageId || !t.clockId || !['mock', 'cv'].includes(t.source) || !Array.isArray(t.samples) || !t.samples.length || t.samples.length > 10000) throw new Error('Invalid trajectory header or sample count.');
  let previous = -1;
  for (const s of t.samples) {
    if (!Number.isFinite(s.t) || s.t < 0 || s.t <= previous || s.t > 600 || !['VALID', 'DEGRADED', 'LOST', 'UNAVAILABLE'].includes(s.status)) throw new Error('Samples require finite, strictly increasing source times and valid status.');
    if (s.yaw !== null && !Number.isFinite(s.yaw)) throw new Error('Invalid heading.');
    if (s.position !== null && (!Array.isArray(s.position) || s.position.length !== 2 || !s.position.every(v => Number.isFinite(v) && Math.abs(v) <= 1000))) throw new Error('Invalid stage position.');
    if (['VALID', 'DEGRADED'].includes(s.status) && !s.position) throw new Error('Valid samples require a stage position.');
    if (['LOST', 'UNAVAILABLE'].includes(s.status) && s.position !== null) throw new Error('Lost positions must be null, not held measurements.');
    previous = s.t;
  }
}

export function parseProject(value: unknown): Project {
  const p = value as Project;
  if (!p || p.schema !== 'pocketstage-director/1' || !p.stage?.id || !Number.isFinite(p.stage.width) || !Number.isFinite(p.stage.depth) || p.stage.width <= 0 || p.stage.width > 100 || p.stage.depth <= 0 || p.stage.depth > 100 || !Array.isArray(p.takes) || p.takes.length > 100) throw new Error('Unsupported or invalid PocketStage project.');
  if (!['fixed', 'look-at'].includes(p.heading) || !p.camera || !['midpoint', 'actor-a', 'actor-b'].includes(p.camera.target) || !Number.isFinite(p.camera.height) || p.camera.height < 0.5 || p.camera.height > 6 || !Number.isFinite(p.camera.fov) || p.camera.fov < 25 || p.camera.fov > 80) throw new Error('Invalid camera or heading settings.');
  const ids = new Set<string>();
  for (const take of p.takes) {
    if (!take.id || ids.has(take.id) || typeof take.name !== 'string' || !['actors', 'camera'].includes(take.kind) || !Number.isFinite(take.duration) || take.duration <= 0 || take.duration > 600 || !Number.isFinite(take.offset) || Math.abs(take.offset) > 600 || !Array.isArray(take.tracks) || take.tracks.length < 1 || take.tracks.length > 2) throw new Error('Invalid take.');
    ids.add(take.id);
    take.tracks.forEach(validateTrack);
    if (take.tracks.some(t => t.stageId !== p.stage.id || (take.kind === 'camera' ? t.role !== 'camera' : t.role === 'camera')) || new Set(take.tracks.map(t => t.role)).size !== take.tracks.length || (take.kind === 'actors' && new Set(take.tracks.map(t => t.clockId)).size !== 1)) throw new Error('Incompatible take tracks.');
    if (Math.abs(take.duration - durationOf(take.tracks)) > 1e-5) throw new Error('Take duration must match source coverage.');
  }
  for (const kind of ['actors', 'camera'] as const) {
    const id = kind === 'actors' ? p.selectedActors : p.selectedCamera;
    if (id !== null && !p.takes.some(t => t.id === id && t.kind === kind)) throw new Error('Broken composition reference.');
  }
  for (const take of p.takes.filter(t => t.kind === 'camera')) {
    if (!p.takes.some(a => a.id === take.actorTakeId && a.kind === 'actors')) throw new Error('Camera take has no referenced actor performance.');
  }
  if (p.selectedCamera && !p.selectedActors) throw new Error('A camera pass requires an actor performance.');
  if (selectedTake(p, 'camera') && selectedTake(p, 'camera')!.actorTakeId !== p.selectedActors) throw new Error('Selected camera belongs to a different actor performance.');
  return structuredClone(p);
}
