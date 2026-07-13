# Agent Skills compliance notes

This package follows the open Agent Skills directory model used by Anthropic-compatible agents.

## Package invariants

- The parent directory name is `image2-api` and matches the frontmatter `name`.
- `SKILL.md` is the entry point.
- Frontmatter contains a specific third-person `description` that includes positive triggers and a negative activation boundary.
- The main skill body stays procedural and concise; detailed material lives one level down in `references/`.
- Executable behavior lives in `scripts/` and exits non-zero on validation or execution failure.
- Reusable static resources live in `assets/`.
- Examples are separate from operational instructions.
- Trigger fixtures live in `evals/` and are intended for host-level description testing.

## Progressive disclosure

The host should initially index only frontmatter. After activation, read `SKILL.md`. Load a reference file only when the current subtask requires it. Avoid chains where one reference points to another reference required for basic execution.

## Local validation

Run:

```bash
python scripts/validate_skill.py
```

When the `skills-ref` CLI is installed, also run:

```bash
skills-ref validate .
```

The local validator checks structural invariants, referenced paths, version consistency, example briefs, prompt review, and trigger fixtures. It does not prove that every host agent will route identically; use the fixtures in `evals/trigger-cases.json` to evaluate descriptions in the target agent runtime.
