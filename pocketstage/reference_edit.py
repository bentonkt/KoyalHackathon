"""Bounded Kling O3 reference-edit experiment; never automatically resubmit."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from urllib.request import Request, build_opener

from .cloud import load_key, _save, _lock
from .fal_transport import FalTransport, _https_handler, _NoRedirects, download_artifact

MODEL='fal-ai/kling-video/o3/pro/video-to-video/edit'
PROMPT=('Transform @Video1 into one photorealistic live-action medieval dark-fantasy battle shot, '
 'with the grounded cinematic realism of Game of Thrones. Use the source video as the exact camera and blocking reference. '
 'Keep its elevated oblique camera angle, portrait composition, continuous timing and motion paths. '
 'There are exactly TWO adult human knights and ONE dragon. The dark WATER BOTTLE moving in from the left '
 'becomes a realistic large dark-gold scaled dragon, moving along that bottle path. The upright PHONE near '
 'the center-right becomes the brave knight in weathered steel armor and a dark red cloak, holding a sword and shield. '
 'The small white MOISTURIZER bottle farther right becomes a second knight in steel armor and a blue cloak. '
 'This blue-cloaked knight runs away to the right following the moisturizer motion. '
 'The red-cloaked hero stays and fights the approaching dragon. In the final third, the hero drives his sword '
 'into the dragon while the dragon strikes the hero with a fatal claw blow. Both the dragon and red-cloaked hero '
 'collapse and remain dead at the end; the fleeing knight survives. Non-graphic action, no gore or dismemberment. '
 'Replace the entire modern setting with a weathered medieval stone castle courtyard, retaining its perspective. '
 'Remove the real people, manipulating hands, table, phones, bottles, railing and modern architecture completely. '
 'The source people are puppeteers, NOT characters to retain. Only the three specified props become characters. '
 'Natural skin, realistic adult anatomy, physically plausible dragon scales and wings, worn chainmail, muted natural '
 'daylight and coherent shadows. A photographed live-action scene, NOT animation, illustration, toy miniatures or a video game. '
 'One full-frame shot, no split screen, no panels, no graphs, no labels, no extra people, no cuts, no camera zoom or reframing.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(repo, output):
    repo,output=Path(repo).resolve(),Path(output).resolve()
    source=repo/'artifacts/IMG_6374_sam_depth/IMG_6374_motion_preview.mp4'
    tracks_path=source.parent/'motion-tracks.json'
    tracks=json.loads(tracks_path.read_text())
    proxy=Path('/tmp/pocketstage-6374-cloud.VoMMHG/takes/f9d38615-6f3c-4073-9c9e-59ca3072acda/proxy.mp4')
    if not proxy.is_file() or digest(proxy)!=tracks['proxy_sha256']:
        raise ValueError('Canonical RGB does not match the local motion export; no upload prepared')
    for name in ('phone','moisturizer','water-bottle'):
        if any(s['position_status'] not in ('VALID','DEGRADED') for s in tracks['tracks_absolute'][name]['samples'] if s['time_s']>=2):
            raise ValueError('Selected interval contains tracking gaps')
    output.mkdir(parents=True,exist_ok=False)
    video=output/'reference-camera.mp4'
    subprocess.run(['ffmpeg','-v','error','-ss','2','-i',str(proxy),'-t','7.2','-an','-vf','scale=720:1280,fps=24',
                    '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-n',str(video)],check=True)
    plan={'schema':'pocketstage-reference-edit/1','model':MODEL,'prompt':PROMPT,'video_path':str(video),
          'video_sha256':digest(video),'source_preview_path':str(source),'tracks_path':str(tracks_path),
          'source_proxy_sha256':tracks['proxy_sha256'],'tracks_sha256':digest(tracks_path),
          'source_interval_s':[2,9.2],'encoding_fps':24,'fps_conversion':'duplicate/drop_frames_no_speed_change',
          'bindings':{'dragon':'water-bottle','fighting_knight':'phone','fleeing_knight':'moisturizer'},
          'ending':'authored_mutual_death_non_graphic','camera':'source_rgb_no_crop_no_reframing',
          'max_submissions':1,'accepted':False,'directory':str(output)}
    _save(output/'plan.json',plan)
    return {'status':'PREPARED','plan':str(output/'plan.json'),'video':str(video)}


def start(directory,key,approved=False):
    if not approved: raise ValueError('Explicit --approve-upload-and-generation required')
    directory=Path(directory)
    with _lock(directory):
        state_path=directory/'state.json'
        if state_path.exists(): return json.loads(state_path.read_text())
        plan=json.loads((directory/'plan.json').read_text())
        if plan['model']!=MODEL or digest(plan['video_path'])!=plan['video_sha256']:
            raise ValueError('Plan or input identity mismatch')
        state={'status':'SUBMITTING','model':MODEL,'request_id':None,'accepted':False}
        _save(state_path,state)
        try:
            transport=FalTransport(key=key)
            url=transport.upload(plan['video_path'])
            payload={'video_url':url,'prompt':plan['prompt'],'keep_audio':False,'shot_type':'customize'}
            req=Request('https://queue.fal.run/'+MODEL,data=json.dumps(payload).encode(),method='POST',
                        headers={'Authorization':'Key '+key,'Content-Type':'application/json'})
            with build_opener(_https_handler(),_NoRedirects()).open(req,timeout=30) as response:
                body=json.loads(response.read(1024*1024))
            request_id=body.get('request_id')
            if not isinstance(request_id,str) or not request_id: raise ValueError('Missing request ID')
            state.update(status='QUEUED',request_id=request_id)
        except Exception as exc:
            state.update(status='NEEDS_RECONCILIATION',error=type(exc).__name__)
        _save(state_path,state)
        return state


def poll(directory,key):
    directory=Path(directory)
    with _lock(directory):
        path=directory/'state.json';state=json.loads(path.read_text())
        if not state.get('request_id') or state['status']=='REVIEW_READY':return state
        transport=FalTransport(key=key)
        try:
            state['status']=transport.status(MODEL,state['request_id'])
            if state['status']=='COMPLETED':
                result=transport.result(MODEL,state['request_id'])
                target=directory/'generated-video.mp4'
                if not target.exists(): download_artifact(result['video']['url'],target)
                from .media import probe_video
                meta=probe_video(target)
                state.update(status='REVIEW_READY',artifact=str(target),
                             media={k:meta[k] for k in ('width','height','frame_count','codec')})
        except Exception as exc:
            state.update(status='FETCH_OR_INSPECTION_FAILED',error=type(exc).__name__)
        _save(path,state);return state


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','start','poll'])
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--approve-upload-and-generation',action='store_true');a=p.parse_args()
    if a.action=='prepare': result=prepare(a.repo,a.out)
    else:
        key=load_key(a.repo/'.env')
        if not key: raise ValueError('Configure local repo FAL_KEY; never print it')
        result=start(a.out,key,a.approve_upload_and_generation) if a.action=='start' else poll(a.out,key)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
