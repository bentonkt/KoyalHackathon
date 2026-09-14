import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from pocketstage.providers import (
    contract_report,
    depth_request,
    load_raw_depths,
    sam2_request,
    validate_binary_masks,
)


class RequestTests(unittest.TestCase):
    def test_request_shapes(self):
        prompts = [{"x": 12, "y": 9, "label": 1, "frame_index": 0}]
        sam = sam2_request("https://example.test/take.mp4", prompts)
        self.assertEqual(sam["model"], "fal-ai/sam2/video")
        self.assertEqual(sam["input"], {"video_url": "https://example.test/take.mp4", "prompts": prompts})
        depth = depth_request("https://example.test/take.mp4")
        self.assertEqual(depth["model"], "fal-ai/depth-anything-video")
        self.assertEqual(depth["input"]["model"], "VDA-Small")
        self.assertIs(depth["input"]["include_raw_depths"], True)

    def test_rejects_bad_urls_and_prompts(self):
        with self.assertRaises(ValueError):
            depth_request("http://example.test/take.mp4")
        with self.assertRaises(ValueError):
            sam2_request("https://example.test/take.mp4", [])
        with self.assertRaises(ValueError):
            sam2_request("https://example.test/take.mp4", [{"frame_index": 0}])
        with self.assertRaises(ValueError):
            sam2_request(
                "https://example.test/take.mp4",
                [{"x": 1, "y": 2, "label": 2, "frame_index": 0}],
            )
        with self.assertRaises(ValueError):
            sam2_request(
                "https://example.test/take.mp4",
                [{"x": 1, "y": 2, "label": 1.0, "frame_index": 0}],
            )
        with self.assertRaises(ValueError):
            sam2_request(
                "https://example.test/take.mp4",
                [{"x": 1, "y": 2, "label": 1, "frame_index": 0, "extra": 3}],
            )

    def test_report_never_claims_endpoint_passed(self):
        report = contract_report(
            {"video": {"url": "https://x"}, "boundingbox_frames_zip": {"url": "https://x"}},
            {"raw_depths": {"url": "https://x"}},
        )
        self.assertFalse(report["endpoint_contract_passed"])
        self.assertEqual(report["mask_contract"]["status"], "unverified")
        self.assertFalse(report["mask_contract"]["usable_raw_masks"])
        self.assertTrue(report["depth_contract"]["raw_depth_url_available"])
        self.assertFalse(report["depth_contract"]["raw_depth_validated"])


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _npz(self, name="depth.npz", **arrays):
        path = self.root / name
        np.savez(path, **arrays)
        return path

    def test_loads_aligned_finite_float_depths(self):
        depths = np.ones((2, 3, 4), dtype=np.float32)
        path = self._npz(depths=depths, shape=np.array(depths.shape), fps=np.array(30.0))
        actual = load_raw_depths(path, (2, 3, 4), 30.0)
        np.testing.assert_array_equal(actual, depths)

    def test_rejects_corrupt_and_misaligned_npz(self):
        corrupt = self.root / "corrupt.npz"
        corrupt.write_bytes(b"not a zip")
        with self.assertRaises(ValueError):
            load_raw_depths(corrupt, (2, 3, 4), 30.0)
        bad = self._npz(depths=np.ones((2, 3, 4), np.float32), fps=np.array(24.0))
        with self.assertRaisesRegex(ValueError, "fps"):
            load_raw_depths(bad, (2, 3, 4), 30.0)
        missing_fps = self._npz("missing.npz", depths=np.ones((2, 3, 4), np.float32))
        with self.assertRaisesRegex(ValueError, "fps"):
            load_raw_depths(missing_fps, (2, 3, 4), 30.0)

    def test_rejects_oversized_npz_before_loading(self):
        path = self.root / "large.npz"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("depths.npy", b"x" * 65)
        with self.assertRaisesRegex(ValueError, "uncompressed-size"):
            load_raw_depths(path, (1, 1, 1), 30.0, max_uncompressed_bytes=64)

    def test_rejects_npy_header_claim_beyond_member(self):
        legitimate = self._npz(depths=np.ones((2, 2, 2), np.float32), fps=np.array(30.0))
        malicious = self.root / "header.npz"
        with zipfile.ZipFile(legitimate) as source, zipfile.ZipFile(malicious, "w") as target:
            for name in source.namelist():
                payload = source.read(name)
                if name == "depths.npy":
                    payload = payload[:-4]
                target.writestr(name, payload)
        with self.assertRaisesRegex(ValueError, "header"):
            load_raw_depths(malicious, (2, 2, 2), 30.0)

    def test_rejects_duplicate_npz_names(self):
        path = self.root / "duplicate.npz"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("depths.npy", b"one")
            archive.writestr("depths.npy", b"two")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_raw_depths(path, (1, 1, 1), 30.0)

    def test_rejects_bad_depth_values_and_shape(self):
        path = self._npz(depths=np.array([[[np.nan]]], np.float32), fps=np.array(30.0))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            load_raw_depths(path, (1, 1, 1), 30.0)
        ints = self._npz("ints.npz", depths=np.ones((1, 1, 1), np.int16), fps=np.array(30.0))
        with self.assertRaisesRegex(ValueError, "floating"):
            load_raw_depths(ints, (1, 1, 1), 30.0)

    def test_binary_mask_validation_rejects_overlays_and_malformed_values(self):
        expected = (2, 3, 4)
        valid = np.zeros(expected, dtype=np.uint8)
        valid[0, 0, 0] = 255
        self.assertEqual(validate_binary_masks(valid, expected).dtype, np.bool_)
        with self.assertRaisesRegex(ValueError, "color overlays"):
            validate_binary_masks(np.zeros((*expected, 3), dtype=np.uint8), expected)
        with self.assertRaisesRegex(ValueError, "0/1 or 0/255"):
            validate_binary_masks(np.full(expected, 127, dtype=np.uint8), expected)


if __name__ == "__main__":
    unittest.main()
