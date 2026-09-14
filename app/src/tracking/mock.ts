import { blankProject, commitTake, type Role, type Sample, type Track, type Vec2, uid } from '../model';
export const DEMO_DURATION = 8;
export function mockPosition(role: Role, t: number, alternate = false): Vec2 {
  const k = Math.min(1, Math.max(0, t / DEMO_DURATION));
  // Approach, hold, retreat. Actor facing is deliberately independent of movement.
  const beat = k < .35 ? k / .35 : k < .6 ? 1 : 1 - (k - .6) / .4 * .55;
  if (role === 'actor-a') return [-2.7 + 1.5 * beat, -.25 + Math.sin(k * Math.PI) * .35];
  if (role === 'actor-b') return [2.5 - 1.2 * beat, -.3 - Math.sin(k * Math.PI) * .25];
  const angle = (alternate ? .8 - k * 1.1 : -.55 + k * 1.0);
  return [Math.sin(angle) * 5.8, Math.cos(angle) * 5.8];
}
export const mockSample = (role: Role, t: number, alternate = false, position?: Vec2): Sample => ({ t, position: position ?? mockPosition(role, t, alternate), status: 'VALID', yaw: null });
export function mockTrack(role: Role, alternate = false): Track {
  return { id: uid(), role, stageId: 'rehearsal-stage', clockId: 'mock-performance', source: 'mock', samples: Array.from({ length: DEMO_DURATION * 15 + 1 }, (_, i) => mockSample(role, i / 15, alternate)) };
}
export function demoProject() {
  let p = blankProject();
  p = commitTake(p, { id: uid(), name: 'Rehearsal · two actors', kind: 'actors', tracks: [mockTrack('actor-a'), mockTrack('actor-b')], duration: DEMO_DURATION, offset: 0 });
  return commitTake(p, { id: uid(), name: 'Rehearsal · camera 01', kind: 'camera', tracks: [mockTrack('camera')], duration: DEMO_DURATION, offset: 0 });
}
