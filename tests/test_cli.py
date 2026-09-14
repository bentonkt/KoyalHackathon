import contextlib
import io
import json
import unittest

from pocketstage.cli import main


class CLITests(unittest.TestCase):
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
