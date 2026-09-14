import { describe, expect, it } from 'vitest';
import { MotionRecorder, type MotionFrame } from './recorder';
const recorder = () => new MotionRecorder({ kind: 'actors', roles: ['actor-a', 'actor-b'], stageId: 'stage', clockId: 'camera-clock', source: 'cv', sourceStart: 100 });
const frame = (t: number): MotionFrame => ({ schema: 'pocketstage-motion/1', stageId: 'stage', clockId: 'camera-clock', timeS: 100 + t, objects: { 'actor-a': { position: [1, 2], status: 'VALID', yaw: null }, 'actor-b': { position: [3, 2], status: 'VALID', yaw: null } } });
describe('source-agnostic bounded recorder', () => {
  it('records source clock relative to a shared capture origin', () => { const r = recorder(); r.push(frame(0)); r.push(frame(.1)); expect(r.tracks[0].samples[1].t).toBeCloseTo(.1); expect(r.tracks[1].samples[1].t).toBeCloseTo(.1); });
  it('rejects clock changes and nonmonotonic delivery', () => { const r = recorder(); r.push(frame(.1)); expect(() => r.push(frame(0))).toThrow('increasing'); expect(() => r.push({ ...frame(.2), clockId: 'new-clock' })).toThrow('clock'); expect(r.tracks[0].samples.length).toBe(1); });
  it('rejects stage changes', () => { expect(() => recorder().push({ ...frame(0), stageId: 'bumped' })).toThrow('stage'); });
  it('keeps missing roles as unavailable observations', () => { const r = recorder(), f = frame(0); delete f.objects['actor-b']; r.push(f); expect(r.tracks[1].samples[0].position).toBeNull(); });
  it('does not partially append a malformed multi-object frame', () => { const r = recorder(), f = frame(0); f.objects['actor-b']!.position = [NaN, 0]; expect(() => r.push(f)).toThrow(); expect(r.tracks[0].samples).toHaveLength(0); });
  it('refuses short, missing, and gapped takes', () => { const r = recorder(); r.push(frame(0)); r.push(frame(.1)); expect(() => r.finish('short', 8)).toThrow('Incomplete'); r.push(frame(8)); expect(() => r.finish('gapped', 8)).toThrow('Incomplete'); });
  it('finalizes a detached take snapshot', () => { const r = recorder(); for (let i = 0; i <= 120; i++) r.push(frame(i / 15)); const take = r.finish('complete', 8); expect(take.duration).toBe(8); r.tracks[0].samples[0].position![0] = 99; expect(take.tracks[0].samples[0].position![0]).toBe(1); });
  it('does not fabricate measurements from lost states', () => { const r = recorder(), f = frame(0); f.objects['actor-a'] = { position: null, status: 'LOST', yaw: null }; r.push(f); r.push(frame(.1)); expect(() => r.finish('lost', .1)).toThrow(); });
});
