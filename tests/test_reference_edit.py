import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pocketstage.reference_edit import MODEL, PROMPT, start, poll


class ReferenceEditTests(unittest.TestCase):
    def test_explicit_approval_before_any_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'missing'
            with self.assertRaises(ValueError): start(out,'unused',False)
            self.assertFalse(out.exists())

    def test_existing_intent_is_not_resubmitted(self):
        with tempfile.TemporaryDirectory() as d:
            state={'status':'NEEDS_RECONCILIATION','request_id':None,'model':MODEL}
            (Path(d)/'state.json').write_text(json.dumps(state))
            with patch('pocketstage.reference_edit.FalTransport') as transport:
                self.assertEqual(start(d,'unused',True),state)
                self.assertEqual(poll(d,'unused'),state)
                transport.assert_not_called()

    def test_exact_story_and_endpoint(self):
        self.assertTrue(MODEL.endswith('/video-to-video/edit'))
        for required in ('WATER BOTTLE','PHONE','MOISTURIZER','both','Non-graphic'):
            self.assertIn(required.lower(),PROMPT.lower())
        self.assertIn('no split screen',PROMPT)
