import { type Role, type Sample, type Take, type Track, durationOf, uid, validateTrack } from '../model';

/** Future live producers push stage-space observations here; no CV or transport in the recorder. */
export interface MotionFrame {
  schema: 'pocketstage-motion/1'; stageId: string; clockId: string; timeS: number;
  objects: Partial<Record<Role, Omit<Sample, 't'>>>;
}
export class MotionRecorder {
  readonly tracks: Track[];
  private previous = -Infinity;
  constructor(readonly config: { kind: Take['kind']; roles: Role[]; stageId: string; clockId: string; source: Track['source']; sourceStart: number }) {
    this.tracks = config.roles.map(role => ({ id: uid(), role, stageId: config.stageId, clockId: config.clockId, source: config.source, samples: [] }));
  }
  push(frame: MotionFrame) {
    if (frame.schema !== 'pocketstage-motion/1' || frame.stageId !== this.config.stageId || frame.clockId !== this.config.clockId) throw new Error('Motion frame stage or clock changed during capture. Stop and review a new take.');
    if (!Number.isFinite(frame.timeS) || frame.timeS <= this.previous) throw new Error('Motion frames must use strictly increasing source time.');
    const t = frame.timeS - this.config.sourceStart;
    if (t < 0 || t > 10.05) throw new Error('Frame is outside this bounded capture.');
    // Validate all observations before mutating any track. Missing roles are explicit gaps.
    const samples = this.tracks.map(track => {
      const object = frame.objects[track.role];
      const sample: Sample = object ? { ...object, position: object.position ? [...object.position] : null, t } : { t, position: null, status: 'UNAVAILABLE', yaw: null };
      validateTrack({ ...track, samples: [sample] }); return sample;
    });
    this.tracks.forEach((track, i) => track.samples.push(samples[i])); this.previous = frame.timeS;
  }
  finish(name: string, requiredDuration: number): Take {
    if (!this.tracks.every(t => t.samples.length >= 2 && t.samples[0].t <= 1 / 15 && t.samples.at(-1)!.t >= requiredDuration - 1 / 15 - 1e-6 && t.samples.every((s, i) => s.position && ['VALID', 'DEGRADED'].includes(s.status) && (!i || s.t - t.samples[i - 1].t <= .25)))) throw new Error('Incomplete or lost capture. Keep the previous accepted composition.');
    return { id: uid(), name, kind: this.config.kind, tracks: structuredClone(this.tracks), duration: durationOf(this.tracks), offset: 0 };
  }
}
