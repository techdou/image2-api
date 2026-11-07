from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from struct import error as StructError, unpack_from
from typing import Any, Iterable
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

from .capabilities import OUTPUT_FORMATS, model_capabilities
from .utils import sha256_bytes

MAX_INPUT_IMAGES = 16
MAX_INPUT_IMAGE_BYTES = 50 * 1024 * 1024
MAX_MASK_BYTES = 50 * 1024 * 1024
MAX_GIF_BYTES = 64 * 1024 * 1024
MAX_GIF_FRAMES = 16
MAX_GIF_EDGE = 3840
MAX_GIF_FRAME_PIXELS = 8_294_400
MAX_SVG_BYTES = 8 * 1024 * 1024
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
_GIF_HEADERS = (b"GIF87a", b"GIF89a")
_SVG_ACTIVE_ELEMENTS = {
    "a", "animate", "animatecolor", "animatemotion", "animatetransform",
    "discard", "feimage", "foreignobject", "handler", "image", "link", "script", "set",
}
_LOCAL_CSS_URL = re.compile(r"""url\(\s*(['"]?)#[\w.:-]+\1\s*\)""", re.IGNORECASE)


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
    frame_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.frame_count is None:
            del result["frame_count"]
        return result


def validate_image_bytes(
    data: bytes, filename: str = "image", *, require_animated_gif: bool = False
) -> ImageInfo:
    is_gif = data.startswith(_GIF_HEADERS)
    if require_animated_gif and not is_gif:
        raise ValueError(f"{filename}: expected a multi-frame GIF from the provider.")
    frame_count = _inspect_gif_structure(data, filename) if is_gif else None
    if require_animated_gif and (frame_count or 0) < 2:
        raise ValueError(f"{filename}: expected a multi-frame GIF, got {frame_count} frame(s).")
    if len(data) < 256 and not is_gif:
        raise ValueError(f"{filename}: returned image is implausibly small ({len(data)} bytes).")
    prefix = data[:256].lstrip().lower()
    if prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html"):
        raise ValueError(f"{filename}: the API returned an HTML page instead of an image.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        # Pillow verify() invalidates its image handle. Decode on a fresh handle.
        with Image.open(BytesIO(data)) as image:
            fmt = (image.format or "unknown").lower()
            image.load()
            width, height = image.size
            mode = image.mode
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            if frame_count is not None:
                for index in range(1, frame_count):
                    image.seek(index)
                    image.load()
    except (UnidentifiedImageError, OSError, EOFError, Image.DecompressionBombError) as exc:
        raise ValueError(f"{filename}: invalid or corrupted image bytes: {exc}") from exc
    if fmt != "gif" and (width < 64 or height < 64):
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
        frame_count=frame_count,
    )


def _inspect_gif_structure(data: bytes, filename: str) -> int:
    """Bound the GIF canvas and count frame descriptors before Pillow decodes pixels."""
    if len(data) > MAX_GIF_BYTES:
        raise ValueError(f"{filename}: GIF exceeds the 64 MiB response limit.")
    try:
        width, height, flags = unpack_from("<HHB", data, 6)
        _check_gif_frame_size((width, height), filename)
        offset = 13 + _gif_color_table_bytes(flags)
        frames = 0
        while True:
            marker = data[offset]
            offset += 1
            if marker == 0x3B and frames:
                return frames
            if marker == 0x2C:
                left, top, frame_width, frame_height, flags = unpack_from("<HHHHB", data, offset)
                _check_gif_frame_size((frame_width, frame_height), filename)
                width, height = max(width, left + frame_width), max(height, top + frame_height)
                _check_gif_frame_size((width, height), filename)
                frames += 1
                if frames > MAX_GIF_FRAMES:
                    raise ValueError(f"{filename}: GIF exceeds {MAX_GIF_FRAMES} frames.")
                offset += 10 + _gif_color_table_bytes(flags)  # descriptor and LZW code size
            elif marker == 0x21:
                offset += 1  # extension label
            else:
                break
            while block_size := data[offset]:
                offset += 1 + block_size
            offset += 1
    except (IndexError, StructError) as exc:
        raise ValueError(f"{filename}: truncated GIF data.") from exc
    raise ValueError(f"{filename}: invalid GIF frame data or trailer.")


