#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from image2lib.client import ImageAPIClient, ImageAPIError
from image2lib.capabilities import OUTPUT_FORMATS, QUALITY_CHOICES
from image2lib.config import APIConfig, MODEL_FAMILIES
from image2lib.jobs import save_image_results
from image2lib.outputs import RunOutput
from image2lib.prompting import PROFILES, lint_prompt, read_prompt
from image2lib.utils import merge_extra_params
from image2lib.validation import validate_generation_options


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate images through an OpenAI-compatible Images API relay.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Image prompt text.")
    source.add_argument("--prompt-file", help="UTF-8 text file containing the prompt.")
    p.add_argument("--model", help="Model name or relay alias. Defaults to IMAGE_API_MODEL.")
    p.add_argument(
        "--model-family",
        choices=MODEL_FAMILIES,
        help="Underlying capability family for relay aliases. Defaults to IMAGE_API_MODEL_FAMILY or auto.",
    )
    p.add_argument("--prompt-profile", default="auto", choices=PROFILES, help="Task profile used for prompt review.")
    p.add_argument("--prompt-lint", default="warn", choices=["off", "warn", "strict"], help="Review prompt quality before the API call.")
    p.add_argument("--base-url", help="API base URL override, normally ending in /v1.")
    p.add_argument("--endpoint", help="Full generation endpoint override.")
    p.add_argument("--size", help="auto or WIDTHxHEIGHT. Defaults to auto for GIF/SVG and 2048x2048 for still raster images.")
    p.add_argument("--quality", default="high", choices=QUALITY_CHOICES)
    p.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    p.add_argument("--output-format", default="png", choices=OUTPUT_FORMATS)
    p.add_argument("--frame-count", type=int, help="GIF only: 2-16 frames (upstream default: 9).")
    p.add_argument("--frame-duration-ms", type=int, help="GIF only: 20-2000 ms per frame (upstream default: 200).")
    p.add_argument("--output-compression", type=int)
    p.add_argument("--moderation", default="auto", choices=["auto", "low"])
    p.add_argument("--count", type=int, default=1, help="Number of images, 1-10.")
    p.add_argument(
        "--batch-mode",
        default="auto",
        choices=["auto", "single", "sequential"],
        help="auto uses sequential calls for count > 1 for relay compatibility.",
    )
    p.add_argument("--output-dir", help="Run output directory. Defaults to output/<name>_<timestamp> under current working directory.")
    p.add_argument("--name", help="Semantic name for this generation. Used as directory and image filename (e.g. --name '海报主视觉' -> output/海报主视觉_20260714_xxx/海报主视觉.png). Falls back to prompt slug if omitted.")
    p.add_argument("--filename-prefix", default="image")
    p.add_argument(
        "--extra-param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Relay-documented extra request parameter; VALUE is parsed as JSON when possible.",
    )
    p.add_argument("--timeout", type=float)
    p.add_argument("--max-retries", type=int)
    p.add_argument("--dry-run", action="store_true", help="Validate and print the sanitized request without calling the API.")
    p.add_argument("--test", action="store_true", help="Cost-saving test mode: forces quality=low (cheapest output tokens). Overrides --quality.")
    p.add_argument("--json", action="store_true", help="Print a machine-readable result object.")
    return p


def _payload(args: argparse.Namespace, prompt: str, model: str, n: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "moderation": args.moderation,
    }
    if args.frame_count is not None:
        payload["frame_count"] = args.frame_count
    if args.frame_duration_ms is not None:
        payload["frame_duration_ms"] = args.frame_duration_ms
    if args.output_compression is not None:
        payload["output_compression"] = args.output_compression
    return merge_extra_params(
        payload,
        args.extra_param,
        reserved={
            "model", "prompt", "n", "size", "quality", "background",
            "output_format", "output_compression", "moderation",
            "frame_count", "frame_duration_ms",
            *({"stream", "partial_images"} if args.output_format in {"gif", "svg"} else ()),
        },
    )


def main() -> int:
    args = parser().parse_args()
    if args.size is None:
        args.size = "auto" if args.output_format in {"gif", "svg"} else "2048x2048"
    if getattr(args, "test", False):
        args.quality = "low"
    try:
        prompt = read_prompt(args.prompt, args.prompt_file)
        config = APIConfig.from_env(
            base_url=args.base_url,
            model=args.model,
            model_family=args.model_family,
            generations_url=args.endpoint,
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
            frame_count=args.frame_count,
            frame_duration_ms=args.frame_duration_ms,
        )
        prompt_review = None
        if args.prompt_lint != "off":
            prompt_review = lint_prompt(
                prompt,
                operation="generate",
                profile=args.prompt_profile,
                model=config.model,
                model_family=config.resolved_model_family,
                quality=args.quality,
                size=args.size,
                background=args.background,
            )
            prompt_review.enforce(strict=args.prompt_lint == "strict")
            warnings += [f"Prompt [{issue.code}]: {issue.message}" for issue in prompt_review.issues if issue.severity == "warning"]
        mode = args.batch_mode
        if mode == "auto":
            mode = "single" if args.count == 1 else "sequential"

        run = RunOutput(args.output_dir, prompt, args.filename_prefix, name=getattr(args, "name", None))
        planned_payloads = (
            [_payload(args, prompt, config.model, args.count)]
            if mode == "single"
            else [_payload(args, prompt, config.model, 1) for _ in range(args.count)]
        )
        run.write_request(
            {
                "operation": "generate",
                "config": config.safe_dict(),
                "batch_mode": mode,
                "requests": planned_payloads,
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
        result = save_image_results(
            run,
            client,
            (client.generate(payload) for payload in planned_payloads),
            output_format=args.output_format,
            count=args.count,
            metadata={
                "operation": "generate",
                "model": config.model,
                "prompt_review": prompt_review.to_dict() if prompt_review else None,
                "warnings": warnings,
            },
        )
        if result["ok"]:
            removed = run.cleanup_intermediates()
            if removed and not args.json:
                print(f"Cleaned intermediate files: {', '.join(removed)}", file=sys.stderr)
        saved_paths = result["images"]
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Generated {len(saved_paths)} image(s).")
            for path in saved_paths:
                print(path)
            print(f"Run directory: {run.path}")
            for warning in warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            if not result["ok"]:
                print(f"Error: {result['error']}", file=sys.stderr)
        return 0 if result["ok"] else 1
    except (ValueError, OSError, ImageAPIError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
