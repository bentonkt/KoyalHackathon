import unittest

import numpy as np

from pocketstage.tracking import generate_fixture, track_frames


class TrackingTests(unittest.TestCase):
    def test_known_translation(self):
        frames, times, region, expected = generate_fixture()
        samples = track_frames(frames, times, region)["samples"]
        self.assertTrue(all(s["position_status"] == "VALID" for s in samples))
        errors = [np.linalg.norm(np.asarray(s["position_px"]) - e) for s, e in zip(samples, expected)]
        self.assertLess(float(np.median(errors)), 1.0)
        self.assertIsNone(samples[-1]["heading_rad"])
        self.assertIsNone(samples[-1]["depth_relative"])

    def test_full_occlusion_fails_closed(self):
        frames, times, region, _ = generate_fixture(30)
        frames[12][:] = 12
        for i in range(13, len(frames)):
            frames[i] = frames[i].copy()
        samples = track_frames(frames, times, region)["samples"]
        self.assertEqual(samples[12]["position_status"], "LOST")
        self.assertTrue(all(s["position_px"] is None for s in samples[12:]))

    def test_prefix_is_unavailable(self):
        frames, times, region, expected = generate_fixture(20)
        region = [region[0] + 5 * 1.25, region[1] + 5 * .55, region[2], region[3]]
        samples = track_frames(frames, times, region, start_frame=5)["samples"]
        self.assertTrue(all(s["position_status"] == "UNAVAILABLE" for s in samples[:5]))
        self.assertAlmostEqual(samples[5]["position_px"][0], expected[5][0], delta=.7)

    def test_invalid_inputs_and_masks(self):
        frames, times, region, _ = generate_fixture(5)
        with self.assertRaises(ValueError):
            track_frames(frames, times[:-1], region)
        with self.assertRaises(ValueError):
            track_frames(frames, [0, 1, 1, 3, 4], region)
        with self.assertRaises(ValueError):
            track_frames(frames, times, region, masks=[np.ones((2, 2))] * 5)
        with self.assertRaises(ValueError):
            track_frames([frames[0], frames[1][:-1], *frames[2:]], times, region)


if __name__ == "__main__":
    unittest.main()
