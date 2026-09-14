"""Fast, offline motion-demo export from completed model runs."""

import csv
import hashlib
import json
from pathlib import Path

from .artifacts import extract_reviewed_sam_masks
from .media import atomic_write_json
from .motion import motion_from_masks
from .preview import render_motion_preview
from .providers import load_raw_depths
from .relative import attach_relative_depth, relative_scene


def reviewed_start_frame(job, prompts, frame_count):
    """A documented review may withhold an ambiguous prefix, never invent frames."""
    prompt_start=min(p['frame_index'] for p in prompts if p['label']==1)
    review=job.get('mask_review',{}).get('valid_from_frame',prompt_start)
    if type(review) is not int or not 0 <= review < frame_count:
        raise ValueError('Invalid reviewed mask start frame')
    return prompt_start,max(prompt_start,review)


def build_motion_demo(object_runs, reference_id, static_ids, output, *, reviewed_masks=False):
    if not reviewed_masks:
        raise ValueError('Review each SAM binary-mask output before using --reviewed-masks')
    if not object_runs or reference_id not in object_runs:
        raise ValueError('Provide object runs including the reference object')
    if len(object_runs)>8:
        raise ValueError('Demo supports at most eight named objects')
    if any(not isinstance(name,str) or not name or len(name)>24 for name in object_runs):
        raise ValueError('Object IDs must be nonempty labels at most 24 characters')
    out=Path(output)
    if out.exists():
        raise FileExistsError('Choose a new output directory to preserve earlier demo exports')
    tracks={}
    common=None
    depth_cache={}
    provenance={}
    source_path=None
    for object_id,directory in object_runs.items():
        directory=Path(directory).resolve()
        state=json.loads((directory/'state.json').read_text())
        proxy=state['configuration']['proxy']
        identity=(proxy['sha256'],proxy['frame_count'],proxy['height'],proxy['width'],proxy['fps'])
        if common is not None and identity!=common:
            raise ValueError('All objects must use the exact same canonical clip and clock')
        common=identity
        source=(directory.parent.parent/proxy['path']).resolve()
        if not source.is_relative_to(directory.parent.parent):
            raise ValueError('Source proxy escapes its project')
        if source_path is None:
            if hashlib.sha256(source.read_bytes()).hexdigest()!=proxy['sha256']:
                raise ValueError('Source proxy hash mismatch')
            source_path=source
        job=state['jobs']['sam2']
        if job.get('status')!='REVIEW_READY':
            raise ValueError(f'SAM output for {object_id} is not ready')
        prompts=state['configuration']['jobs']['sam2']['input']['prompts']
        prompt_start,start=reviewed_start_frame(job,prompts,proxy['frame_count'])
        shape=(proxy['frame_count'],proxy['height'],proxy['width'])
        masks=extract_reviewed_sam_masks(Path(job['artifact']),shape,proxy['fps'],
                                        start_frame=start,reviewed_binary_video=True)
        track=motion_from_masks(masks['masks'],masks['available'],proxy['timestamps'])
        depth_job=state['jobs'].get('depth',{})
        if depth_job.get('status')=='REVIEW_READY' and depth_job.get('artifact'):
            depth_path=Path(depth_job['artifact']).resolve()
            if depth_path not in depth_cache:
                depth_cache[depth_path]=load_raw_depths(depth_path,shape,proxy['fps'])
            track=attach_relative_depth(track,depth_cache[depth_path],masks['masks'],masks['available'])
        tracks[object_id]=track
        provenance[object_id]={'sam_request_id':job['request_id'],'prompt_frame':prompt_start,
                               'mask_valid_from_frame':start,'mask_review':job.get('mask_review'),
                               'run_id':state['run_id'],'mask_profile':masks['metadata']}
    scene=relative_scene(tracks,reference_id,static_ids=static_ids)
    scene.update(schema_version=1,object_ids=list(tracks),source_dimensions=[common[3],common[2]],
                 proxy_sha256=common[0],fps=common[4],object_provenance=provenance,
                 capability='approximate_mask_centroid_demo',accepted=False)
    out.mkdir(parents=True,exist_ok=False)
    atomic_write_json(out/'motion-tracks.json',scene)
    with (out/'motion-tracks.csv').open('x',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['frame','time_s','object_id','reference_id','x_relative','y_relative','depth_difference_raw','status','role'])
        for index,sample in enumerate(scene['samples']):
            for object_id,obj in sample['objects'].items():
                xy=obj['position_relative'] or [None,None]
                writer.writerow([index,sample['time_s'],object_id,reference_id,*xy,obj['depth_difference_raw'],obj['status'],obj['role']])
    preview=render_motion_preview(source_path,scene,out/'motion-preview.mp4')
    summary={'object_ids':list(tracks),'reference_id':reference_id,'static_ids':list(static_ids),
             'frame_count':len(scene['samples']),'fps':common[4],
             'relative_position_frames':{name:sum(s['objects'][name]['position_relative'] is not None for s in scene['samples']) for name in tracks},
             'mask_motion_frames':{name:sum(s['position_status']=='VALID' for s in tracks[name]['samples']) for name in tracks},
             'gaps_are_not_interpolated':True,'units':'normalized_image_not_metres',
             'depth':'raw_model_difference_not_metric_distance',
             'identity_accuracy_certified':False,'preview':preview,'tracks':str(out/'motion-tracks.json')}
    atomic_write_json(out/'summary.json',summary)
    return summary
