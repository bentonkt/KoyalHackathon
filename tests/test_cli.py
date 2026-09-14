import contextlib
import io
import json
import unittest
from unittest.mock import patch

from pocketstage.cli import main


class CLITests(unittest.TestCase):
    def test_cloud_object_returns_reusable_run_directory(self):
        state={'run_id':'new','run_directory':'/project/cloud/new','status':'QUEUED','jobs':{}}
        with patch('pocketstage.cloud.load_key',return_value='test:key'),patch('pocketstage.objects.add_object_run',return_value=state),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['cloud-object','/parent','--id','bottle','--point','1','2','0','--consent-upload','--sponsor-covered']),0)
        self.assertEqual(json.loads(output.getvalue())['run_directory'],'/project/cloud/new')
    def test_doctor_is_offline_and_non_disclosing(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["doctor"]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["paid_jobs_submitted"])
        self.assertEqual(result["sponsor_coverage"], "unverified")

    def test_take_id_cannot_be_a_path(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["track", "--project", ".", "--take", "../../escape", "--region", "0", "0", "10", "10"]), 2)
