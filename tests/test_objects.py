import json
import tempfile
import unittest
from pathlib import Path

from pocketstage.objects import add_object_run


class FakeTransport:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def upload(self, path):
        raise AssertionError("upload must not be called")

    def submit(self, model, input):
        self.calls.append((model, input))
        if self.fail:
            raise TimeoutError("ambiguous")
        return "sam-new"


def parent_state():
    proxy = {"width": 100, "height": 50, "frame_count": 10, "sha256": "abc", "path": "proxy.mp4"}
    depth_request = {"model": "fal-ai/depth-anything-video", "input": {"video_url": "https://x.fal.media/p.mp4"}}
    return {
        "run_id": "parent-run", "uploaded_url": "https://x.fal.media/p.mp4",
        "upload_consent": True, "sponsor_coverage_confirmed_by_user": True,
        "configuration": {"proxy": proxy, "jobs": {"depth": depth_request, "sam2": {}}},
        "jobs": {"depth": {"model": "fal-ai/depth-anything-video", "status": "REVIEW_READY",
                            "request_id": "depth-original", "artifact": "/same/depth.npz"}},
    }


class ObjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name) / "cloud" / "parent-run"
        self.parent.mkdir(parents=True)
        (self.parent / "state.json").write_text(json.dumps(parent_state()))

    def tearDown(self):
        self.temp.cleanup()

    def test_reuses_upload_and_depth_and_submits_one_flat_sam_prompt(self):
        transport = FakeTransport()
        state = add_object_run(self.parent, "chair-2", (4, 5, 6), transport,
                               upload_consent=True, sponsor_coverage=True)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][0], "fal-ai/sam2/video")
        self.assertEqual(transport.calls[0][1]["prompts"],
                         [{"x": 4, "y": 5, "label": 1, "frame_index": 6}])
        self.assertEqual(state["jobs"]["depth"]["request_id"], "depth-original")
        self.assertEqual(state["jobs"]["depth"]["artifact"], "/same/depth.npz")
        self.assertEqual(Path(state["configuration"]["proxy"]["path"]), Path("proxy.mp4"))

    def test_existing_and_uncertain_runs_never_resubmit(self):
        transport = FakeTransport()
        first = add_object_run(self.parent, "cup", (1, 2, 3), transport,
                               upload_consent=True, sponsor_coverage=True)
        second = add_object_run(self.parent, "cup", (1, 2, 3), transport,
                                upload_consent=True, sponsor_coverage=True)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(len(transport.calls), 1)
        failing = FakeTransport(fail=True)
        with self.assertRaises(RuntimeError):
            add_object_run(self.parent, "lamp", (1, 2, 3), failing,
                           upload_consent=True, sponsor_coverage=True)
        recovered = add_object_run(self.parent, "lamp", (1, 2, 3), failing,
                                   upload_consent=True, sponsor_coverage=True)
        self.assertEqual(recovered["status"], "NEEDS_RECONCILIATION")
        self.assertEqual(len(failing.calls), 1)

    def test_invalid_coordinate_has_no_side_effect(self):
        transport = FakeTransport()
        before = set(self.parent.parent.iterdir())
        with self.assertRaises(ValueError):
            add_object_run(self.parent, "cup", (100, 2, 3), transport,
                           upload_consent=True, sponsor_coverage=True)
        self.assertEqual(transport.calls, [])
        self.assertEqual(set(self.parent.parent.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
