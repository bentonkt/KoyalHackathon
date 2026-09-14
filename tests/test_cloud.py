import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pocketstage.cloud import load_key, start_run, poll_run, public_status


class Fake:
    def __init__(self,fail=False): self.uploads=0; self.submits=0; self.fail=fail
    def upload(self,path): self.uploads+=1; return 'https://v3.fal.media/clip.mp4'
    def submit(self,model,args):
        self.submits+=1
        if self.fail: raise RuntimeError('secret body must not escape')
        return str(self.submits)


class CloudTests(unittest.TestCase):
    def plan(self,directory):
        return {'run_id':'test','directory':str(directory),'proxy_path':'clip.mp4',
                'configuration':{'jobs':{'sam2':{'model':'sam','input':{}},'depth':{'model':'depth','input':{}}}}}
    def test_consent_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            fake=Fake()
            with self.assertRaises(ValueError): start_run(self.plan(Path(d)),fake)
            self.assertEqual(fake.uploads,0)
    def test_one_upload_two_submissions_idempotent_restart(self):
        with tempfile.TemporaryDirectory() as d:
            fake=Fake(); plan=self.plan(Path(d))
            first=start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            second=start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            self.assertEqual((fake.uploads,fake.submits),(1,2))
            self.assertEqual(first,second)
            self.assertNotIn('uploaded_url',public_status(first))
    def test_uncertain_submission_never_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            fake=Fake(True); plan=self.plan(Path(d))
            with self.assertRaisesRegex(RuntimeError,'uncertain'):
                start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            state=start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            self.assertEqual(fake.submits,1)
            self.assertEqual(state['status'],'NEEDS_RECONCILIATION')
            self.assertNotIn('secret body',json.dumps(state))
    def test_env_is_data_not_shell(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{},clear=True):
            path=Path(d)/'.env'; path.write_text('FAL_KEY="test:credential"\n')
            self.assertEqual(load_key(path),'test:credential')
            path.write_text('test:credential\n')
            self.assertEqual(load_key(path),'test:credential')

    def test_completed_jobs_download_once_without_submitting(self):
        class Completed(Fake):
            def status(self,model,request_id): return 'COMPLETED'
            def result(self,model,request_id):
                return {'video':{'url':'https://v3.fal.media/masks.mp4'},'raw_depths':{'url':'https://v3.fal.media/depth.npz'}}
        with tempfile.TemporaryDirectory() as d:
            plan=self.plan(Path(d)); plan['configuration']['proxy']={'frame_count':2,'height':4,'width':6,'fps':15}
            fake=Completed()
            start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            downloads=[]
            def download(url,path): downloads.append(url); path.write_bytes(b'fixture')
            with patch('pocketstage.artifacts.inspect_sam_video',return_value={'mask_contract':'requires_review'}),patch('pocketstage.artifacts.inspect_depth',return_value={'units':'unknown'}):
                state=poll_run(d,fake,downloader=download)
                poll_run(d,fake,downloader=download)
            self.assertEqual(len(downloads),2)
            self.assertEqual(fake.submits,2)
            self.assertEqual(state['status'],'REVIEW_READY')
            self.assertFalse(state['full_pipeline_verified'])

    def test_invalid_artifact_preserves_job_for_retrieval_only(self):
        class Invalid(Fake):
            def status(self,model,request_id): return 'COMPLETED'
            def result(self,model,request_id): return {}
        with tempfile.TemporaryDirectory() as d:
            plan=self.plan(Path(d)); plan['configuration']['proxy']={'frame_count':2,'height':4,'width':6,'fps':15}
            fake=Invalid(); start_run(plan,fake,upload_consent=True,sponsor_coverage=True)
            state=poll_run(d,fake)
            self.assertEqual(fake.submits,2)
            self.assertTrue(all(j['request_id'] for j in state['jobs'].values()))
            self.assertTrue(all(j['status']=='INSPECTION_OR_FETCH_FAILED' for j in state['jobs'].values()))


if __name__=='__main__': unittest.main()
