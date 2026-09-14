import unittest

import numpy as np

from pocketstage.relative import attach_relative_depth, relative_scene


def track(points, depths=None):
    samples = []
    for index, point in enumerate(points):
        samples.append({
            "time_s": index / 10,
            "position_status": "VALID" if point is not None else "LOST",
            "position_px": point,
            "position_normalized": point,
            "depth_raw": None if depths is None else depths[index],
        })
    return {"samples": samples}


class DepthTests(unittest.TestCase):
    def test_raw_depth_static_and_gap_are_not_normalized_or_smoothed(self):
        source = track([[1, 1], None, [1, 1]])
        depths = np.stack([np.full((7, 7), 4.0), np.full((7, 7), 99.0), np.full((7, 7), 4.0)])
        masks = np.ones_like(depths, dtype=bool)
        result = attach_relative_depth(source, depths, masks, np.ones(3, dtype=bool))
        self.assertEqual(result["samples"][0]["depth_raw"], 4.0)
        self.assertEqual(result["samples"][0]["depth_delta_from_first_valid"], 0.0)
        self.assertIsNone(result["samples"][1]["depth_raw"])
        self.assertEqual(result["samples"][2]["depth_delta_from_first_valid"], 0.0)
        self.assertEqual(result["samples"][2]["depth_status"], "RELATIVE_UNVALIDATED")
        self.assertFalse(result["depth_provenance"]["identity_certified"])


class SceneTests(unittest.TestCase):
    def test_common_translation_cancels_and_reference_is_zero(self):
        tracks = {
            "reference": track([[0.1, 0.2], [0.2, 0.3]], [4.0, 5.0]),
            "actor": track([[0.4, 0.6], [0.5, 0.7]], [7.0, 8.0]),
        }
        scene = relative_scene(tracks, "reference")
        for sample in scene["samples"]:
            np.testing.assert_allclose(sample["objects"]["actor"]["position_relative"], [0.3, 0.4])
            np.testing.assert_allclose(sample["objects"]["reference"]["position_relative"], [0, 0])
            self.assertEqual(sample["objects"]["actor"]["depth_difference_raw"], 3.0)
        self.assertFalse(scene["identity_certified"])
        self.assertIn("not_3d_or_metres", scene["semantics"])

    def test_reference_gap_invalidates_every_relative_position(self):
        scene = relative_scene(
            {"reference": track([[0, 0], None]), "actor": track([[1, 1], [2, 2]])},
            "reference",
        )
        self.assertIsNone(scene["samples"][1]["objects"]["actor"]["position_relative"])

    def test_multiple_static_objects_keep_measured_coordinates(self):
        tracks = {
            "reference": track([[0, 0], [1, 0]]),
            "wall": track([[2, 0], [2.5, 0]]),
            "chair": track([[4, 0], [5, 0]]),
        }
        scene = relative_scene(tracks, "reference", static_ids=["wall", "chair"])
        self.assertEqual(scene["samples"][0]["objects"]["wall"]["role"], "static_measured")
        self.assertEqual(scene["samples"][1]["objects"]["wall"]["position_relative"], [1.5, 0.0])
        self.assertEqual(scene["samples"][1]["objects"]["chair"]["position_relative"], [4.0, 0.0])
        self.assertEqual(scene["static_policy"], "role_only_coordinates_remain_measured")

    def test_rejects_invalid_times_and_unknown_static_ids(self):
        invalid = track([[0, 0], [1, 1]])
        invalid["samples"][1]["time_s"] = invalid["samples"][0]["time_s"]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            relative_scene({"reference": invalid}, "reference")
        with self.assertRaisesRegex(ValueError, "static_ids"):
            relative_scene({"reference": track([[0, 0]])}, "reference", ["unknown"])

    def test_does_not_mix_stage_and_normalized_coordinates(self):
        reference = track([[0, 0]])
        actor = track([[1, 1]])
        del actor["samples"][0]["position_normalized"]
        actor["samples"][0]["position_stage"] = [1, 1]
        scene = relative_scene({"reference": reference, "actor": actor}, "reference")
        self.assertIsNone(scene["samples"][0]["objects"]["actor"]["position_relative"])


if __name__ == "__main__":
    unittest.main()
