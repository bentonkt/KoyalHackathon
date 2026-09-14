from pathlib import Path
import subprocess
import tempfile
import unittest

from pocketstage.media import probe_video
from pocketstage.preview import _scene_point, project_relative, render_motion_preview


class PreviewTests(unittest.TestCase):
    def test_projection_and_null(self):
        self.assertEqual(project_relative([1, -1], (100, 100), (80, 60)), (140, 70))
        self.assertIsNone(project_relative(None, (100, 100), (80, 60)))
        self.assertIsNone(project_relative([float("nan"), 0], (100, 100), (80, 60)))
        self.assertIsNone(_scene_point("ref", "ref", {"position_relative": None}, (100, 100), (80, 60), 1))
        self.assertEqual(_scene_point("ref", "ref", {"position_relative": [0, 0]}, (100, 100), (80, 60), 1),
                         (100, 100))

    def test_synthetic_video_encode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.mp4", root / "preview.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc2=size=120x80:rate=5:duration=0.6", "-frames:v", "3",
                            "-c:v", "mpeg4", str(source)], check=True)
            times = [value - probe_video(source)["timestamps"][0] for value in probe_video(source)["timestamps"]]
            samples = [{"time_s": time, "objects": {
                "ref": {"position_relative": [0, 0], "depth_difference_raw": 0, "status": "VALID"},
                "actor": {"position_relative": None if index == 1 else [index / 4, 0.2],
                          "depth_difference_raw": .5, "status": "LOST" if index == 1 else "VALID"}}}
                       for index, time in enumerate(times)]
            report = render_motion_preview(source, {"samples": samples, "reference_id": "ref",
                                                     "object_ids": ["ref", "actor"]}, output)
            self.assertEqual(report["frame_count"], 3)
            self.assertEqual((report["width"], report["height"]), (960, 540))
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
