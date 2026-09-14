import { describe, expect, it } from 'vitest';
import { blankProject, commitTake, parseProject, sampleAt, selectedTake, validateTrack, type Sample, type Track } from './model';
import { demoProject, mockTrack } from './tracking/mock';
import { importCandidate } from './tracking/adapter';

const track = (samples: Sample[]): Track => ({ id: 'track', role: 'actor-a', stageId: 'stage', clockId: 'clock', source: 'cv', samples });
const sample = (t: number, x = 0): Sample => ({ t, position: [x, 0], status: 'VALID', yaw: null });
describe('source-timed playback', () => {
  it('interpolates by timestamps, not frame indices', () => { const t = track([sample(0), sample(.2, 10)]); expect(sampleAt(t, .05).position).toEqual([2.5, 0]); });
  it('never extrapolates before or beyond coverage', () => { const t = track([sample(.1), sample(.2)]); expect(sampleAt(t, 0).position).toBeNull(); expect(sampleAt(t, .21).position).toBeNull(); });
  it('keeps exact final sample available', () => { expect(sampleAt(track([sample(0), sample(.2, 10)]), .2).position).toEqual([10, 0]); });
  it('does not bridge tracking loss in either direction', () => { const t = track([sample(0), { t: .1, position: null, status: 'LOST', yaw: null }, sample(.2)]); for (const time of [.05, .1, .15]) expect(sampleAt(t, time).position).toBeNull(); });
  it('does not bridge a long frame gap', () => { expect(sampleAt(track([sample(0), sample(1, 10)]), .3).position).toBeNull(); });
  it('keeps degraded interpolation visibly degraded', () => { const t = track([sample(0), { ...sample(.1), status: 'DEGRADED' }]); expect(sampleAt(t, .05).status).toBe('DEGRADED'); });
  it('takes the shortest yaw arc and never derives it from velocity', () => { const t = track([{ ...sample(0), yaw: 3 }, { ...sample(.1, -10), yaw: -3 }]); expect(sampleAt(t, .05).yaw).toBeCloseTo(Math.PI); expect(sampleAt(track([sample(0), sample(.1, -10)]), .05).yaw).toBeNull(); });
  it('does not mutate observations', () => { const t = track([sample(0), sample(.1, 10)]), before = JSON.stringify(t); sampleAt(t, .05); expect(JSON.stringify(t)).toBe(before); });
});

describe('immutable composition', () => {
  it('replaces only the camera selection and retains all previous data', () => { const p = demoProject(), before = JSON.stringify(selectedTake(p, 'actors')), oldCamera = p.selectedCamera; const next = commitTake(p, { ...selectedTake(p, 'camera')!, id: 'retake', tracks: [mockTrack('camera', true)] }); expect(JSON.stringify(selectedTake(next, 'actors'))).toBe(before); expect(next.takes.some(t => t.id === oldCamera)).toBe(true); expect(next.selectedCamera).toBe('retake'); expect(p.selectedCamera).toBe(oldCamera); });
  it('records which actor performance the camera was performed against', () => { const p = demoProject(); expect(selectedTake(p, 'camera')?.actorTakeId).toBe(p.selectedActors); });
  it('changing actors clears selected camera, preserving camera history', () => { const p = demoProject(); const next = commitTake(p, { ...selectedTake(p, 'actors')!, id: 'actors-two' }); expect(next.selectedCamera).toBeNull(); expect(next.takes.length).toBe(3); });
  it('rejects cross-stage compositions', () => { const p = demoProject(), t = mockTrack('camera'); t.stageId = 'bumped-camera'; expect(() => commitTake(p, { ...selectedTake(p, 'camera')!, tracks: [t] })).toThrow('Stage mismatch'); });
  it('rejects actors from unrelated clocks', () => { const p = demoProject(), a = mockTrack('actor-a'), b = mockTrack('actor-b'); b.clockId = 'different-source'; expect(() => commitTake(p, { ...selectedTake(p, 'actors')!, tracks: [a, b] })).toThrow('same source'); });
  it('round-trips all trajectories and composition references', () => { const p = demoProject(); expect(parseProject(JSON.parse(JSON.stringify(p)))).toEqual(p); });
  it('rejects invalid project without mutating previous project', () => { const p = demoProject(), before = JSON.stringify(p); expect(() => parseProject({ ...p, schema: 'future' })).toThrow(); expect(JSON.stringify(p)).toBe(before); });
  it('rejects forged selected camera / actor pairing', () => { const p = demoProject(), next = commitTake(p, { ...selectedTake(p, 'actors')!, id: 'other-actors' }); expect(() => parseProject({ ...next, selectedCamera: p.selectedCamera })).toThrow('different actor'); });
  it('rejects bad duration and broken references', () => { const p = demoProject(); expect(() => parseProject({ ...p, selectedCamera: 'missing' })).toThrow(); p.takes[0].duration = 100; expect(() => parseProject(p)).toThrow('duration'); });
  it('requires actors before a camera take', () => { expect(() => commitTake(blankProject(), { ...selectedTake(demoProject(), 'camera')! })).toThrow('requires an actor'); });
});

