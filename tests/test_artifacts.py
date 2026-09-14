from pathlib import Path
import subprocess
import tempfile
import unittest

import cv2
import numpy as np

from pocketstage.artifacts import inspect_depth, inspect_sam_video, extract_reviewed_sam_masks


def _video(path: Path, frames: list[np.ndarray], fps: int = 5) -> None:
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"FFV1"), fps, (width, height))
    if not writer.isOpened():
        raise unittest.SkipTest("FFV1 writer unavailable")
    for frame in frames:
        writer.write(frame)
    writer.release()


class ArtifactTests(unittest.TestCase):
    def test_reviewed_extraction_discards_uninitialized_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'prefix.mkv'
            full=np.full((40,50,3),255,np.uint8)
            mask=np.zeros((40,50,3),np.uint8); mask[10:20,15:25]=255
            mask[10,15]=128  # One compressed boundary pixel.
            _video(path,[full,mask,mask],5)
            with self.assertRaises(ValueError):
                extract_reviewed_sam_masks(path,(3,40,50),5,start_frame=1)
            result=extract_reviewed_sam_masks(path,(3,40,50),5,start_frame=1,reviewed_binary_video=True)
            self.assertEqual(result['available'].tolist(),[False,True,True])
            self.assertFalse(result['masks'][0].any())
            self.assertEqual(result['masks'].dtype,np.bool_)
    def test_binary_video_is_only_a_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masks.mkv"
            frames = []
            for index in range(3):
                image = np.zeros((16, 20, 3), np.uint8)
                image[:, index * 3:index * 3 + 5] = 255
                frames.append(image)
            _video(path, frames)
            report = inspect_sam_video(path, (3, 16, 20), 5)
            self.assertTrue(report["binary_candidate"])
            self.assertEqual(report["mask_contract"], "requires_review")
            self.assertEqual(report["temporal_alignment"], "unverified")

    def test_colored_segmented_video_is_not_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "colored.mkv"
            image = np.zeros((16, 20, 3), np.uint8)
            image[:, :10] = (0, 0, 255)
            _video(path, [image, image], 5)
            report = inspect_sam_video(path, (2, 16, 20), 5)
            self.assertFalse(report["binary_candidate"])
            self.assertFalse(report["channels_agree"])

    def test_depth_report_has_no_units_or_alignment_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "depth.npz"
            np.savez_compressed(path, depths=np.arange(24, dtype=np.float32).reshape(2, 3, 4),
                                shape=np.array([2, 3, 4]), fps=np.array(5.0))
            report = inspect_depth(path, (2, 3, 4), 5)
            self.assertTrue(report["valid_numeric_depth"])
            self.assertEqual(report["minimum"], 0.0)
            self.assertEqual(report["maximum"], 23.0)
            self.assertEqual(report["units"], "unknown")
            self.assertEqual(report["temporal_alignment"], "unverified")
            self.assertIsNone(report["model_confidence"])


if __name__ == "__main__":
    unittest.main()
