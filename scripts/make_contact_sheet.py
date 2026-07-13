#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}


def collect(paths: list[str], directory: str | None) -> list[Path]:
    result = [Path(p).resolve() for p in paths]
    if directory:
        result.extend(
            p.resolve()
            for p in sorted(Path(directory).iterdir())
            if p.is_file() and p.suffix.lower() in SUPPORTED
        )
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in result:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    if not unique:
        raise ValueError("No input images found.")
    return unique


def main() -> int:
    p = argparse.ArgumentParser(description="Create a labeled contact sheet for comparing generated candidates.")
    p.add_argument("--input", action="append", default=[], help="Input image; repeat as needed.")
    p.add_argument("--dir", help="Directory containing generated images.")
    p.add_argument("--output", default="contact-sheet.png")
    p.add_argument("--columns", type=int, default=2)
    p.add_argument("--cell-width", type=int, default=640)
    p.add_argument("--cell-height", type=int, default=480)
    args = p.parse_args()
    try:
        images = collect(args.input, args.dir)
        if args.columns < 1:
            raise ValueError("columns must be at least 1.")
        rows = math.ceil(len(images) / args.columns)
        label_height = 34
        canvas = Image.new(
            "RGB",
            (args.columns * args.cell_width, rows * (args.cell_height + label_height)),
            "white",
        )
        draw = ImageDraw.Draw(canvas)
        for index, path in enumerate(images):
            with Image.open(path) as source:
                image = ImageOps.contain(source.convert("RGB"), (args.cell_width, args.cell_height))
            col = index % args.columns
            row = index // args.columns
            x = col * args.cell_width + (args.cell_width - image.width) // 2
            y = row * (args.cell_height + label_height) + (args.cell_height - image.height) // 2
            canvas.paste(image, (x, y))
            label_y = row * (args.cell_height + label_height) + args.cell_height + 8
            draw.text((col * args.cell_width + 10, label_y), f"{index + 1}. {path.name}", fill="black")
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, format="PNG")
        print(output)
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
