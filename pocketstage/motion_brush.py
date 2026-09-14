"""Bounded IMG_6374 Motion Brush A/B experiment; never upload source footage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import Request, build_opener

import cv2
import numpy as np

from .cloud import _lock, _save, load_key
from .fal_transport import FalTransport, _https_handler, _NoRedirects, download_artifact

MODEL = 'fal-ai/kling-video/v1.5/pro/image-to-video'
PROMPT = ('A photorealistic live-action medieval fantasy shot. Fixed elevated camera. '
          'Exactly one dark-gold dragon, one red-cloaked knight and one blue-cloaked knight. '
          'The dragon advances, the red knight faces it with sword and shield, and the blue '
          'knight runs across the courtyard. Natural walking and running, realistic weight, '
          'coherent shadows, stable identities. One continuous shot, stationary courtyard, no cuts.')
IDS = ('water-bottle', 'phone', 'moisturizer')
# Reviewed character-center anchors and coarse manual silhouettes in the generated image.
ANCHORS = ((.21, .40), (.585, .52), (.87, .53))
POLYGONS = (
    ((0,.37),(.08,.33),(.16,.31),(.22,.33),(.26,.31),(.37,.33),(.43,.37),(.41,.40),(.31,.38),(.29,.43),(.34,.47),(.29,.48),(.24,.46),(.18,.49),(.14,.48),(.12,.46),(.07,.48),(0,.47)),
    ((.515,.455),(.548,.476),(.565,.456),(.593,.456),(.606,.475),(.625,.48),(.669,.564),(.661,.579),(.63,.58),(.599,.565),(.556,.565),(.548,.584),(.514,.584),(.518,.555),(.514,.533),(.52,.5)),
    ((.86,.468),(.89,.471),(.915,.514),(.947,.554),(.929,.557),(.924,.583),(.894,.59),(.874,.582),(.858,.566),(.833,.571),(.826,.586),(.806,.585),(.805,.57),(.817,.548),(.82,.513),(.846,.488)),
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_paths(tracks, width, height, edited=False):
    query = np.linspace(2., 7., 11)
    result = []
    for index, name in enumerate(IDS):
        samples = tracks['tracks_absolute'][name]['samples']
        selected = [s for s in samples if 2.-1e-6 <= s['time_s'] <= 7.+1e-6]
        times = np.array([s['time_s'] for s in selected])
        if len(times) < 2 or times[0] > 2.001 or times[-1] < 6.999 or np.any(np.diff(times) <= 0) or np.any(np.diff(times) > .1):
            raise ValueError('Missing coverage or time gap')
        if any(s['position_status'] not in ('VALID', 'DEGRADED') or s.get('position_normalized') is None for s in selected):
            raise ValueError('Unreviewable tracking gap')
        xy = np.asarray([s['position_normalized'] for s in selected], dtype=float)
        if xy.shape != (len(times), 2) or not np.isfinite(xy).all():
            raise ValueError('Invalid coordinates')
        path = np.column_stack([np.interp(query, times, xy[:, axis]) for axis in range(2)])
        path = np.asarray(ANCHORS[index]) + .35 * (path-path[0])
        if edited and name == 'moisturizer':
            path[:, 1] += .16 * np.linspace(0, 1, len(query))
        if np.any(path < 0) or np.any(path > 1):
            raise ValueError('Path leaves frame')
        pixels = np.rint(path*np.array([width-1, height-1])).astype(int)
        result.append([{'x':int(x), 'y':int(y)} for x,y in pixels])
    return result


def prepare(tracks_path, image_path, output):
    output = Path(output).resolve()
    tracks = json.loads(Path(tracks_path).read_text())
    im = cv2.imread(str(image_path))
    if im is None: raise ValueError('Unreadable starting image')
    height, width = im.shape[:2]
    paths = {v:compile_paths(tracks,width,height,v=='B') for v in ('A','B')}
    output.mkdir(parents=True,exist_ok=False)
    image_path = Path(shutil.copyfile(image_path,output/'starting-image.png'))
    masks=[]
    for index,polygon in enumerate(POLYGONS):
        mask=np.zeros((height,width),np.uint8)
        cv2.fillPoly(mask,[np.rint(np.asarray(polygon)*[width-1,height-1]).astype(np.int32)],255)
        point=paths['A'][index][0]
        if mask[point['y'],point['x']] != 255: raise ValueError('Anchor outside mask')
        target=output/f'mask-{IDS[index]}.png'
        if not cv2.imwrite(str(target),mask): raise ValueError('Mask write failed')
        masks.append(target)
    common={'model':MODEL,'prompt':PROMPT,'duration':'5','aspect_ratio':'9:16',
            'cfg_scale':.5,'negative_prompt':'camera movement, cuts, identity swap, extra people, animation, split screen, text'}
    for variant in ('A','B'):
        directory=output/variant;directory.mkdir()
        plan={'schema':'pocketstage-motion-brush-experiment/1','variant':variant,
              'settings':common,'image':str(image_path),'masks':[str(p) for p in masks],
              'file_hashes':{str(p):digest(p) for p in [image_path,*masks]},
              'source_tracks':str(Path(tracks_path).resolve()),'source_sha256':digest(tracks_path),
              'source_interval_s':[2,7],'sample_times_s':np.linspace(0,5,11).tolist(),
              'subject_ids':IDS,'trajectories':paths[variant],
              'mapping':{'space':'normalized_source_image_displacements','scale':.35,
                         'anchors':ANCHORS,'placement':'authored_to_reviewed_image','timing':'equal_points_unverified_provider_timing'},
              'edit':None if variant=='A' else {'subject':'moisturizer','ramp_down_normalized':.16},
              'source_video_uploaded':False,'accepted':False,'nominal_price_usd':.5}
        _save(directory/'plan.json',plan)
    return {'status':'PREPARED','directory':str(output),'dimensions':[width,height]}


def start(directory,key,approved=False):
    if not approved: raise ValueError('Explicit approval required')
    directory=Path(directory)
    with _lock(directory):
        state_path=directory/'state.json'
        if state_path.exists(): return json.loads(state_path.read_text())
        plan=json.loads((directory/'plan.json').read_text())
        if plan['settings']['model'] != MODEL: raise ValueError('Unexpected endpoint')
        for path,expected in plan['file_hashes'].items():
            if digest(path) != expected: raise ValueError('Input changed')
        state={'status':'SUBMITTING','request_id':None,'accepted':False,'model':MODEL}
        _save(state_path,state)
        try:
            transport=FalTransport(key=key)
            cache_path=(directory if plan.get('isolated_upload_cache') else directory.parent)/'uploads.json'
            cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
            for path,sha in plan['file_hashes'].items():
                if sha not in cache:
                    cache[sha]=transport.upload(path);_save(cache_path,cache)
            payload={k:v for k,v in plan['settings'].items() if k!='model'}
            payload['image_url']=cache[plan['file_hashes'][plan['image']]]
            payload['dynamic_masks']=[{'mask_url':cache[plan['file_hashes'][p]],'trajectories':t}
                                      for p,t in zip(plan['masks'],plan['trajectories'])]
            _save(directory/'request.json',payload)
            request=Request('https://queue.fal.run/'+MODEL,data=json.dumps(payload).encode(),method='POST',
                            headers={'Authorization':'Key '+key,'Content-Type':'application/json'})
            with build_opener(_https_handler(),_NoRedirects()).open(request,timeout=30) as response:
                result=json.loads(response.read(1024*1024))
            if not isinstance(result.get('request_id'),str): raise ValueError('No request ID')
            state.update(status='QUEUED',request_id=result['request_id'])
        except Exception as exc:
            state.update(status='NEEDS_RECONCILIATION',error=type(exc).__name__)
        _save(state_path,state);return state


def poll(directory,key):
    directory=Path(directory)
    with _lock(directory):
        path=directory/'state.json';state=json.loads(path.read_text())
        if not state.get('request_id') or state['status']=='REVIEW_READY': return state
        try:
            transport=FalTransport(key=key)
            state['status']=transport.status(MODEL,state['request_id'])
            if state['status']=='COMPLETED':
                result=transport.result(MODEL,state['request_id'])
                target=directory/'generated-video.mp4'
                if not target.exists(): download_artifact(result['video']['url'],target)
                from .media import probe_video
                metadata=probe_video(target)
                state.update(status='REVIEW_READY',artifact=str(target),
                             media={k:metadata[k] for k in ('width','height','frame_count','codec')})
        except Exception as exc:
            state.update(status='FETCH_OR_INSPECTION_FAILED',error=type(exc).__name__)
        _save(path,state);return state


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','start','poll'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--image',type=Path);p.add_argument('--tracks',type=Path)
    p.add_argument('--approve-generation',action='store_true');args=p.parse_args()
    if args.action=='prepare': result=prepare(args.tracks,args.image,args.out)
    else:
        key=load_key(Path(__file__).resolve().parents[1]/'.env')
        if not key: raise ValueError('Configure FAL_KEY in local .env')
        result=start(args.out,key,args.approve_generation) if args.action=='start' else poll(args.out,key)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
