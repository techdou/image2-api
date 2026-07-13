from __future__ import annotations

import base64
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from .config import APIConfig
from .outputs import media_type_for
from .utils import redact
from .version import __version__

_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass(slots=True)
class APIResult:
    payload: dict[str, Any]
    request_id: str | None
    status_code: int
    attempts: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "payload": redact(self.payload),
        }


class ImageAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ImageAPIClient:
    def __init__(self, config: APIConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "User-Agent": f"image2-api/{__version__}",
            **config.extra_headers,
        }
        self.timeout = httpx.Timeout(config.timeout)

    def _sleep(self, attempt: int, response: httpx.Response | None = None) -> None:
        retry_after: float | None = None
        if response is not None:
            raw = response.headers.get("retry-after")
            if raw:
                try:
                    retry_after = float(raw)
                except ValueError:
                    retry_after = None
        delay = retry_after if retry_after is not None else min(30.0, (2**attempt) + random.random())
        time.sleep(max(0.0, delay))

    @staticmethod
    def _decode_json(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except json.JSONDecodeError as exc:
            snippet = response.text[:500]
            raise ImageAPIError(
                f"API returned non-JSON content (HTTP {response.status_code}): {snippet}",
                status_code=response.status_code,
                body=snippet,
            ) from exc
        if not isinstance(value, dict):
            raise ImageAPIError(
                f"API returned a JSON value that is not an object: {type(value).__name__}",
                status_code=response.status_code,
                body=value,
            )
        return value

    @staticmethod
    def _error_message(payload: dict[str, Any], status_code: int) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or json.dumps(error, ensure_ascii=False)
        elif error:
            message = str(error)
        else:
            message = payload.get("message") or payload.get("detail") or json.dumps(payload, ensure_ascii=False)[:700]
        return f"Image API request failed with HTTP {status_code}: {message}"

    def _request(self, method: str, url: str, **kwargs: Any) -> APIResult:
        last_exc: Exception | None = None
        request_headers = {**self.headers, **kwargs.pop("headers", {})}
        with httpx.Client(timeout=self.timeout, verify=self.config.verify_ssl, follow_redirects=True) as client:
            for attempt in range(self.config.max_retries + 1):
                try:
                    response = client.request(method, url, headers=request_headers, **kwargs)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    if attempt >= self.config.max_retries:
                        raise ImageAPIError(f"Network failure after {attempt + 1} attempts: {exc}") from exc
                    self._sleep(attempt)
                    continue

                if response.status_code in _RETRY_STATUS and attempt < self.config.max_retries:
                    self._sleep(attempt, response)
                    continue

                payload = self._decode_json(response)
                if response.is_error:
                    raise ImageAPIError(
                        self._error_message(payload, response.status_code),
                        status_code=response.status_code,
                        body=payload,
                    )
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                return APIResult(payload, request_id, response.status_code, attempt + 1)

        raise ImageAPIError(f"Request failed: {last_exc}")

    def generate(self, payload: dict[str, Any]) -> APIResult:
        return self._request(
            "POST",
            self.config.generation_endpoint,
            json=payload,
            headers={**self.headers, "Content-Type": "application/json"},
        )

    def edit(
        self,
        fields: dict[str, Any],
        image_paths: list[Path],
        mask_path: Path | None = None,
    ) -> APIResult:
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for path in image_paths:
            files.append(("image[]", (path.name, path.read_bytes(), media_type_for(path))))
        if mask_path:
            files.append(("mask", (mask_path.name, mask_path.read_bytes(), "image/png")))
        data: dict[str, str] = {}
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, (dict, list, bool)):
                data[key] = json.dumps(value, ensure_ascii=False)
            else:
                data[key] = str(value)
        return self._request("POST", self.config.edit_endpoint, data=data, files=files)

    def download(self, url: str) -> bytes:
        if url.startswith("data:"):
            try:
                header, encoded = url.split(",", 1)
            except ValueError as exc:
                raise ImageAPIError("Malformed data URL in image response.") from exc
            if ";base64" not in header:
                raise ImageAPIError("Only base64 data URLs are supported.")
            return base64.b64decode(encoded)

        absolute = urljoin(self.config.base_url + "/", url)
        scheme = urlsplit(absolute).scheme.lower()
        if scheme not in {"http", "https"}:
            raise ImageAPIError(f"Unsupported image URL scheme: {scheme or 'missing'}")
        base_host = urlsplit(self.config.base_url).netloc
        target_host = urlsplit(absolute).netloc
        headers = {"User-Agent": f"image2-api/{__version__}"}
        if target_host == base_host:
            headers.update(self.headers)
        with httpx.Client(timeout=self.timeout, verify=self.config.verify_ssl, follow_redirects=True) as client:
            response = client.get(absolute, headers=headers)
            response.raise_for_status()
            return response.content


def extract_image_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("data")
    if not isinstance(candidates, list):
        candidates = payload.get("images")
    if not isinstance(candidates, list):
        single = payload.get("image")
        candidates = [single] if isinstance(single, dict) else []

    entries: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, str):
            if item.startswith("http") or item.startswith("data:"):
                entries.append({"url": item})
            else:
                entries.append({"b64_json": item})
            continue
        if not isinstance(item, dict):
            continue
        b64_value = item.get("b64_json") or item.get("image_base64") or item.get("base64")
        url_value = item.get("url") or item.get("image_url")
        if b64_value:
            entries.append({**item, "b64_json": b64_value})
        elif url_value:
            entries.append({**item, "url": url_value})
    if not entries:
        raise ImageAPIError(
            "The API response contained no supported image entry under data/images. "
            "This relay may use an asynchronous or non-OpenAI response schema.",
            body=payload,
        )
    return entries


def entry_to_bytes(client: ImageAPIClient, entry: dict[str, Any]) -> bytes:
    encoded = entry.get("b64_json")
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ImageAPIError("The image base64 payload is invalid.") from exc
    url = entry.get("url")
    if url:
        return client.download(str(url))
    raise ImageAPIError("Image entry has neither b64_json nor url.")
