import base64
import json
import tempfile
import unittest
from pathlib import Path

from pocketstage.server import JobService, _decode_metadata, _safe_object_ids


def encoded(value):
    return base64.b64encode(json.dumps(value).encode()).decode()


class CaptureStudioServerTests(unittest.TestCase):
    def test_selection_metadata_requires_consent_and_bounded_points(self):
        valid = {
            "upload_consent": True,
            "sponsor_coverage": True,
            "objects": [{"label": "Phone", "role": "actor-a", "x": 0.25, "y": 0.75}],
        }
        self.assertEqual(_decode_metadata(encoded(valid)), valid)
        for patch in (
            {"upload_consent": False},
            {"sponsor_coverage": False},
            {"objects": []},
            {"objects": [{"label": "Phone", "role": "actor-a", "x": 1.1, "y": 0.5}]},
        ):
            invalid = dict(valid, **patch)
            with self.assertRaises(ValueError):
                _decode_metadata(encoded(invalid))

    def test_object_ids_are_safe_stable_and_unique(self):
        objects = [{"label": "Black Water Bottle!"}, {"label": "Black Water Bottle!"}, {"label": "💧"}]
        self.assertEqual(_safe_object_ids(objects), ["black-water-bottle", "black-water-bottl-2", "object-3"])

    def test_public_job_state_hides_local_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            service = JobService(Path(folder))
            job_id = "a" * 32
            directory = Path(folder) / job_id
            directory.mkdir()
            (directory / "api-state.json").write_text(json.dumps({
                "job_id": job_id,
                "status": "QUEUED",
                "source_path": "/private/source.mov",
                "project_path": "/private/project",
                "result_path": "/private/result",
            }))
            state = service.read(job_id)
            self.assertEqual(state["status"], "QUEUED")
            self.assertNotIn("source_path", state)
            self.assertNotIn("project_path", state)
            self.assertNotIn("result_path", state)


if __name__ == "__main__":
    unittest.main()
