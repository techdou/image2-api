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


def _find_skill_root() -> Path:
    """Walk up from this file to find the skill root (contains SKILL.md)."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "SKILL.md").is_file():
            return parent
    return current.parents[2]


def _resolve_skill_root() -> Path:
    """Find the real skill root that contains .env.

    Problem: on Windows, .claude/skills/ may be a plain directory copy (not a
    symlink/junction), so the skill root found by walking up from __file__ has
    no .env (it was gitignored). We check multiple known locations.
    """
    import os

    here = _find_skill_root()

    # If this skill root has .env, use it directly
    if (here / ".env").is_file():
        return here

    # Try common alternative locations where the real skill installation lives
    home = Path.home()
    candidates = [
        home / ".agents" / "skills" / "image2-api",
        home / ".claude" / "skills" / "image2-api",
        here,  # fallback to the discovered root
    ]
    for candidate in candidates:
        if (candidate / ".env").is_file():
            return candidate

    return here


def _load_env_files() -> None:
    if load_dotenv is None:
        return
    skill_root = _resolve_skill_root()
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
class ProviderProfile:
    """Configuration for a single upstream image API provider.

    Used as a building block of ProviderChain. Each provider is fully
    self-contained — no inheritance between providers — so the .env format
    stays simple and explicit.
    """

    name: str
    api_key: str
    base_url: str
    model: str = "gpt-image-2"
    model_family: str = "auto"
    generations_url: str | None = None
    edits_url: str | None = None
    timeout: float = 180.0
    max_retries: int = 2
    verify_ssl: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)

    def resolved_model_family(self) -> str:
        return resolve_model_family(self.model, self.model_family)

    def generation_endpoint(self) -> str:
        return build_endpoint(self.base_url, "generation", self.generations_url)

    def edit_endpoint(self) -> str:
        return build_endpoint(self.base_url, "edit", self.edits_url)

    def safe_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model,
            "model_family": self.resolved_model_family(),
            "generation_endpoint": self.generation_endpoint(),
            "edit_endpoint": self.edit_endpoint(),
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "verify_ssl": self.verify_ssl,
            "extra_header_names": sorted(self.extra_headers),
        }


@dataclass(slots=True)
class ProviderChain:
    """Ordered list of providers with fallback policy.

    The chain is consulted in order; a provider whose response signals a
    fallback-eligible error (status code in fallback_status, or a network
    error when fallback_on_network_error is true) causes the next provider
    to be tried. All providers exhausting without success raises
    ProviderChainError.
    """

    profiles: list[ProviderProfile]
    fallback_status: set[int] = field(default_factory=lambda: {429, 500, 502, 503, 504})
    fallback_on_network_error: bool = True  # dataclass default

    @classmethod
    def from_env(cls) -> "ProviderChain | None":
        """Parse IMAGE_API_PROVIDERS from environment. Returns None if not set,
        meaning the legacy single-provider code path should be used.
        """
        raw = os.getenv("IMAGE_API_PROVIDERS", "").strip()
        if not raw:
            return None
        names = [n.strip() for n in raw.split(",") if n.strip()]
        if not names:
            return None
        # Validate that we can build all profiles before raising on a later one
        profiles: list[ProviderProfile] = []
        for name in names:
            profiles.append(_profile_from_env(name))
        fallback_status_raw = os.getenv("IMAGE_API_FALLBACK_STATUS", "429,500,502,503,504,network_error")
        fallback_status: set[int] = set()
        fallback_on_network_error = False
        for part in fallback_status_raw.split(","):
            token = part.strip().lower()
            if not token:
                continue
            if token == "network_error":
                fallback_on_network_error = True
                continue
            try:
                fallback_status.add(int(token))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid IMAGE_API_FALLBACK_STATUS value {token!r}; "
                    "expected an integer status code or 'network_error'."
                ) from exc
        return cls(
            profiles=profiles,
            fallback_status=fallback_status,
            fallback_on_network_error=fallback_on_network_error,
        )

    def safe_dict(self) -> dict[str, Any]:
        return {
            "providers": [p.safe_dict() for p in self.profiles],
            "fallback_status": sorted(self.fallback_status),
            "fallback_on_network_error": self.fallback_on_network_error,
        }


def _profile_from_env(name: str) -> ProviderProfile:
    """Build a ProviderProfile by reading IMAGE_API_<NAME>_* environment variables."""
    upper = name.upper()
    base_url_raw = os.getenv(f"IMAGE_API_{upper}_BASE_URL", "").strip()
    if not base_url_raw:
        raise ValueError(
            f"Provider {name!r} is listed in IMAGE_API_PROVIDERS but "
            f"IMAGE_API_{upper}_BASE_URL is not set."
        )
    api_key = os.getenv(f"IMAGE_API_{upper}_KEY", "").strip()
    return ProviderProfile(
        name=name,
        api_key=api_key,
        base_url=normalize_base_url(base_url_raw),
        model=os.getenv(f"IMAGE_API_{upper}_MODEL", "gpt-image-2").strip(),
        model_family=os.getenv(f"IMAGE_API_{upper}_MODEL_FAMILY", "auto").strip(),
        generations_url=os.getenv(f"IMAGE_API_{upper}_GENERATIONS_URL") or None,
        edits_url=os.getenv(f"IMAGE_API_{upper}_EDITS_URL") or None,
        timeout=_env_float(f"IMAGE_API_{upper}_TIMEOUT", 180.0),
        max_retries=_env_int(f"IMAGE_API_{upper}_MAX_RETRIES", 2),
        verify_ssl=_env_bool(f"IMAGE_API_{upper}_VERIFY_SSL", True),
        extra_headers=parse_extra_headers(os.getenv(f"IMAGE_API_{upper}_EXTRA_HEADERS")),
    )


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
    chain: ProviderChain | None = None

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
        chain = ProviderChain.from_env()
        if chain is not None:
            primary = chain.profiles[0]
            return cls(
                api_key=primary.api_key,
                base_url=primary.base_url,
                model=primary.model,
                model_family=primary.model_family,
                generations_url=primary.generations_url,
                edits_url=primary.edits_url,
                timeout=primary.timeout,
                max_retries=primary.max_retries,
                verify_ssl=primary.verify_ssl,
                extra_headers=dict(primary.extra_headers),
                chain=chain,
            )
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

    @property
    def primary_profile(self) -> ProviderProfile:
        """Return the active primary provider as a ProviderProfile.

        Single-provider mode (legacy) constructs an ad-hoc profile so callers
        can treat both modes uniformly.
        """
        if self.chain is not None:
            return self.chain.profiles[0]
        return ProviderProfile(
            name="default",
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            model_family=self.model_family,
            generations_url=self.generations_url,
            edits_url=self.edits_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            verify_ssl=self.verify_ssl,
            extra_headers=dict(self.extra_headers),
        )

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
        out: dict[str, Any] = {
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
        if self.chain is not None:
            out["chain"] = self.chain.safe_dict()
        return out
