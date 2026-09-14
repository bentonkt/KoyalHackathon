"""Small fal SDK transport and bounded artifact downloader."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import importlib
import ipaddress
import json
import os
import tempfile
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class FalTransportError(RuntimeError):
    """A sanitized provider or download failure (never includes response bodies)."""


def _https_handler():
    import certifi
    return HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))


class FalTransport:
    def __init__(
        self, key: str | None = None, sdk: object | None = None, submit_opener: object | None = None
    ):
        self._key = key or os.environ.get("FAL_KEY")
        self._sdk = sdk
        self._submit_opener = submit_opener
        self._client_instance: object | None = None

    def _client(self) -> object:
        if self._client_instance is not None:
            return self._client_instance
        sdk = self._sdk or importlib.import_module("fal_client")
        client_type = getattr(sdk, "SyncClient", None)
        if client_type is None:
            self._client_instance = sdk
        else:
            if not self._key:
                raise FalTransportError("fal credentials are not configured")
            self._client_instance = client_type(key=self._key)
        return self._client_instance

    @staticmethod
    def _call(operation: str, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as exc:
            raise FalTransportError(f"fal {operation} failed ({type(exc).__name__})") from None

    def upload(self, path: str | Path) -> str:
        source = Path(path)
        if not source.is_file():
            raise ValueError("upload path must be an existing file")
        client = self._client()
        value = self._call("upload", getattr(client, "upload_file"), str(source))
        if not isinstance(value, str) or not value:
            raise FalTransportError("fal upload returned an invalid URL")
        return value

    def submit(self, model: str, input: Mapping[str, object]) -> str:
        if model not in {"fal-ai/sam2/video", "fal-ai/depth-anything-video"} or not isinstance(input, Mapping):
            raise ValueError("model and input are required")
        if not self._key:
            raise FalTransportError("fal credentials are not configured")
        request = Request(
            f"https://queue.fal.run/{model}",
            data=json.dumps(dict(input), separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Key {self._key}", "Content-Type": "application/json"},
        )
        opener = self._submit_opener or build_opener(_https_handler(), _NoRedirects())
        try:
            with opener.open(request, timeout=30) as response:
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise FalTransportError("fal submit returned an oversized response")
                value = json.loads(body)
        except FalTransportError:
            raise
        except Exception as exc:
            raise FalTransportError(f"fal submit failed ({type(exc).__name__})") from None
        request_id = value.get("request_id") if isinstance(value, Mapping) else None
        if not isinstance(request_id, str) or not request_id:
            raise FalTransportError("fal submit returned an invalid request id")
        return request_id

    def status(self, model: str, request_id: str) -> str:
        response = self._call(
            "status", getattr(self._client(), "status"), model, request_id, with_logs=False
        )
        state = getattr(response, "status", None) or type(response).__name__
        return str(state).upper()

    def result(self, model: str, request_id: str) -> dict[str, object]:
        value = self._call("result", getattr(self._client(), "result"), model, request_id)
        if not isinstance(value, Mapping):
            raise FalTransportError("fal result returned an invalid payload")
        return dict(value)

    def cancel(self, model: str, request_id: str) -> bool:
        function = getattr(self._client(), "cancel", None)
        if function is None:
            return False
        self._call("cancel", function, model, request_id)
        return True


def _validate_artifact_url(url: str) -> str:
    if not isinstance(url, str):
        raise ValueError("artifact URL must be a string")
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("artifact URL cannot use an IP literal")
    allowed = host in {"fal.ai", "fal.media"} or host.endswith(".fal.ai") or host.endswith(".fal.media")
    if parsed.scheme != "https" or not allowed or parsed.username is not None:
        raise ValueError("artifact URL must use HTTPS on an allowed fal host")
    return url


class _SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url = _validate_artifact_url(urljoin(req.full_url, newurl))
        return Request(safe_url, method="GET", headers={"User-Agent": "PocketStage/0"})


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact(
    url: str,
    destination: str | Path,
    *,
    max_bytes: int = 128 * 1024 * 1024,
    opener: object | None = None,
) -> Path:
    """Stream an allowlisted public artifact and publish atomically without overwrite."""
    safe_url = _validate_artifact_url(url)
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    target = Path(destination)
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    open_url = opener or build_opener(_https_handler(), _SafeRedirects())
    temp_path: Path | None = None
    try:
        request = Request(safe_url, method="GET", headers={"User-Agent": "PocketStage/0"})
        response = open_url.open(request, timeout=30)
        with response:
            _validate_artifact_url(response.geturl())
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                raise FalTransportError("artifact exceeds download limit")
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as out:
                temp_path = Path(out.name)
                total = 0
                while True:
                    chunk = response.read(min(64 * 1024, max_bytes - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise FalTransportError("artifact exceeds download limit")
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
        os.link(temp_path, target)
        temp_path.unlink()
        return target
    except FileExistsError:
        raise
    except (HTTPError, URLError, OSError, ValueError, FalTransportError) as exc:
        if isinstance(exc, FalTransportError):
            raise
        raise FalTransportError(f"artifact download failed ({type(exc).__name__})") from None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
