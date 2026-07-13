from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:
    from dotenv import load_dotenv
except ImportError:  # doctor.py reports the missing optional dependency.
    load_dotenv = None

MODEL_FAMILIES = ("auto", "gpt-image-2", "gpt-image-1.5", "generic")


def _load_env_files() -> None:
    if load_dotenv is None:
        return
    skill_root = Path(__file__).resolve().parents[2]
    candidates = [Path.cwd() / ".env", skill_root / ".env"]
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path not in seen and path.is_file():
            load_dotenv(path, override=False)
            seen.add(path)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def normalize_base_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("The API base URL is empty.")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Invalid API base URL: {value!r}")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def build_endpoint(base_url: str, kind: str, override: str | None = None) -> str:
    if override:
        return normalize_base_url(override)
    base = normalize_base_url(base_url)
    if kind == "generation":
        suffix = "/images/generations"
        if base.endswith(suffix):
            return base
        if base.endswith("/images/edits"):
            base = base[: -len("/images/edits")]
    elif kind == "edit":
        suffix = "/images/edits"
        if base.endswith(suffix):
            return base
        if base.endswith("/images/generations"):
            base = base[: -len("/images/generations")]
    else:
        raise ValueError(f"Unknown endpoint kind: {kind}")
    return base + suffix


def parse_extra_headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("IMAGE_API_EXTRA_HEADERS must be a JSON object.") from exc
    if not isinstance(obj, dict):
        raise ValueError("IMAGE_API_EXTRA_HEADERS must be a JSON object.")
    result: dict[str, str] = {}
    for key, value in obj.items():
        if value is None:
            continue
        result[str(key)] = str(value)
    return result


def resolve_model_family(model: str, configured: str | None = None) -> str:
    family = (configured or "auto").strip().lower()
    if family not in MODEL_FAMILIES:
        raise ValueError(
            f"Unknown model family {configured!r}. Choose from: {', '.join(MODEL_FAMILIES)}."
        )
    if family != "auto":
        return family
    normalized = model.strip().lower()
    if normalized == "gpt-image-2" or normalized.startswith("gpt-image-2-"):
        return "gpt-image-2"
    if normalized in {"gpt-image-1.5", "gpt-image-1"} or normalized.startswith(
        ("gpt-image-1.5-", "gpt-image-1-")
    ):
        return "gpt-image-1.5"
    return "generic"


@dataclass(slots=True)
class APIConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-2"
    model_family: str = "auto"
    generations_url: str | None = None
    edits_url: str | None = None
    timeout: float = 180.0
    max_retries: int = 3
    verify_ssl: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
        model_family: str | None = None,
        generations_url: str | None = None,
        edits_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> "APIConfig":
        _load_env_files()
        api_key = os.getenv("IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        resolved_model = (model or os.getenv("IMAGE_API_MODEL") or "gpt-image-2").strip()
        return cls(
            api_key=api_key.strip(),
            base_url=normalize_base_url(
                base_url or os.getenv("IMAGE_API_BASE_URL") or "https://api.openai.com/v1"
            ),
            model=resolved_model,
            model_family=(
                model_family or os.getenv("IMAGE_API_MODEL_FAMILY") or "auto"
            ).strip(),
            generations_url=generations_url or os.getenv("IMAGE_API_GENERATIONS_URL") or None,
            edits_url=edits_url or os.getenv("IMAGE_API_EDITS_URL") or None,
            timeout=timeout if timeout is not None else _env_float("IMAGE_API_TIMEOUT", 180.0),
            max_retries=(
                max_retries
                if max_retries is not None
                else _env_int("IMAGE_API_MAX_RETRIES", 3)
            ),
            verify_ssl=_env_bool("IMAGE_API_VERIFY_SSL", True),
            extra_headers=parse_extra_headers(os.getenv("IMAGE_API_EXTRA_HEADERS")),
        )

    @property
    def resolved_model_family(self) -> str:
        return resolve_model_family(self.model, self.model_family)

    @property
    def is_gpt_image_2(self) -> bool:
        return self.resolved_model_family == "gpt-image-2"

    def validate(self, require_key: bool = True) -> list[str]:
        warnings: list[str] = []
        if require_key and not self.api_key:
            raise ValueError(
                "No API key found. Set IMAGE_API_KEY (preferred) or OPENAI_API_KEY."
            )
        if not self.model:
            raise ValueError("The image model name is empty.")
        _ = self.resolved_model_family
        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if not self.base_url.endswith("/v1") and not (
            self.generations_url or self.edits_url
        ):
            warnings.append(
                "The base URL does not end in /v1. That may be correct for the relay, "
                "but 404 errors often mean the API prefix is missing."
            )
        if self.model_family == "auto" and self.resolved_model_family == "generic":
            warnings.append(
                "The relay model alias is not recognized. Set IMAGE_API_MODEL_FAMILY=gpt-image-2 "
                "when the alias maps to GPT Image 2 so model-specific validation remains active."
            )
        if not self.verify_ssl:
            warnings.append("TLS certificate verification is disabled.")
        return warnings

    @property
    def generation_endpoint(self) -> str:
        return build_endpoint(self.base_url, "generation", self.generations_url)

    @property
    def edit_endpoint(self) -> str:
        return build_endpoint(self.base_url, "edit", self.edits_url)

    def safe_dict(self) -> dict[str, Any]:
        return {
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model,
            "model_family": self.resolved_model_family,
            "generation_endpoint": self.generation_endpoint,
            "edit_endpoint": self.edit_endpoint,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "verify_ssl": self.verify_ssl,
            "extra_header_names": sorted(self.extra_headers),
        }
