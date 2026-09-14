import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from pocketstage.media import _mapping, atomic_write_json, import_take, probe_video


class MediaTests(unittest.TestCase):
    def test_mapping_preserves_pts_prefix(self):
        probe = {"timestamps": [5.0, 5.04, 5.11, 5.20], "frame_durations": [0.04, 0.07, 0.09, 0.1]}
        times, indices = _mapping(probe, 10)
        self.assertEqual(times, [0.0, 0.1, 0.2])
        self.assertEqual(indices, [0, 2, 3])

    def test_probe_rejects_bad_timestamps(self):
        payload = {"streams": [{"width": 10, "height": 10}], "frames": [
            {"best_effort_timestamp_time": "1"}, {"best_effort_timestamp_time": "1"}]}
        result = type("R", (), {"stdout": json.dumps(payload).encode()})()
        with mock.patch("pocketstage.media._run", return_value=result):
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                probe_video(Path("bad.mp4"))

    def test_probe_rejects_rotation(self):
        payload = {"streams": [{"width": 10, "height": 10, "tags": {"rotate": "90"}}],
                   "frames": [{"best_effort_timestamp_time": "0", "pkt_duration_time": "1"}]}
        result = type("R", (), {"stdout": json.dumps(payload).encode()})()
        with mock.patch("pocketstage.media._run", return_value=result):
            with self.assertRaisesRegex(ValueError, "rotated video"):
                probe_video(Path("rotated.mp4"))

    def test_atomic_json_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            atomic_write_json(path, {"first": True})
            with self.assertRaises(FileExistsError):
                atomic_write_json(path, {"first": False})
            self.assertEqual(json.loads(path.read_text()), {"first": True})

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
    def test_import_take_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc2=size=160x90:rate=30:duration=0.6", "-c:v", "mpeg4", str(source)], check=True)
            manifest = import_take(source, root / "project", fps=15, height=48)
            source.write_bytes(b"changed externally")
            stored = root / "project" / manifest["source"]["path"]
            self.assertNotEqual(stored.read_bytes(), source.read_bytes())
            self.assertEqual(manifest["proxy"]["frame_count"], len(manifest["proxy"]["source_frame_indices"]))
            self.assertEqual(manifest["proxy"]["timestamps"],
                             [i / 15 for i in range(manifest["proxy"]["frame_count"])])
            self.assertEqual(manifest["proxy"]["width"] % 2, 0)
            self.assertEqual(manifest["proxy"]["height"] % 2, 0)

    def test_import_bounds_before_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input"
            source.write_bytes(b"x")
            with self.assertRaises(ValueError):
                import_take(source, Path(directory) / "project", fps=31)


if __name__ == "__main__":
    unittest.main()
