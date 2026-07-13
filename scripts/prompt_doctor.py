#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from image2lib.config import MODEL_FAMILIES
from image2lib.prompting import PROFILES, lint_prompt, read_prompt


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Review a prompt against GPT Image 2 prompting patterns.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--prompt-file")
    p.add_argument("--operation", default="generate", choices=["generate", "edit"])
    p.add_argument("--profile", default="auto", choices=PROFILES)
    p.add_argument("--model", default="gpt-image-2")
    p.add_argument("--model-family", default="auto", choices=MODEL_FAMILIES)
    p.add_argument("--image-count", type=int, default=0)
    p.add_argument("--mask", action="store_true", help="Indicate that a mask will be supplied.")
    p.add_argument("--quality", default="auto", choices=["low", "medium", "high", "auto"])
    p.add_argument("--size", default="auto")
    p.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    p.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    p.add_argument("--json", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        prompt = read_prompt(args.prompt, args.prompt_file)
        report = lint_prompt(
            prompt,
            operation=args.operation,
            profile=args.profile,
            model=args.model,
            model_family=args.model_family,
            image_count=args.image_count,
            has_mask=args.mask,
            quality=args.quality,
            size=args.size,
            background=args.background,
        )
        try:
            report.enforce(strict=args.strict)
        except ValueError as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc), "review": report.to_dict()}, ensure_ascii=False, indent=2))
            else:
                print(f"Prompt status: {report.status} | profile: {report.profile} | operation: {report.operation}")
                for issue in report.issues:
                    print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
                    if issue.suggestion:
                        print(f"  Fix: {issue.suggestion}")
                print(f"Error: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps({"ok": True, "review": report.to_dict()}, ensure_ascii=False, indent=2))
        else:
            print(f"Prompt status: {report.status} | profile: {report.profile} | operation: {report.operation}")
            if not report.issues:
                print("No prompt-quality issues found.")
            for issue in report.issues:
                print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
                if issue.suggestion:
                    print(f"  Fix: {issue.suggestion}")
        return 0
    except (ValueError, OSError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
