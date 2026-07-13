from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import safe_slug, write_json

_FORMAT_EXTENSIONS = {
    "png": ".png",
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "webp": ".webp",
}


def extension_for_format(image_format: str) -> str:
    return _FORMAT_EXTENSIONS.get(image_format.lower(), ".png")


class RunOutput:
    def __init__(
        self,
        output_dir: str | None,
        prompt: str,
        prefix: str = "image",
        name: str | None = None,
    ) -> None:
        if output_dir:
            path = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if name:
                slug = safe_slug(name, 60)
                path = Path("output") / f"{slug}_{timestamp}"
                self.prefix = slug
            else:
                path = Path("output") / f"{timestamp}_{safe_slug(prompt[:80])}"
                self.prefix = safe_slug(prefix, 32)
        self.path = path.resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "prompt.txt").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def image_path(self, index: int, output_format: str, total: int = 1) -> Path:
        ext = extension_for_format(output_format)
        if total <= 1:
            return self.path / f"{self.prefix}{ext}"
        return self.path / f"{self.prefix}_{index:02d}{ext}"

    def write_request(self, request: dict[str, Any]) -> None:
        write_json(self.path / "request.json", request)

    def write_prompt_review(self, review: dict[str, Any]) -> None:
        write_json(self.path / "prompt_review.json", review)

    def write_response_summary(self, summary: dict[str, Any]) -> None:
        write_json(self.path / "response_summary.json", summary)

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        write_json(self.path / "metadata.json", metadata)


def media_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"
