from __future__ import annotations

from dataclasses import dataclass

MODEL_FAMILIES = ("auto", "gpt-image-2.5", "gpt-image-2", "gpt-image-1.5", "generic")
QUALITY_CHOICES = ("low", "medium", "high", "xhigh", "max", "auto")
STANDARD_GPT_IMAGE_SIZES = frozenset({"1024x1024", "1536x1024", "1024x1536"})


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    family: str
    qualities: frozenset[str]
    flexible_size: bool
    transparent_background: bool
    transparent_preview: bool = False
    omit_input_fidelity: bool = False
    experimental_over_pixels: int | None = None


_CAPABILITIES = {
    "gpt-image-2.5": ModelCapabilities(
        family="gpt-image-2.5",
        qualities=frozenset({"low", "medium", "high", "xhigh", "max", "auto"}),
        flexible_size=True,
        transparent_background=True,
        experimental_over_pixels=3_686_400,
    ),
    "gpt-image-2": ModelCapabilities(
        family="gpt-image-2",
        qualities=frozenset({"low", "medium", "high", "auto"}),
        flexible_size=True,
        transparent_background=True,
        transparent_preview=True,
        omit_input_fidelity=True,
        experimental_over_pixels=3_686_400,
    ),
    "gpt-image-1.5": ModelCapabilities(
        family="gpt-image-1.5",
        qualities=frozenset({"low", "medium", "high", "auto"}),
        flexible_size=False,
        transparent_background=True,
    ),
    # Generic relays are intentionally permissive for request values while
    # emitting portability warnings elsewhere. Provider aliases should set an
    # explicit family whenever the upstream model is known.
    "generic": ModelCapabilities(
        family="generic",
        qualities=frozenset(QUALITY_CHOICES),
        flexible_size=False,
        transparent_background=True,
    ),
}


def resolve_model_family(model: str, configured: str | None = None) -> str:
    family = (configured or "auto").strip().lower()
    if family not in MODEL_FAMILIES:
        raise ValueError(
            f"Unknown model family {configured!r}. Choose from: {', '.join(MODEL_FAMILIES)}."
        )
    if family != "auto":
        return family

    normalized = model.strip().lower()
    if normalized.startswith(("gpt-image-2.5-flare", "gpt-image-2.5-sunburst")):
        return "gpt-image-2.5"
    if normalized == "gpt-image-2" or normalized.startswith("gpt-image-2-"):
        return "gpt-image-2"
    if normalized in {"gpt-image-1.5", "gpt-image-1"} or normalized.startswith(
        ("gpt-image-1.5-", "gpt-image-1-")
    ):
        return "gpt-image-1.5"
    return "generic"


def model_capabilities(model: str, configured_family: str | None = None) -> ModelCapabilities:
    family = resolve_model_family(model, configured_family)
    return _CAPABILITIES[family]


def is_gpt_image_25_model(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith(("gpt-image-2.5-flare", "gpt-image-2.5-sunburst"))


def model_role(model: str) -> str | None:
    normalized = model.strip().lower()
    if normalized.startswith("gpt-image-2.5-flare"):
        return "speed"
    if normalized.startswith("gpt-image-2.5-sunburst"):
        return "quality"
    return None
