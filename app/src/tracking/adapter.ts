import { type Role, type Track, type Status, uid, validateTrack } from '../model';

export interface CandidateReview { role: Role; stageId: string; sourceWidth: number; sourceDepth: number; stageWidth: number; stageDepth: number }
export interface RelativeReview { role: Role; objectId: string; stageId: string; scale: number; origin: [number, number] }

export function relativeObjectIds(value: unknown): string[] {
  const r = value as Record<string, unknown>;
  if (!r || r.schema_version !== 1 || r.capability !== 'approximate_mask_centroid_demo' || !Array.isArray(r.object_ids) || !Array.isArray(r.samples) || r.samples.length < 1 || r.samples.length > 10000) return [];
  const ids = r.object_ids;
  if (!ids.every((id): id is string => typeof id === 'string' && id.length > 0 && id.length <= 24) || new Set(ids).size !== ids.length) return [];
  return ids;
}

/** Adapt Benton's multi-object motion demo through a reviewed artistic mapping.
 * These normalized image offsets are DEGRADED controls, never stage measurements.
 */
export function importRelativeMotion(value: unknown, review: RelativeReview): Track {
  const r = value as Record<string, unknown>, ids = relativeObjectIds(value);
  if (!ids.includes(review.objectId) || typeof r.proxy_sha256 !== 'string' || !r.proxy_sha256 || typeof r.reference_id !== 'string' || !ids.includes(r.reference_id) || r.semantics !== 'normalized_screen_plane_relative_to_measured_reference_not_3d_or_metres' || r.identity_certified !== false) throw new Error('Expected a PocketStage approximate multi-object motion export.');
  if (!review.stageId.trim() || !Number.isFinite(review.scale) || review.scale <= 0 || review.scale > 100 || review.origin.length !== 2 || !review.origin.every(Number.isFinite)) throw new Error('Review a finite artistic motion scale, origin, and stage ID.');
  const samples = r.samples as Array<Record<string, unknown>>;
  const track: Track = {
    id: uid(), role: review.role, stageId: review.stageId.trim(), clockId: `relative:${r.proxy_sha256}`, source: 'cv',
    provenance: { candidateId: `relative:${review.objectId}`, takeId: `relative:${r.proxy_sha256}`, proxySha256: r.proxy_sha256, original: structuredClone(value), mapping: { ...review, semantics: 'artistic_relative_screen_plane_to_stage' } },
    samples: samples.map(frame => {
      const objects = frame.objects as Record<string, Record<string, unknown>> | undefined;
      const object = objects?.[review.objectId];
      const xy = object?.position_relative;
      const present = Array.isArray(xy) && xy.length === 2 && xy.every(Number.isFinite);
      if ((present && object?.status !== 'RELATIVE_UNVALIDATED_IDENTITY') || (!present && object?.status !== 'REFERENCE_OR_OBJECT_GAP')) throw new Error('Relative motion status and position disagree.');
      return { t: frame.time_s as number, position: present ? [review.origin[0] + (xy[0] as number) * review.scale, review.origin[1] + (xy[1] as number) * review.scale] as [number, number] : null, status: present ? 'DEGRADED' : 'LOST', yaw: null };
    }),
  };
  validateTrack(track);
  return track;
}

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
