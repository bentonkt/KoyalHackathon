import { type Role, type Track, type Status, uid, validateTrack } from '../model';

export interface CandidateReview { role: Role; stageId: string; sourceWidth: number; sourceDepth: number; stageWidth: number; stageDepth: number }

/** Adapt Benton's schema v1 candidates, preserving original evidence and gaps.
 * The user explicitly reviews stage identity and source rectangle extents:
 * the current Python JSON does not contain these calibration identity/size fields.
 */
export function importCandidate(value: unknown, review: CandidateReview): Track {
  const c = value as Record<string, unknown>;
  if (!c || c.schema_version !== 1 || !Array.isArray(c.samples) || !c.samples.length || typeof c.candidate_id !== 'string' || typeof c.take_id !== 'string' || typeof c.proxy_sha256 !== 'string') throw new Error('Expected a schema_version: 1 CV candidate JSON, not a manifest or provider response.');
  if (!review.stageId.trim() || ![review.sourceWidth, review.sourceDepth, review.stageWidth, review.stageDepth].every(n => Number.isFinite(n) && n > 0 && n <= 1000)) throw new Error('Review the stage ID and positive coordinate extents.');
  if (!c.samples.some((s: Record<string, unknown>) => Array.isArray(s.position_stage))) throw new Error('No calibrated position_stage data. Benton must export tracking with --corners; pixel positions are not stage coordinates.');
  const track: Track = {
    id: uid(), role: review.role, stageId: review.stageId.trim(), clockId: c.take_id, source: 'cv',
    provenance: { candidateId: c.candidate_id, takeId: c.take_id, proxySha256: c.proxy_sha256, original: structuredClone(value), mapping: { ...review } },
    samples: c.samples.map((raw: Record<string, unknown>) => {
      const status = raw.position_status as Status;
      const valid = status === 'VALID' || status === 'DEGRADED';
      const pos = raw.position_stage as number[] | null;
      if (valid && (!Array.isArray(pos) || pos.length !== 2 || !pos.every(Number.isFinite))) throw new Error('A valid CV observation is missing finite position_stage coordinates.');
      // u right, v down in CV plane -> X right, Z down in right-handed Y-up stage.
      // Camera height is explicit; apparent object scale is never treated as depth.
      return { t: raw.time_s as number, position: valid ? [(pos![0] / review.sourceWidth - 0.5) * review.stageWidth, (pos![1] / review.sourceDepth - 0.5) * review.stageDepth] as [number, number] : null, status, yaw: null };
    }),
  };
  validateTrack(track);
  return track;
}
