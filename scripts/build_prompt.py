#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from image2lib.config import MODEL_FAMILIES
from image2lib.prompting import (
    PROFILES,
    brief_schema,
    build_prompt,
    lint_prompt,
    load_brief,
    resolve_prompt_context,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Compile a structured visual brief into a GPT Image 2 creative brief and optionally review it."
    )
    p.add_argument("--brief", help="Path to a UTF-8 JSON brief.")
    p.add_argument("--output", help="Optional output prompt text file.")
    p.add_argument("--profile", default="auto", choices=PROFILES)
    p.add_argument("--operation", choices=["generate", "edit"])
    p.add_argument("--lint", action="store_true", help="Review the compiled prompt and print issues to stderr.")
    p.add_argument("--strict", action="store_true", help="Fail when prompt review returns warnings.")
    p.add_argument("--model", default="gpt-image-2")
    p.add_argument("--model-family", default="auto", choices=MODEL_FAMILIES)
    p.add_argument("--quality", default="auto", choices=["low", "medium", "high", "auto"])
    p.add_argument("--size", default="auto")
    p.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    p.add_argument("--image-count", type=int, default=0)
    p.add_argument("--mask", action="store_true")
    p.add_argument("--json", action="store_true", help="Print prompt and review as JSON.")
    p.add_argument("--print-schema", action="store_true", help="Print the supported brief schema and exit.")
    p.add_argument("--list-profiles", action="store_true", help="List prompt profiles and exit.")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.list_profiles:
            print("\n".join(PROFILES))
            return 0
        if args.print_schema:
            print(json.dumps(brief_schema(), ensure_ascii=False, indent=2))
            return 0
        if not args.brief:
            raise ValueError("--brief is required unless --print-schema or --list-profiles is used.")

        brief = load_brief(args.brief)
        effective_profile, operation = resolve_prompt_context(
            brief, profile=args.profile, operation=args.operation
        )
        prompt = build_prompt(brief, profile=effective_profile, operation=operation)
        report = lint_prompt(
            prompt,
            operation=operation,
            profile=effective_profile,
            model=args.model,
            model_family=args.model_family,
            image_count=args.image_count,
            has_mask=args.mask,
            quality=args.quality,
            size=args.size,
            background=args.background,
        )
        report.enforce(strict=args.strict)

        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prompt + "\n", encoding="utf-8")

        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "profile": report.profile,
                        "operation": report.operation,
                        "prompt": prompt,
                        "output": str(Path(args.output).resolve()) if args.output else None,
                        "review": report.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(str(Path(args.output).resolve()) if args.output else prompt)
            if args.lint:
                for issue in report.issues:
                    print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}", file=sys.stderr)
                    if issue.suggestion:
                        print(f"  Fix: {issue.suggestion}", file=sys.stderr)
        return 0
    except (ValueError, OSError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
