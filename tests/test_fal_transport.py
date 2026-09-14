import io
import tempfile
import unittest
from pathlib import Path

from pocketstage.fal_transport import FalTransport, FalTransportError, download_artifact


class Handle:
    request_id = "request-123"


class Status:
    status = "running"


class FakeSDK:
    def __init__(self):
        self.calls = []

    def upload_file(self, path):
        self.calls.append(("upload", path))
        return "https://files.fal.media/input.mp4"

    def submit(self, model, *, arguments):
        self.calls.append(("submit", model, arguments))
        return Handle()

    def status(self, model, request_id, *, with_logs):
        self.calls.append(("status", model, request_id, with_logs))
        return Status()

    def result(self, model, request_id):
        self.calls.append(("result", model, request_id))
        return {"ok": True}


class Response(io.BytesIO):
    def __init__(self, body, url="https://cdn.fal.media/a.bin", length=None):
        super().__init__(body)
        self._url = url
        self.headers = {} if length is None else {"Content-Length": str(length)}

    def geturl(self):
        return self._url


class Opener:
    def __init__(self, response):
        self.response = response
        self.request = None

    def open(self, request, timeout=None):
        self.request = request
        self.timeout = timeout
        return self.response


class SubmitOpener(Opener):
    def __init__(self):
        super().__init__(Response(b'{"request_id":"request-123"}', url="https://queue.fal.run/fal-ai/sam2/video"))


class TransportTests(unittest.TestCase):
    def test_sdk_operations_and_signatures(self):
        sdk = FakeSDK()
        submit_opener = SubmitOpener()
        transport = FalTransport(key="credential", sdk=sdk, submit_opener=submit_opener)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "clip.mp4"
            source.write_bytes(b"video")
            self.assertEqual(transport.upload(source), "https://files.fal.media/input.mp4")
        self.assertEqual(transport.status("model", "request-123"), "RUNNING")
        self.assertEqual(transport.result("model", "request-123"), {"ok": True})
        self.assertFalse(transport.cancel("model", "request-123"))
        self.assertEqual(transport.submit("fal-ai/sam2/video", {"x": 1}), "request-123")
        self.assertEqual(submit_opener.timeout, 30)
        self.assertEqual(submit_opener.request.get_header("Authorization"), "Key credential")
        self.assertNotIn(("submit", "fal-ai/sam2/video", {"x": 1}), sdk.calls)

    def test_provider_errors_are_sanitized(self):
        class BadSDK:
            def result(self, model, request_id):
                raise RuntimeError("secret key and raw response body")

        with self.assertRaisesRegex(FalTransportError, r"fal result failed \(RuntimeError\)") as caught:
            FalTransport(sdk=BadSDK()).result("model", "id")
        self.assertNotIn("secret", str(caught.exception))


class DownloadTests(unittest.TestCase):
    def test_bounded_atomic_download_has_no_authorization_header(self):
        opener = Opener(Response(b"artifact"))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "artifact.bin"
            self.assertEqual(download_artifact("https://fal.media/a", target, opener=opener), target)
            self.assertEqual(target.read_bytes(), b"artifact")
            self.assertIsNone(opener.request.get_header("Authorization"))
            self.assertEqual(opener.timeout, 30)
            with self.assertRaises(FileExistsError):
                download_artifact("https://fal.media/a", target, opener=opener)

    def test_rejects_bad_hosts_redirects_and_oversized_content(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "artifact.bin"
            with self.assertRaises(ValueError):
                download_artifact("https://evil.example/a", target)
            with self.assertRaises(FalTransportError):
                download_artifact(
                    "https://fal.media/a", target,
                    opener=Opener(Response(b"x", url="https://evil.example/a")),
                )
            with self.assertRaises(FalTransportError):
                download_artifact(
                    "https://fal.media/a", target,
                    max_bytes=4, opener=Opener(Response(b"12345")),
                )
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_rejects_ip_literals_and_declared_oversize(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "artifact.bin"
            with self.assertRaises(ValueError):
                download_artifact("https://127.0.0.1/a", target)
            with self.assertRaises(FalTransportError):
                download_artifact(
                    "https://fal.ai/a", target,
                    max_bytes=4, opener=Opener(Response(b"x", length=5)),
                )


if __name__ == "__main__":
    unittest.main()
