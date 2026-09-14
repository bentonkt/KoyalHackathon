import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pocketstage.motion_brush import IDS, compile_paths, start


class BrushTests(unittest.TestCase):
    def fixture(self):
        return {'tracks_absolute':{name:{'samples':[{'time_s':i/15,'position_normalized':[.2+i*.001,.4],
                'position_status':'VALID'} for i in range(106)]} for name in IDS}}

    def test_edit_changes_only_runner_after_start(self):
        source=self.fixture(); original=copy.deepcopy(source)
        a=compile_paths(source,900,1600);b=compile_paths(source,900,1600,True)
        self.assertEqual(a[:2],b[:2]);self.assertEqual(a[2][0],b[2][0])
        self.assertGreater(b[2][-1]['y'],a[2][-1]['y']);self.assertEqual(source,original)

    def test_gap_rejected(self):
        source=self.fixture();source['tracks_absolute']['phone']['samples'][45]['position_status']='LOST'
        with self.assertRaises(ValueError):compile_paths(source,900,1600)

    def test_no_repeat_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            state={'status':'SUBMITTING','request_id':None}
            (Path(directory)/'state.json').write_text(json.dumps(state))
            with patch('pocketstage.motion_brush.FalTransport') as transport:
                self.assertEqual(start(directory,'unused',True),state);transport.assert_not_called()

    def test_approval_required(self):
        with self.assertRaises(ValueError):start('missing','unused')