const candidate = () => ({ schema_version: 1, candidate_id: 'candidate-a', take_id: 'physical-take-01', proxy_sha256: 'proxy-hash', accepted: false, samples: [{ time_s: 0, position_stage: [0, 0], position_status: 'VALID', heading_rad: null }, { time_s: .1, position_stage: null, position_status: 'LOST', heading_rad: null }, { time_s: .2, position_stage: [1, 1], position_status: 'VALID', heading_rad: null }] });
const review = { role: 'actor-a' as const, stageId: 'table-01', sourceWidth: 1, sourceDepth: 1, stageWidth: 12, stageDepth: 12 };
describe('Benton candidate adapter', () => {
  it('maps top-left origin to centered X/Z and keeps evidence', () => { const c = candidate(), t = importCandidate(c, review); expect(t.samples[0].position).toEqual([-6, -6]); expect(t.samples[2].position).toEqual([6, 6]); expect(t.provenance?.original).toEqual(c); expect(t.provenance?.mapping).toEqual(review); expect(c.accepted).toBe(false); expect(t.clockId).toBe(c.take_id); });
  it('preserves gaps rather than holding a valid position', () => { const t = importCandidate(candidate(), review); expect(t.samples[1]).toMatchObject({ t: .1, position: null, status: 'LOST' }); });
  it('does not invent heading or depth', () => { const t = importCandidate(candidate(), review); expect(t.samples.every(s => s.yaw === null)).toBe(true); });
  it('respects explicitly reviewed non-square source extents', () => { const t = importCandidate(candidate(), { ...review, sourceWidth: 2, stageDepth: 8 }); expect(t.samples[2].position).toEqual([0, 4]); });
  it('rejects uncalibrated pixels', () => { const c = candidate(); c.samples.forEach(s => { s.position_stage = null; }); expect(() => importCandidate(c, review)).toThrow('No calibrated'); });
  it('rejects missing stage position marked valid', () => { const c = candidate(); c.samples[0].position_stage = null; expect(() => importCandidate(c, review)).toThrow('missing finite'); });
  it('rejects invalid times, unknown schemas, and zero extents', () => { const c = candidate(); c.samples[2].time_s = .1; expect(() => importCandidate(c, review)).toThrow('increasing'); expect(() => importCandidate({ ...candidate(), schema_version: 2 }, review)).toThrow(); expect(() => importCandidate(candidate(), { ...review, sourceWidth: 0 })).toThrow(); });
  it('rejects non-finite, nonmonotonic and fabricated lost measurements', () => { expect(() => validateTrack(track([sample(0), sample(0)]))).toThrow(); expect(() => validateTrack(track([sample(NaN)]))).toThrow(); expect(() => validateTrack(track([{ ...sample(0), status: 'LOST' }]))).toThrow('Lost positions'); });
});
