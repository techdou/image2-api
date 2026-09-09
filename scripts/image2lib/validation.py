from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

from .capabilities import model_capabilities
from .utils import sha256_bytes

MAX_INPUT_IMAGES = 16
MAX_INPUT_IMAGE_BYTES = 50 * 1024 * 1024
MAX_MASK_BYTES = 50 * 1024 * 1024


@dataclass(slots=True)
class ImageInfo:
    filename: str
    format: str
    width: int
    height: int
    mode: str
    bytes: int
    sha256: str
    has_alpha: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_image_bytes(data: bytes, filename: str = "image") -> ImageInfo:
    if len(data) < 256:
        raise ValueError(f"{filename}: returned image is implausibly small ({len(data)} bytes).")
    prefix = data[:256].lstrip().lower()
    if prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html"):
        raise ValueError(f"{filename}: the API returned an HTML page instead of an image.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            width, height = image.size
            fmt = (image.format or "unknown").lower()
            mode = image.mode
            has_alpha = "A" in image.getbands() or "transparency" in image.info
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"{filename}: invalid or corrupted image bytes: {exc}") from exc
    if width < 64 or height < 64:
        raise ValueError(f"{filename}: image dimensions are too small: {width}x{height}.")
    return ImageInfo(
        filename=filename,
        format=fmt,
        width=width,
        height=height,
        mode=mode,
        bytes=len(data),
        sha256=sha256_bytes(data),
        has_alpha=has_alpha,
    )


def _inspect_input_image(
    path: str | Path,
    *,
    max_bytes: int = MAX_INPUT_IMAGE_BYTES,
) -> tuple[tuple[int, int], str, bool, tuple[int, int] | None]:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Image file not found: {file_path}")
    size_bytes = file_path.stat().st_size
    if size_bytes >= max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise ValueError(f"Input file must be smaller than {limit_mb} MB: {file_path}")
    try:
        with Image.open(file_path) as image:
            image.verify()
        with Image.open(file_path) as image:
            image.load()
            size = image.size
            fmt = (image.format or "").upper()
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            alpha_extrema = None
            if "A" in image.getbands():
                alpha_extrema = image.getchannel("A").getextrema()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Invalid input image {file_path}: {exc}") from exc
    return size, fmt, has_alpha, alpha_extrema


def validate_input_image(path: str | Path, *, is_mask: bool = False) -> tuple[int, int]:
    size, fmt, has_alpha, alpha_extrema = _inspect_input_image(
        path,
        max_bytes=MAX_MASK_BYTES if is_mask else MAX_INPUT_IMAGE_BYTES,
    )
    if fmt not in {"PNG", "JPEG", "WEBP"}:
        role = "mask" if is_mask else "input image"
        raise ValueError(
            f"Unsupported {role} format {fmt or 'unknown'}. Use PNG, JPEG/JPG, or WebP."
        )
    if is_mask:
        if not has_alpha:
            raise ValueError(
                "The edit mask must contain an alpha channel. Transparent areas indicate the edit region."
            )
        if alpha_extrema and alpha_extrema[0] == 255:
            raise ValueError(
                "The mask is fully opaque and contains no transparent edit region."
            )
    return size


def validate_input_images(paths: Iterable[str | Path]) -> list[Path]:
    resolved = [Path(path).resolve() for path in paths]
    if not resolved:
        raise ValueError("At least one input image is required.")
    if len(resolved) > MAX_INPUT_IMAGES:
        raise ValueError(f"GPT Image edit requests support at most {MAX_INPUT_IMAGES} input images.")
    for path in resolved:
        validate_input_image(path)
    return resolved


