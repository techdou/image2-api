#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT_DEFAULT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from image2lib.prompting import build_prompt, brief_schema, lint_prompt, load_brief, resolve_prompt_context
from image2lib.version import __version__

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PATH_RE = re.compile(
    r"(?<![\w/])((?:references|scripts|examples|assets|evals)/[A-Za-z0-9_./-]+(?:\.[A-Za-z0-9_-]+)?)"
)


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter delimited by ---.")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter has no closing --- delimiter.")
    raw = text[4:end]
    values: dict[str, str] = {}
    in_metadata = False
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "metadata:":
            in_metadata = True
            continue
        if not line.startswith(" "):
            in_metadata = False
        match = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip().strip('"').strip("'")
        values[f"metadata.{key}" if in_metadata else key] = value
    return values, text[end + 5 :]


def _add(checks: list[dict[str, Any]], ok: bool, code: str, message: str) -> None:
    checks.append({"ok": ok, "code": code, "message": message})


def validate(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    root = root.resolve()
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        return {"ok": False, "root": str(root), "checks": [{"ok": False, "code": "missing-skill", "message": "SKILL.md not found."}]}

    text = skill_path.read_text(encoding="utf-8")
    try:
        meta, body = _frontmatter(text)
    except ValueError as exc:
        return {"ok": False, "root": str(root), "checks": [{"ok": False, "code": "frontmatter", "message": str(exc)}]}

    name = meta.get("name", "")
    description = meta.get("description", "")
    compatibility = meta.get("compatibility", "")
    version = meta.get("metadata.version", "")

    _add(checks, bool(NAME_RE.fullmatch(name)), "name-format", f"Skill name is {name!r} and must use lowercase hyphen-case.")
    _add(checks, root.name == name, "name-directory-match", f"Directory {root.name!r} must match frontmatter name {name!r}.")
    _add(checks, 1 <= len(description) <= 1024, "description-length", f"Description length is {len(description)}; expected 1-1024 characters.")
    _add(checks, description.startswith("This skill should be used"), "description-third-person", "Description should begin with a third-person activation phrase.")
    trigger_terms = ["OpenAI-compatible", "gpt-image-2", "base URL", "/v1/images/generations", "mask"]
    missing_terms = [term for term in trigger_terms if term.lower() not in description.lower()]
    _add(checks, not missing_terms, "description-triggers", "Description contains explicit API/model/edit triggers." if not missing_terms else "Missing trigger terms: " + ", ".join(missing_terms))
    _add(checks, "Do not select" in description, "description-negative-boundary", "Description includes a negative activation boundary.")
    _add(checks, len(compatibility) <= 500, "compatibility-length", f"Compatibility length is {len(compatibility)}; maximum is 500.")
    _add(checks, version == __version__, "version-consistency", f"Frontmatter version {version!r} must equal code version {__version__!r}.")
    _add(checks, len(text.splitlines()) <= 500, "skill-line-count", f"SKILL.md has {len(text.splitlines())} lines; expected no more than 500.")
    _add(checks, "## " in body, "skill-body", "SKILL.md contains procedural sections.")

    referenced = sorted(set(PATH_RE.findall(text)))
    missing_paths = [path for path in referenced if not (root / path.rstrip(".,;:)`\"")).exists()]
    _add(checks, not missing_paths, "referenced-paths", "All SKILL.md resource paths exist." if not missing_paths else "Missing paths: " + ", ".join(missing_paths))

    required = [
        "README.md",
        "requirements.txt",
        "scripts/generate_image.py",
        "scripts/edit_image.py",
        "scripts/build_prompt.py",
        "scripts/prompt_doctor.py",
        "references/agent-routing.md",
        "references/api-compatibility.md",
        "assets/prompt-brief.schema.json",
        "evals/trigger-cases.json",
    ]
    missing_required = [path for path in required if not (root / path).is_file()]
    _add(checks, not missing_required, "required-files", "Required package files exist." if not missing_required else "Missing required files: " + ", ".join(missing_required))

    try:
        schema_file = json.loads((root / "assets/prompt-brief.schema.json").read_text(encoding="utf-8"))
        _add(checks, schema_file == brief_schema(), "schema-sync", "Machine-readable brief schema matches the compiler schema.")
    except Exception as exc:
        _add(checks, False, "schema-sync", f"Cannot validate brief schema: {exc}")

    example_failures: list[str] = []
    for path in sorted((root / "examples/briefs").glob("*.json")):
        try:
            brief = load_brief(path)
            profile, operation = resolve_prompt_context(brief)
            prompt = build_prompt(brief, profile=profile, operation=operation)
            review = lint_prompt(prompt, operation=operation, profile=profile, model_family="gpt-image-2")
            review.enforce(strict=True)
        except Exception as exc:
            example_failures.append(f"{path.name}: {exc}")
    _add(checks, not example_failures, "example-briefs", "All example briefs compile and pass strict prompt review." if not example_failures else "Example failures: " + " | ".join(example_failures))

    try:
        fixtures = json.loads((root / "evals/trigger-cases.json").read_text(encoding="utf-8"))
        cases = fixtures.get("cases", [])
        ids = [case.get("id") for case in cases]
        expected = {case.get("expected") for case in cases}
        fixture_ok = (
            fixtures.get("skill") == name
            and fixtures.get("version") == __version__
            and len(cases) >= 8
            and len(ids) == len(set(ids))
            and {"select", "do-not-select"}.issubset(expected)
            and all(case.get("prompt") for case in cases)
        )
        _add(checks, fixture_ok, "trigger-fixtures", f"Trigger fixtures contain {len(cases)} unique positive/negative cases.")
    except Exception as exc:
        _add(checks, False, "trigger-fixtures", f"Cannot validate trigger fixtures: {exc}")

    return {"ok": all(item["ok"] for item in checks), "root": str(root), "version": __version__, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the image2-api Agent Skill package.")
    parser.add_argument("--skill-root", default=str(SKILL_ROOT_DEFAULT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.skill_root))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"image2-api skill validation: {'PASS' if result['ok'] else 'FAIL'}")
        for check in result["checks"]:
            mark = "OK" if check["ok"] else "FAIL"
            print(f"[{mark}] {check['code']}: {check['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
