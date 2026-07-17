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


class _ShouldFallback(Exception):
    """Internal signal: this provider failed with a fallback-eligible condition,
    so the next provider in the chain should be tried."""

    def __init__(self, status_code: int | None, reason: str, provider: str):
        self.status_code = status_code
        self.reason = reason
        self.provider = provider
        super().__init__(reason)


@dataclass(slots=True)
class APIResult:
    payload: dict[str, Any]
    request_id: str | None
    status_code: int
    attempts: int
    provider_name: str | None = None

    def safe_summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status_code": self.status_code,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "payload": redact(self.payload),
        }
        if self.provider_name is not None:
            out["provider"] = self.provider_name
        return out


class ImageAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ProviderChainError(ImageAPIError):
    """All providers in the chain failed."""

    def __init__(self, message: str, attempts: list[dict[str, Any]]):
        super().__init__(message, status_code=None)
        self.attempts = attempts


class ImageAPIClient:
    def __init__(self, config: APIConfig):
        self.config = config
        primary = config.primary_profile
        self._primary_headers = {
            "Authorization": f"Bearer {primary.api_key}",
            "User-Agent": f"image2-api/{__version__}",
            **primary.extra_headers,
        }
        self.headers = dict(self._primary_headers)
        self.timeout = httpx.Timeout(primary.timeout)
        # Decide mode: chain fallback only when there are 2+ profiles.
        self._chain_mode = (
            config.chain is not None and len(config.chain.profiles) >= 2
        )

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
        """Route to single-provider or chain-with-fallback path."""
        if not self._chain_mode:
            return self._request_single(method, url, **kwargs)
        return self._request_chain(method, url, **kwargs)

    def _request_single(self, method: str, url: str, **kwargs: Any) -> APIResult:
        """Original single-provider path with internal retries."""
        last_exc: Exception | None = None
        request_headers = {**self.headers, **kwargs.pop("headers", {})}
        max_retries = self.config.primary_profile.max_retries
        verify_ssl = self.config.primary_profile.verify_ssl
        with httpx.Client(timeout=self.timeout, verify=verify_ssl, follow_redirects=True) as client:
            for attempt in range(max_retries + 1):
                try:
                    response = client.request(method, url, headers=request_headers, **kwargs)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        raise ImageAPIError(f"Network failure after {attempt + 1} attempts: {exc}") from exc
                    self._sleep(attempt)
                    continue

                if response.status_code in _RETRY_STATUS and attempt < max_retries:
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

    def _request_chain(self, method: str, url: str, **kwargs: Any) -> APIResult:
        """Try each provider in order; fall back when response signals so."""
        chain = self.config.chain
        assert chain is not None
        attempts_log: list[dict[str, Any]] = []
        for index, profile in enumerate(chain.profiles):
            is_last = index == len(chain.profiles) - 1
            try:
                return self._try_one_provider(
                    profile, method, url, chain=chain, **kwargs
                )
            except _ShouldFallback as exc:
                attempts_log.append(
                    {
                        "provider": profile.name,
                        "status_code": exc.status_code,
                        "reason": exc.reason,
                        "attempts": 1,
                    }
                )
                continue
            except ImageAPIError as exc:
                # Non-fallback terminal error (e.g. 400, 401, decode failure).
                # Don't try other providers — they won't fix a malformed request.
                attempts_log.append(
                    {
                        "provider": profile.name,
                        "status_code": getattr(exc, "status_code", None),
                        "reason": str(exc),
                        "attempts": 1,
                    }
                )
                # If this was the last provider, surface; otherwise surface
                # the terminal error without falling back.
                raise
        # All providers exhausted — surface a chain error.
        names = " -> ".join(p.name for p in chain.profiles)
        details = "; ".join(
            f"{a['provider']}(HTTP {a['status_code']}): {a['reason']}"
            for a in attempts_log
        )
        raise ProviderChainError(
            f"All {len(chain.profiles)} providers failed [{names}]: {details}",
            attempts=attempts_log,
        )

    def _try_one_provider(
        self,
        profile: ProviderProfile,
        method: str,
        url: str,
        *,
        chain: ProviderChain,
        **kwargs: Any,
    ) -> APIResult:
        """Send the request to a single provider's endpoint with internal retries.

        Raises _ShouldFallback when the response indicates the chain should
        move to the next provider. Raises ImageAPIError for terminal errors
        that should not trigger fallback.
        """
        # Rebuild URL against this provider's endpoint when caller passed
        # the original endpoint. Generate/edit endpoints differ per provider.
        provider_url = self._endpoint_for_profile(url, profile)
        headers = {
            "Authorization": f"Bearer {profile.api_key}",
            "User-Agent": f"image2-api/{__version__}",
            **profile.extra_headers,
            **kwargs.pop("headers", {}),
        }
        last_exc: Exception | None = None
        attempts = 0
        with httpx.Client(
            timeout=httpx.Timeout(profile.timeout),
            verify=profile.verify_ssl,
            follow_redirects=True,
        ) as http_client:
            for attempt in range(profile.max_retries + 1):
                attempts += 1
                try:
                    response = http_client.request(method, provider_url, headers=headers, **kwargs)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                    if attempt >= profile.max_retries:
                        if chain.fallback_on_network_error:
                            raise _ShouldFallback(
                                status_code=None,
                                reason=f"network failure after {attempt + 1} attempts: {exc}",
                                provider=profile.name,
                            ) from exc
                        raise ImageAPIError(
                            f"Network failure after {attempt + 1} attempts: {exc}"
                        ) from exc
                    self._sleep(attempt)
                    continue

                if response.status_code in _RETRY_STATUS and attempt < profile.max_retries:
                    self._sleep(attempt, response)
                    continue

                # Decide: terminal error, fallback, or success
                if response.is_error:
                    payload = self._decode_json(response)
                    message = self._error_message(payload, response.status_code)
                    if response.status_code in chain.fallback_status:
                        raise _ShouldFallback(
                            status_code=response.status_code,
                            reason=message,
                            provider=profile.name,
                        )
                    raise ImageAPIError(message, status_code=response.status_code, body=payload)

                payload = self._decode_json(response)
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                return APIResult(
                    payload,
                    request_id,
                    response.status_code,
                    attempts,
                    provider_name=profile.name,
                )

        if chain.fallback_on_network_error and last_exc is not None:
            raise _ShouldFallback(
                status_code=None,
                reason=f"network failure: {last_exc}",
                provider=profile.name,
            ) from last_exc
        raise ImageAPIError(f"Request failed: {last_exc}")

    @staticmethod
    def _endpoint_for_profile(original_url: str, profile: ProviderProfile) -> str:
        """Map the original endpoint URL to the equivalent endpoint on a
        different provider. We compare against both providers' endpoints so
        that callers passing `generation_endpoint` or `edit_endpoint` get
        the correct URL even when the chain swaps providers.
        """
        # If the URL doesn't match a known endpoint pattern, pass it through.
        if "/images/generations" in original_url or "/images/edits" in original_url:
            if "/images/generations" in original_url:
                return profile.generation_endpoint()
            if "/images/edits" in original_url:
                return profile.edit_endpoint()
        return original_url

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