def validate_mask_compatibility(image_path: str | Path, mask_path: str | Path) -> None:
    image_size, image_format, _, _ = _inspect_input_image(image_path)
    mask_size, mask_format, has_alpha, alpha_extrema = _inspect_input_image(
        mask_path, max_bytes=MAX_MASK_BYTES
    )
    if mask_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError("The edit mask must be PNG, JPEG/JPG, or WebP.")
    if mask_format != image_format:
        raise ValueError(
            f"Mask format {mask_format} must match the first image format {image_format}. "
            "For masked edits, use an alpha-capable format such as PNG or WebP for both files."
        )
    if not has_alpha:
        raise ValueError(
            "The edit mask must contain an alpha channel. Use PNG or WebP when creating a mask."
        )
    if alpha_extrema and alpha_extrema[0] == 255:
        raise ValueError("The mask is fully opaque and contains no transparent edit region.")
    if mask_size != image_size:
        raise ValueError(
            f"Mask dimensions {mask_size[0]}x{mask_size[1]} must match the first image "
            f"{image_size[0]}x{image_size[1]}."
        )


def validate_generation_options(
    *,
    model: str,
    model_family: str = "auto",
    size: str,
    quality: str,
    background: str,
    output_format: str,
    output_compression: int | None,
    count: int,
) -> list[str]:
    import re

    warnings: list[str] = []
    caps = model_capabilities(model, model_family)

    if quality not in caps.qualities:
        allowed = ", ".join(sorted(caps.qualities))
        raise ValueError(
            f"quality {quality!r} is not supported for {caps.family}; choose from: {allowed}."
        )
    if background not in {"transparent", "opaque", "auto"}:
        raise ValueError("background must be transparent, opaque, or auto.")
    output_format = output_format.lower()
    if output_format not in {"png", "jpeg", "webp"}:
        raise ValueError("output_format must be png, jpeg, or webp.")
    if not 1 <= count <= 10:
        raise ValueError("count must be between 1 and 10.")
    if output_compression is not None:
        if output_format not in {"jpeg", "webp"}:
            raise ValueError("output_compression is only valid for jpeg or webp.")
        if not 0 <= output_compression <= 100:
            raise ValueError("output_compression must be between 0 and 100.")

    if background == "transparent":
        if not caps.transparent_background:
            raise ValueError(f"{caps.family} does not support transparent backgrounds.")
        if output_format not in {"png", "webp"}:
            raise ValueError("transparent backgrounds require output_format png or webp.")
        if caps.transparent_preview:
            warnings.append(
                "Transparent backgrounds are currently a preview capability for gpt-image-2; "
                "verify the returned alpha channel before production use."
            )

    if size != "auto":
        match = re.fullmatch(r"(\d+)x(\d+)", size)
        if not match:
            raise ValueError("size must be auto or WIDTHxHEIGHT, for example 1536x1024.")
        width, height = map(int, match.groups())
        if width <= 0 or height <= 0:
            raise ValueError("size edges must be positive integers.")
        if caps.flexible_size:
            if width > 3840 or height > 3840:
                raise ValueError(
                    f"For {caps.family}, each edge must not exceed 3840 pixels."
                )
            if width % 16 or height % 16:
                raise ValueError(f"For {caps.family}, both edges must be multiples of 16.")
            pixels = width * height
            if not 655_360 <= pixels <= 8_294_400:
                raise ValueError(
                    f"For {caps.family}, total pixels must be between 655,360 and 8,294,400."
                )
            if max(width, height) / min(width, height) > 3:
                raise ValueError(
                    f"For {caps.family}, the long-to-short edge ratio cannot exceed 3:1."
                )
            if caps.experimental_over_pixels and pixels > caps.experimental_over_pixels:
                warnings.append(
                    f"{width}x{height} exceeds 3,686,400 pixels (2560x1440); "
                    f"this resolution tier is experimental for {caps.family}."
                )
        elif size not in {"1024x1024", "1536x1024", "1024x1536"}:
            warnings.append(
                f"The selected {caps.family} family is not validated for arbitrary sizes; "
                "this relay may only accept standard GPT Image sizes."
            )

    if caps.family == "generic" and quality in {"xhigh", "max"}:
        warnings.append(
            f"quality={quality} is being passed through to an unrecognized relay model; "
            "set IMAGE_API_MODEL_FAMILY=gpt-image-2.5 when the alias maps to GPT Image 2.5."
        )
    return warnings
