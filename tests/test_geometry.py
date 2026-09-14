import unittest

from pocketstage.geometry import map_planar_samples


class GeometryTests(unittest.TestCase):
    def test_mapping_and_evidence_preserved(self):
        sample = {"position_px": [50, 25], "position_status": "VALID"}
        result = map_planar_samples([sample], [[0, 0], [100, 0], [100, 50], [0, 50]], 4, 2)
        self.assertEqual(result[0]["position_stage"], [2, 1])
        self.assertNotIn("position_stage", sample)

    def test_gap_is_not_position(self):
        result = map_planar_samples([{"position_px": None, "position_status": "LOST"}], [[0, 0], [10, 0], [10, 10], [0, 10]])
        self.assertIsNone(result[0]["position_stage"])

    def test_invalid_corners(self):
        with self.assertRaises(ValueError):
            map_planar_samples([], [[0, 0], [10, 10], [0, 10], [10, 0]])


if __name__ == "__main__":
    unittest.main()
