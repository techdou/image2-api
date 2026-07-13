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
from image2lib.validation import validate_generation_options, validate_image_bytes


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
    p.add_argument("--size", default="auto", help="auto or WIDTHxHEIGHT.")
    p.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"])
    p.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    p.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
    p.add_argument("--output-compression", type=int)
    p.add_argument("--moderation", default="auto", choices=["auto", "low"])
    p.add_argument("--count", type=int, default=1, help="Number of images, 1-10.")
    p.add_argument(
        "--batch-mode",
        default="auto",
        choices=["auto", "single", "sequential"],
        help="auto uses sequential calls for count > 1 for relay compatibility.",
    )
    p.add_argument("--output-dir", help="Run output directory. Defaults to outputs/<timestamp>_<slug>.")
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
    if args.output_compression is not None:
        payload["output_compression"] = args.output_compression
    return merge_extra_params(
        payload,
        args.extra_param,
        reserved={
            "model", "prompt", "n", "size", "quality", "background",
            "output_format", "output_compression", "moderation",
        },
    )


def main() -> int:
    args = parser().parse_args()
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

        run = RunOutput(args.output_dir, prompt, args.filename_prefix)
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
        responses: list[dict[str, Any]] = []
        image_metadata: list[dict[str, Any]] = []
        saved_paths: list[str] = []
        output_index = 1

        for payload in planned_payloads:
            api_result = client.generate(payload)
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
                "operation": "generate",
                "model": config.model,
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
            print(f"Generated {len(saved_paths)} image(s).")
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
