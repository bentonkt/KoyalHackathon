import unittest

import numpy as np

from pocketstage.motion import motion_from_masks


def boxes(xs, count=None, height=80, width=100):
    count = len(xs) if count is None else count
    masks = np.zeros((count, height, width), dtype=bool)
    for i, x in enumerate(xs):
        masks[i, 25:35, x:x + 10] = True
    return masks


class MotionTests(unittest.TestCase):
    def test_translated_mask_and_schema(self):
        masks = boxes([10, 12, 14])
        result = motion_from_masks(masks, np.ones(3, bool), [0, .1, .2])
        self.assertEqual(result["metadata"]["method"], "sam_mask_centroid_demo")
        self.assertFalse(result["metadata"]["identity_guarantee"])
        sample = result["samples"][1]
        self.assertEqual(sample["position_status"], "VALID")
        self.assertAlmostEqual(sample["raw_position_px"][0], 16.5)
        self.assertAlmostEqual(sample["position_normalized"][0], 16.5 / 99)
        self.assertIsNone(sample["depth_relative"])

    def test_empty_and_unavailable_prefix(self):
        masks = boxes([20], count=3)
        available = np.array([False, True, True])
        samples = motion_from_masks(masks, available, [0, 1, 2])["samples"]
        self.assertEqual(samples[0]["position_status"], "UNAVAILABLE")
        self.assertEqual(samples[1]["position_status"], "LOST")
        self.assertEqual(samples[2]["position_status"], "LOST")

    def test_fragmented_mask_is_lost(self):
        masks = np.zeros((1, 80, 100), bool)
        masks[0, 5:10, 5:10] = True
        masks[0, 50:55, 70:75] = True
        sample = motion_from_masks(masks, np.ones(1, bool), [0])["samples"][0]
        self.assertEqual(sample["position_status"], "LOST")
        self.assertEqual(sample["reason"], "fragmented_ambiguous_mask")

    def test_gap_does_not_smooth_across_and_can_resume(self):
        masks = boxes([10, 12, 70, 72, 74])
        available = np.array([True, True, False, True, True])
        samples = motion_from_masks(masks, available, np.arange(5))["samples"]
        self.assertIsNone(samples[2]["position_px"])
        self.assertTrue(samples[3]["new_segment"])
        self.assertEqual(samples[3]["reason"], "new_segment")
        self.assertAlmostEqual(samples[1]["position_px"][0], 15.5)
        self.assertAlmostEqual(samples[3]["position_px"][0], 77.5)

    def test_outputs_are_finite_and_bad_arrays_rejected(self):
        result = motion_from_masks(boxes([10, 10, 10]), np.ones(3, bool), [0, 1, 2])
        values = [v for s in result["samples"] for v in (s["position_px"] or [])]
        self.assertTrue(np.all(np.isfinite(values)))
        with self.assertRaises(ValueError):
            motion_from_masks(boxes([10]).astype(np.uint8), np.ones(1, bool), [0])


if __name__ == "__main__":
    unittest.main()
