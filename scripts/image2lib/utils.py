from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "secret",
    "signature",
}
_URL_KEYS = {"url", "image_url", "download_url", "signed_url"}


def safe_slug(text: str, max_length: int = 48) -> str:
    text = text.strip()
    # Remove Windows-unsafe chars and collapse whitespace, keep CJK + alphanumeric + hyphens
    text = re.sub(r'[\\/:*?"<>|\n\r\t]+', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:max_length].rstrip("-") or "image-run"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_key_value(items: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=value for --extra-param, got {item!r}")
        key, raw = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("An --extra-param key cannot be empty.")
        raw = raw.strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        result[key] = value
    return result


def merge_extra_params(
    base: dict[str, Any],
    items: Iterable[str],
    *,
    reserved: Iterable[str] = (),
) -> dict[str, Any]:
    extras = parse_key_value(items)
    blocked = {str(key).lower() for key in reserved}
    collisions = sorted(key for key in extras if key.lower() in blocked or key in base)
    if collisions:
        raise ValueError(
            "--extra-param cannot override standard request fields: " + ", ".join(collisions)
        )
    return {**base, **extras}


def _redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<url omitted>"
    if parts.scheme not in {"http", "https"}:
        return "<url omitted>"
    # Preserve only origin and path for diagnostics. Query strings and fragments often contain signatures.
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def redact(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _SECRET_KEYS:
                out[str(key)] = "***REDACTED***"
            elif normalized in _URL_KEYS and isinstance(child, str):
                out[str(key)] = _redact_url(child)
            else:
                out[str(key)] = redact(child, str(key))
        return out
    if isinstance(value, list):
        return [redact(v, parent_key) for v in value]
    if isinstance(value, str) and parent_key.lower() in {"b64_json", "image_base64", "base64"}:
        return f"<base64 omitted: {len(value)} chars>"
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
