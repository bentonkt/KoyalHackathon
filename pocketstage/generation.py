"""Capture Studio -> generic, persisted Kling Motion Brush jobs."""
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import threading

import cv2
import numpy as np

from .cloud import _save, load_key
from .motion_brush import MODEL, digest, start, poll

MAX_REQUEST_BYTES = 16 * 1024 * 1024


def number(value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('Invalid numeric generation setting')
    return float(value)


def compile_controls(tracks, bindings, width, height, start_s, scale):
    """Move reviewed image-region centers by absolute-source displacements."""
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 6:
        raise ValueError('Bind one to six subjects')
    output, ids = [], set()
    query = np.linspace(start_s, start_s + 5, 11)
    for binding in bindings:
        if not isinstance(binding, dict): raise ValueError('Invalid binding')
        object_id = binding.get('object_id')
        if not isinstance(object_id, str) or object_id in ids or object_id not in tracks.get('tracks_absolute', {}):
            raise ValueError('Choose unique objects from this analyzed take')
        ids.add(object_id)
        rect = binding.get('rect')
        if not isinstance(rect, list) or len(rect) != 4: raise ValueError('Draw a character region')
        x, y, w, h = [number(v, 0, 1) for v in rect]
        if w < .01 or h < .01 or x+w > 1.000001 or y+h > 1.000001:
            raise ValueError('Character region is too small or outside image')
        samples = tracks['tracks_absolute'][object_id]['samples']
        times = np.array([s['time_s'] for s in samples], dtype=float)
        if len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            raise ValueError('Invalid source timestamps')
        if query[0] < times[0] or query[-1] > times[-1]+1e-6:
            raise ValueError('Choose a fully observed five-second interval')
        lo = max(0, int(np.searchsorted(times, query[0], side='right'))-1)
        hi = min(len(times), int(np.searchsorted(times, query[-1], side='left'))+1)
        selected = samples[lo:hi]; times = times[lo:hi]
        if np.any(np.diff(times) > .25) or any(s.get('position_status') not in ('VALID','DEGRADED') or s.get('position_normalized') is None for s in selected):
            raise ValueError(f'Tracking gap in {object_id}; choose another interval')
        xy = np.asarray([s['position_normalized'] for s in selected], dtype=float)
        if xy.shape != (len(times),2) or not np.isfinite(xy).all(): raise ValueError('Invalid track positions')
        path = np.column_stack([np.interp(query,times,xy[:,axis]) for axis in range(2)])
        path = np.array([x+w/2,y+h/2]) + scale*(path-path[0])
        if np.any(path < 0) or np.any(path > 1): raise ValueError(f'{object_id} leaves frame; reduce motion scale or reposition region')
        pixels = np.rint(path*[width-1,height-1]).astype(int)
        output.append({'object_id':object_id,'rect':[x,y,w,h],
                       'trajectories':[{'x':int(px),'y':int(py)} for px,py in pixels]})
    return output


class GenerationService:
    def __init__(self, jobs_root, key_path):
        self.jobs_root, self.key_path = Path(jobs_root), Path(key_path)
        self.lock = threading.Lock()

    def directory(self, job_id, generation_id):
        if not all(isinstance(value,str) and re.fullmatch(r'[0-9a-f]{32}', value) for value in (job_id,generation_id)):
            raise ValueError('Invalid job ID')
        return self.jobs_root/job_id/'generations'/generation_id

    def create(self, job_id, data):
        if not isinstance(data,dict) or data.get('consent') is not True:
            raise ValueError('Review controls and approve fal generation first')
        generation_id=data.get('generation_id','')
        directory=self.directory(job_id,generation_id)
        fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()
        with self.lock:
            if directory.exists():
                meta=json.loads((directory/'api-state.json').read_text())
                if meta['input_hash'] != fingerprint: raise ValueError('This request ID belongs to different inputs; use a new generation')
                return self.read(job_id,generation_id,refresh=False)
            parent=json.loads((self.jobs_root/job_id/'api-state.json').read_text())
            if parent.get('status') != 'READY': raise ValueError('Wait for analysis to finish')
            prompt=data.get('prompt')
            if not isinstance(prompt,str) or not 1 <= len(prompt.strip()) <= 2000: raise ValueError('Prompt must contain 1–2000 characters')
            start_s=number(data.get('start_s',0),0,600);scale=number(data.get('motion_scale',1),.05,3)
            encoded=data.get('image_base64')
            if not isinstance(encoded,str) or len(encoded)>MAX_REQUEST_BYTES: raise ValueError('Image is too large')
            try: raw=base64.b64decode(encoded,validate=True)
            except ValueError: raise ValueError('Invalid image encoding') from None
            # Inspect dimensions before OpenCV allocation/decoding.
            import io
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as header:
                width,height=header.size
                if header.format not in ('PNG','JPEG') or min(width,height)<300 or max(width,height)>3840 or width*height>9_000_000:
                    raise ValueError('Use a PNG/JPEG, 300–3840 pixels per side, at most 9 megapixels')
            image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            if image is None: raise ValueError('Image could not be decoded')
            tracks_path=self.jobs_root/job_id/'result'/'motion-tracks.json'
            controls=compile_controls(json.loads(tracks_path.read_text()),data.get('bindings'),width,height,start_s,scale)
            if not load_key(self.key_path): raise ValueError('FAL_KEY is not configured on the backend')
            directory.mkdir(parents=True,exist_ok=False)
            image_path=directory/'starting-image.png';cv2.imwrite(str(image_path),image)
            masks=[]
            for index,control in enumerate(controls):
                mask=np.zeros((height,width),np.uint8);x,y,w,h=control['rect']
                cv2.rectangle(mask,(round(x*(width-1)),round(y*(height-1))),
                              (round((x+w)*(width-1)),round((y+h)*(height-1))),255,-1)
                target=directory/f'mask-{index}.png';cv2.imwrite(str(target),mask);masks.append(target)
            ratio=width/height;aspect='9:16' if ratio<.8 else '16:9' if ratio>1.25 else '1:1'
            _save(directory/'plan.json',{'schema':'pocketstage-ui-motion-brush/1',
                'settings':{'model':MODEL,'prompt':prompt.strip(),'duration':'5','aspect_ratio':aspect},
                'image':str(image_path),'masks':[str(p) for p in masks],
                'file_hashes':{str(p):digest(p) for p in [image_path,*masks]},
                'source_sha256':digest(tracks_path),'source_interval_s':[start_s,start_s+5],
                'controls':controls,'trajectories':[c['trajectories'] for c in controls],
                'sample_times_s':np.linspace(0,5,11).tolist(),'motion_scale':scale,
                'semantics':'reviewed_image_anchor_plus_absolute_screen_displacement_not_3d',
                'timing':'uniform_points_provider_timing_unverified','source_video_uploaded':False,
                'isolated_upload_cache':True,'accepted':False})
            _save(directory/'api-state.json',{'input_hash':fingerprint,'status':'PREPARING'})
            threading.Thread(target=self._submit,args=(directory,),daemon=True).start()
        return self.read(job_id,generation_id,refresh=False)

    def _submit(self,directory):
        try: start(directory,load_key(self.key_path),approved=True)
        except Exception:
            if not (directory/'state.json').exists():
                _save(directory/'state.json',{'status':'NEEDS_RECONCILIATION','request_id':None})

    def read(self,job_id,generation_id,refresh=True):
        directory=self.directory(job_id,generation_id)
        if (directory/'state.json').exists():
            state=poll(directory,load_key(self.key_path)) if refresh else json.loads((directory/'state.json').read_text())
        else: state=json.loads((directory/'api-state.json').read_text())
        public={'generation_id':generation_id,'status':state['status'],'accepted':False,
                'request_id':state.get('request_id'),'model':MODEL}
        if state['status']=='REVIEW_READY': public['video_url']=f'/api/jobs/{job_id}/generations/{generation_id}/video'
        return public

    def artifact(self,job_id,generation_id):
        if self.read(job_id,generation_id,refresh=False)['status']!='REVIEW_READY': raise FileNotFoundError
        return self.directory(job_id,generation_id)/'generated-video.mp4'