def _gif_color_table_bytes(flags: int) -> int:
    return 3 * (2 << (flags & 7)) if flags & 0x80 else 0


def _check_gif_frame_size(size: tuple[int, int], filename: str) -> None:
    width, height = size
    if not 0 < min(size) or max(size) > MAX_GIF_EDGE or width * height > MAX_GIF_FRAME_PIXELS:
        raise ValueError(f"{filename}: GIF frame dimensions exceed local limits: {width}x{height}.")


def validate_svg_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """Check a static SVG payload and describe its viewport without rasterizing it."""
    if len(data) > MAX_SVG_BYTES:
        raise ValueError(f"{filename}: SVG exceeds the 8 MiB response limit.")
    try:
        xml = data.decode("utf-8-sig")
        if re.search(r"<!DOCTYPE|<!ENTITY|<\?(?!xml\s)", xml, re.IGNORECASE):
            raise ValueError(f"{filename}: SVG contains a document type or processing instruction.")
        root = ElementTree.fromstring(xml)
    except (UnicodeDecodeError, ElementTree.ParseError) as exc:
        raise ValueError(f"{filename}: expected a valid UTF-8 SVG document.") from exc
    if root.tag != f"{SVG_NAMESPACE}svg":
        raise ValueError(f"{filename}: expected an SVG document from the provider.")

    for element in root.iter():
        tag = element.tag.removeprefix(SVG_NAMESPACE).lower()
        if not element.tag.startswith(SVG_NAMESPACE) or tag in _SVG_ACTIVE_ELEMENTS:
            raise ValueError(f"{filename}: SVG contains an unsupported element: {tag}.")
        for attr, value in element.attrib.items():
            name = attr.rsplit("}", 1)[-1].lower()
            if name.startswith("on") or name == "base" or (name == "href" and not value.strip().startswith("#")):
                raise ValueError(f"{filename}: SVG contains an active attribute or external reference.")
            if name == "style" or "(" in value or "\\" in value:
                _check_svg_css(value, filename)
        if tag == "style":
            _check_svg_css("".join(element.itertext()), filename)

    return {
        "filename": filename,
        "format": "svg",
        "width": root.get("width"),
        "height": root.get("height"),
        "view_box": root.get("viewBox"),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def _check_svg_css(value: str, filename: str) -> None:
    # Only permit literal fragment URLs. Avoid CSS escapes, imports, and indirection.
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    remaining = _LOCAL_CSS_URL.sub("", value)
    if re.search(r"[@\\]|\b(?:url|src|image(?:-set)?|var)\s*\(", remaining, re.IGNORECASE):
        raise ValueError(f"{filename}: SVG contains an unsupported CSS reference.")


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
    frame_count: int | None = None,
    frame_duration_ms: int | None = None,
    has_mask: bool = False,
) -> list[str]:
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
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of: {', '.join(OUTPUT_FORMATS)}.")
    if output_format == "svg":
        if not caps.native_svg:
            raise ValueError("SVG output requires GPT Image 2.6 Flare or Sunburst (or a relay alias declared as gpt-image-2.6).")
        if count != 1:
            raise ValueError("SVG output supports one image per request. Set count to 1.")
    if output_format == "gif":
        if not caps.animated_gif:
            raise ValueError("GIF output requires GPT Image 2.6 Flare or Sunburst (or a relay alias declared as gpt-image-2.6).")
        if has_mask:
            raise ValueError("GIF output does not support masks. Supply still reference images without a mask.")
        if frame_count is not None and not 2 <= frame_count <= MAX_GIF_FRAMES:
            raise ValueError("frame_count must be between 2 and 16.")
        if frame_duration_ms is not None and not 20 <= frame_duration_ms <= 2000:
            raise ValueError("frame_duration_ms must be between 20 and 2000.")
    elif frame_count is not None or frame_duration_ms is not None:
        raise ValueError("frame_count and frame_duration_ms are only valid for GIF output.")
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
        if output_format == "gif":
            if width % 16 or height % 16:
                raise ValueError("GIF frame edges must be multiples of 16.")
        elif caps.flexible_size:
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
