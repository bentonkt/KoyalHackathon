import tempfile
import unittest
from pathlib import Path
from pocketstage.demo import build_motion_demo, reviewed_start_frame


class DemoTests(unittest.TestCase):
    def test_review_can_only_delay_available_prefix(self):
        prompts=[{'frame_index':3,'label':1}]
        self.assertEqual(reviewed_start_frame({'mask_review':{'valid_from_frame':15}},prompts,79),(3,15))
        self.assertEqual(reviewed_start_frame({'mask_review':{'valid_from_frame':0}},prompts,79),(3,3))
        with self.assertRaises(ValueError):
            reviewed_start_frame({'mask_review':{'valid_from_frame':79}},prompts,79)
    def test_review_before_reading_artifacts(self):
        with self.assertRaisesRegex(ValueError,'Review'):
            build_motion_demo({'phone':'missing'},'phone',[],Path('unused'))
    def test_requires_reference(self):
        with self.assertRaisesRegex(ValueError,'reference'):
            build_motion_demo({'phone':'missing'},'bottle',[],Path('unused'),reviewed_masks=True)
    def test_preserves_existing_exports(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError):
                build_motion_demo({'phone':'missing'},'phone',[],d,reviewed_masks=True)
