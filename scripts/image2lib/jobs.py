from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .client import APIResult, ImageAPIClient, ImageAPIError, entry_to_bytes, extract_image_entries
from .outputs import RunOutput, extension_for_format
from .validation import validate_image_bytes, validate_svg_bytes


def save_image_results(
    run: RunOutput,
    client: ImageAPIClient,
    results: Iterable[APIResult],
    *,
    output_format: str,
    count: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Persist validated images and report partial success if a later result fails."""
    responses = []
    images = []
    saved_paths = []
    failure = {}
    try:
        for result in results:
            responses.append(result.safe_summary())
            entries = extract_image_entries(result.payload)
            if output_format == "svg" and len(entries) != 1:
                raise ValueError("Expected exactly one SVG in the provider response.")
            for entry in entries:
                data = entry_to_bytes(client, entry)
                path = run.image_path(len(saved_paths) + 1, output_format, total=count)
                if output_format == "svg":
                    info = validate_svg_bytes(data, path.name)
                else:
                    info = validate_image_bytes(
                        data, path.name, require_animated_gif=output_format == "gif"
                    ).to_dict()
                path = path.with_suffix(extension_for_format(info["format"]))
                _write_image(path, data)
                images.append({**info, "filename": path.name})
                saved_paths.append(str(path))
    except (ValueError, OSError, ImageAPIError) as exc:
        failure = {"error": str(exc), "partial": bool(saved_paths)}

    run.write_response_summary({"responses": responses})
    run.write_metadata({**metadata, "image_count": len(images), "images": images, **failure})
    return {
        "ok": not failure,
        "run_dir": str(run.path),
        "images": saved_paths,
        "warnings": metadata["warnings"],
        **failure,
    }


def _write_image(path: Path, data: bytes) -> None:
    with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.close()
            os.replace(staged, path)
        finally:
            temporary.close()
            staged.unlink(missing_ok=True)
