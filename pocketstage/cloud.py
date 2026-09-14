"""Persisted, bounded SAM/depth smoke runs; no tracking or pose inference."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .providers import sam2_request, depth_request


def load_key(env_file=None):
    """Read only FAL_KEY. Never execute .env contents or print the value."""
    if os.environ.get('FAL_KEY'):
        return os.environ['FAL_KEY']
    if env_file is not None and Path(env_file).is_file():
        lines=Path(env_file).read_text().splitlines()
        for line in lines:
            name, separator, value = line.strip().partition('=')
            if separator and name.strip().removeprefix('export ') == 'FAL_KEY':
                return value.strip().strip('\"\'') or None
        # Also accept a user-provided single bare credential without rewriting it.
        entries=[line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
        if len(entries)==1 and ':' in entries[0] and not any(c.isspace() for c in entries[0]) and '=' not in entries[0]:
            return entries[0].strip('\"\'')
    return None


def _save(path, value):
    fd, temp = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def _lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('This cloud run is already being operated on') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def plan_run(project, take_id, point):
    """Validate one immutable proxy and construct a stable two-job run identity."""
    import uuid
    project = Path(project).resolve()
    take_id = str(uuid.UUID(take_id))
    manifest = json.loads((project/'takes'/take_id/'manifest.json').read_text())
    proxy = manifest['proxy']
    path = (project/proxy['path']).resolve()
    if not path.is_relative_to(project) or not path.is_file():
        raise ValueError('Invalid proxy path')
    if path.stat().st_size > 100*1024*1024:
        raise ValueError('Proxy exceeds the smoke-run upload limit')
    if hashlib.sha256(path.read_bytes()).hexdigest() != proxy['sha256']:
        raise ValueError('Proxy hash mismatch')
    x, y, frame = point
    if any(type(v) is not int for v in point) or not (0 <= x < proxy['width'] and 0 <= y < proxy['height'] and 0 <= frame < proxy['frame_count']):
        raise ValueError('Point must be X Y FRAME within the canonical proxy')
    placeholder = 'https://pending.fal.media/canonical-proxy.mp4'
    sam = sam2_request(placeholder, [{'x':x,'y':y,'label':1,'frame_index':frame}])
    sam['input'].update(apply_mask=False, boundingbox_zip=False)
    depth = depth_request(placeholder)
    depth['input'].update(resolution='auto', max_frames=proxy['frame_count'], output_fps=proxy['fps'])
    config = {'schema_version':1, 'take_id':take_id, 'proxy':proxy, 'jobs':{'sam2':sam,'depth':depth}}
    run_id = hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:24]
    return {'run_id':run_id,'directory':str(project/'cloud'/run_id), 'proxy_path':str(path),
            'configuration':config,'max_model_submissions':2,'requires_upload_consent':True,
            'requires_sponsor_coverage':True,'sam_mask_semantics':'unverified'}


def start_run(plan, transport, *, upload_consent=False, sponsor_coverage=False):
    if not upload_consent or not sponsor_coverage:
        raise ValueError('Upload consent and confirmed sponsor coverage are required')
    directory=Path(plan['directory'])
    with _lock(directory):
        state_path=directory/'state.json'
        if state_path.exists():
            # Existing or ambiguous submissions are never blindly replayed.
            return json.loads(state_path.read_text())
        state={'run_id':plan['run_id'],'configuration':plan['configuration'],
               'upload_consent':True,'sponsor_coverage_confirmed_by_user':True,
               'status':'UPLOADING','jobs':{}}
        _save(state_path,state)
        try:
            uploaded=transport.upload(Path(plan['proxy_path']))
            state['uploaded_url']=uploaded
            state['status']='SUBMITTING'
            _save(state_path,state)
            for name, request in plan['configuration']['jobs'].items():
                args=dict(request['input'],video_url=uploaded)
                job={'model':request['model'],'status':'SUBMITTING','request_id':None}
                state['jobs'][name]=job
                _save(state_path,state) # Intent before network; uncertain submit never retries.
                request_id=transport.submit(request['model'],args)
                job.update(request_id=request_id,status='QUEUED')
                _save(state_path,state)
            state['status']='QUEUED'
        except Exception as exc:
            state['status']='NEEDS_RECONCILIATION'
            state['error']='Upload/submission failed or is uncertain; inspect provider requests before any new submission'
            state['diagnostic_type']=type(exc).__name__
            _save(state_path,state)
            raise RuntimeError(state['error']) from None
        _save(state_path,state)
        return state


def poll_run(directory, transport, *, downloader=None):
    """One nonblocking queue snapshot plus completed-result retrieval; never submit."""
    from .fal_transport import download_artifact
    from .artifacts import inspect_sam_video, inspect_depth
    downloader=downloader or download_artifact
    directory=Path(directory)
    with _lock(directory):
        state_path=directory/'state.json'
        state=json.loads(state_path.read_text())
        proxy=state['configuration']['proxy']
        expected=(proxy['frame_count'],proxy['height'],proxy['width'])
        for name,job in state['jobs'].items():
            if not job.get('request_id') or job['status']=='REVIEW_READY':
                continue
            try:
                status=transport.status(job['model'],job['request_id'])
                job['status']=status
                _save(state_path,state)
                if status != 'COMPLETED':
                    continue
                result=job.get('result')
                if result is None:
                    result=transport.result(job['model'],job['request_id'])
                    job['result']=result
                    _save(state_path,state)
                key='video' if name=='sam2' else 'raw_depths'
                item=result.get(key)
                if not isinstance(item,dict) or not item.get('url'):
                    raise ValueError('Required model artifact is missing')
                artifact=directory/('sam2-video.mp4' if name=='sam2' else 'depths.npz')
                if not artifact.exists():
                    downloader(item['url'],artifact)
                job['artifact']=str(artifact)
                job['inspection']=(inspect_sam_video(artifact,expected,proxy['fps']) if name=='sam2'
                                   else inspect_depth(artifact,expected,proxy['fps']))
                job['status']='REVIEW_READY'
                job.pop('error',None)
            except Exception:
                # Preserve request IDs and allow retrieval-only reconciliation.
                job['status']='INSPECTION_OR_FETCH_FAILED'
                job['error']='Provider status, artifact retrieval or validation failed; no replacement job submitted'
            _save(state_path,state)
        state['status']='REVIEW_READY' if len(state['jobs'])==2 and all(j['status']=='REVIEW_READY' for j in state['jobs'].values()) else 'PENDING_OR_NEEDS_REVIEW'
        state['full_pipeline_verified']=False
        _save(state_path,state)
        return state


def public_status(state):
    """Console output excludes keys, hosted footage URLs and raw provider responses."""
    return {'run_id':state['run_id'],'status':state['status'],
            'full_pipeline_verified':False,
            'jobs':{name:{k:v for k,v in job.items() if k in ('model','request_id','status','artifact','inspection','error')}
                    for name,job in state['jobs'].items()}}
