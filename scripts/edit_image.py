#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from image2lib.client import ImageAPIClient, ImageAPIError, entry_to_bytes, extract_image_entries
from image2lib.config import APIConfig, MODEL_FAMILIES
from image2lib.outputs import RunOutput, extension_for_format
from image2lib.prompting import PROFILES, lint_prompt, read_prompt
from image2lib.utils import merge_extra_params
from image2lib.validation import (
    validate_generation_options,
    validate_image_bytes,
    validate_input_image,
    validate_input_images,
    validate_mask_compatibility,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Edit images through an OpenAI-compatible Images API relay.")
    p.add_argument("--image", action="append", required=True, help="Input/reference image. Repeat for multiple images.")
    p.add_argument("--mask", help="Optional PNG mask; transparent areas indicate the edit region.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Edit prompt text.")
    source.add_argument("--prompt-file", help="UTF-8 text file containing the prompt.")
    p.add_argument("--model", help="Model name or relay alias. Defaults to IMAGE_API_MODEL.")
    p.add_argument(
        "--model-family",
        choices=MODEL_FAMILIES,
        help="Underlying capability family for relay aliases. Defaults to IMAGE_API_MODEL_FAMILY or auto.",
    )
    p.add_argument("--prompt-profile", default="edit", choices=PROFILES, help="Task profile used for prompt review.")
    p.add_argument("--prompt-lint", default="warn", choices=["off", "warn", "strict"], help="Review prompt quality before the API call.")
    p.add_argument("--base-url", help="API base URL override, normally ending in /v1.")
    p.add_argument("--endpoint", help="Full edit endpoint override.")
    p.add_argument("--size", default="auto")
    p.add_argument("--quality", default="medium", choices=["low", "medium", "high", "auto"])
    p.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
    p.add_argument("--output-compression", type=int)
    p.add_argument("--moderation", default="auto", choices=["auto", "low"])
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--batch-mode", default="auto", choices=["auto", "single", "sequential"])
    p.add_argument("--output-dir")
    p.add_argument("--filename-prefix", default="edited")
    p.add_argument("--extra-param", action="append", default=[], metavar="KEY=VALUE")
    p.add_argument("--timeout", type=float)
    p.add_argument("--max-retries", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--test", action="store_true", help="Cost-saving test mode: forces quality=low (cheapest output tokens). Overrides --quality.")
    p.add_argument("--json", action="store_true")
    return p


def _fields(
    args: argparse.Namespace, prompt: str, model: str, n: int, *, is_gpt_image_2: bool
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "moderation": args.moderation,
    }
    if args.output_compression is not None:
        fields["output_compression"] = args.output_compression
    fields = merge_extra_params(
        fields,
        args.extra_param,
        reserved={
            "model", "prompt", "n", "size", "quality", "background",
            "output_format", "output_compression", "moderation",
            "image", "image[]", "mask",
        },
    )
    if is_gpt_image_2:
        fields.pop("input_fidelity", None)
    return fields


def main() -> int:
    args = parser().parse_args()
    if getattr(args, "test", False):
        args.quality = "low"
    try:
        prompt = read_prompt(args.prompt, args.prompt_file)
        image_paths = validate_input_images(args.image)
        mask_path = Path(args.mask).resolve() if args.mask else None
        if mask_path:
            validate_input_image(mask_path, is_mask=True)
            validate_mask_compatibility(image_paths[0], mask_path)

        config = APIConfig.from_env(
            base_url=args.base_url,
            model=args.model,
            model_family=args.model_family,
            edits_url=args.endpoint,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
        warnings = config.validate(require_key=not args.dry_run)
        warnings += validate_generation_options(
            model=config.model,
            model_family=config.resolved_model_family,
            size=args.size,
            quality=args.quality,
            background=args.background,
            output_format=args.output_format,
            output_compression=args.output_compression,
            count=args.count,
        )
        prompt_review = None
        if args.prompt_lint != "off":
            prompt_review = lint_prompt(
                prompt,
                operation="edit",
                profile=args.prompt_profile,
                model=config.model,
                model_family=config.resolved_model_family,
                image_count=len(image_paths),
                has_mask=bool(mask_path),
                quality=args.quality,
                size=args.size,
                background=args.background,
            )
            prompt_review.enforce(strict=args.prompt_lint == "strict")
            warnings += [f"Prompt [{issue.code}]: {issue.message}" for issue in prompt_review.issues if issue.severity == "warning"]
        mode = args.batch_mode
        if mode == "auto":
            mode = "single" if args.count == 1 else "sequential"
        planned_fields = (
            [_fields(args, prompt, config.model, args.count, is_gpt_image_2=config.is_gpt_image_2)]
            if mode == "single"
            else [
                _fields(args, prompt, config.model, 1, is_gpt_image_2=config.is_gpt_image_2)
                for _ in range(args.count)
            ]
        )
        run = RunOutput(args.output_dir, prompt, args.filename_prefix)
        run.write_request(
            {
                "operation": "edit",
                "config": config.safe_dict(),
                "batch_mode": mode,
                "input_images": [str(p) for p in image_paths],
                "mask": str(mask_path) if mask_path else None,
                "requests": planned_fields,
                "prompt_review": prompt_review.to_dict() if prompt_review else None,
                "warnings": warnings,
            }
        )
        if prompt_review:
            run.write_prompt_review(prompt_review.to_dict())
        if args.dry_run:
            result = {"ok": True, "dry_run": True, "run_dir": str(run.path), "warnings": warnings}
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Dry run valid: {run.path}")
            return 0

        client = ImageAPIClient(config)
        responses: list[dict[str, Any]] = []
        image_metadata: list[dict[str, Any]] = []
        saved_paths: list[str] = []
        output_index = 1
        for fields in planned_fields:
            api_result = client.edit(fields, image_paths, mask_path)
            responses.append(api_result.safe_summary())
            for entry in extract_image_entries(api_result.payload):
                data = entry_to_bytes(client, entry)
                path = run.image_path(output_index, args.output_format)
                info = validate_image_bytes(data, path.name)
                actual_ext = extension_for_format(info.format)
                if path.suffix.lower() != actual_ext:
                    path = path.with_suffix(actual_ext)
                path.write_bytes(data)
                info.filename = path.name
                image_metadata.append(info.to_dict())
                saved_paths.append(str(path))
                output_index += 1

        run.write_response_summary({"responses": responses})
        run.write_metadata(
            {
                "operation": "edit",
                "model": config.model,
                "input_images": [str(p) for p in image_paths],
                "mask": str(mask_path) if mask_path else None,
                "image_count": len(saved_paths),
                "images": image_metadata,
                "prompt_review": prompt_review.to_dict() if prompt_review else None,
                "warnings": warnings,
            }
        )
        result = {"ok": True, "run_dir": str(run.path), "images": saved_paths, "warnings": warnings}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Created {len(saved_paths)} edited image(s).")
            for path in saved_paths:
                print(path)
            print(f"Run directory: {run.path}")
            for warning in warnings:
                print(f"Warning: {warning}", file=sys.stderr)
        return 0
    except (ValueError, OSError, ImageAPIError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
