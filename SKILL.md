---
name: image2-api
description: This skill should be used when the user asks to generate, edit, localize, composite, or batch-create images through an OpenAI-compatible Images API or a third-party GPT Image 2 relay. Trigger on explicit mentions of gpt-image-2, an image model alias, custom base URL, /v1/images/generations, /v1/images/edits, API-based image generation, prompt compilation or review for an API call, reference images, masks, or reproducible image run metadata. Do not select it solely for ordinary built-in image generation when no API or relay workflow is requested.
compatibility: Requires Python 3.10+, packages in requirements.txt, and network access for live API calls. Prompt compilation, linting, dry runs, validation, and tests work offline.
metadata:
  version: "1.2.0"
  format: "agentskills.io"
---

# Image 2 API

Use this skill only for an explicit OpenAI-compatible Images API or third-party relay workflow. Keep ordinary host-product image generation outside this skill unless the user specifically requests API execution, relay configuration, model-specific prompt preparation, or reproducible local artifacts.

## Route the request

| Request | Command |
|---|---|
| Compile structured requirements into a GPT Image 2 prompt | `python scripts/build_prompt.py` |
| Review an existing prompt without calling the API | `python scripts/prompt_doctor.py` |
| Generate from text | `python scripts/generate_image.py` |
| Edit, localize, composite, or use reference images/masks | `python scripts/edit_image.py` |
| Compare generated candidates | `python scripts/make_contact_sheet.py` |
| Diagnose configuration or probe a relay | `python scripts/doctor.py` |
| Validate this skill package | `python scripts/validate_skill.py` |

## Configuration modes

This skill supports two configuration modes. Pick one.

- **Single-provider (default).** Set `IMAGE_API_KEY`, `IMAGE_API_BASE_URL`,
  `IMAGE_API_MODEL`, `IMAGE_API_MODEL_FAMILY`. Use for one upstream relay
  or direct OpenAI access.
- **Multi-provider with automatic fallback.** Set `IMAGE_API_PROVIDERS=fenno,backup`
  plus an `IMAGE_API_<NAME>_*` block per provider. The skill tries providers
  in order; a 429/5xx or network failure moves to the next provider.
  See `references/api-compatibility.md` for the full schema.

Read `references/agent-routing.md` when the activation boundary is unclear. Read only the task-specific reference files needed for the current request.

## Execute the workflow

1. **Resolve the skill root.** Run scripts from this directory or invoke them by absolute path. Store user assets outside the installed skill directory.
2. **Classify the operation.** Choose `generate` or `edit`, then select the closest prompt profile.
3. **Inspect inputs before execution.** Confirm reference-image order, mask presence, exact text, required identity/brand invariants, output purpose, and relay model alias. Ask only when a missing fact would materially alter identity, literal copy, brand compliance, or the requested edit boundary.
4. **Compile or write the prompt.** Prefer a structured brief for complex assets. Use concrete visual decisions rather than legacy quality keywords.
5. **Review locally.** Run `prompt_doctor.py` or retain the generation/edit command's default `--prompt-lint warn`. Use strict mode for production templates, exact text, diagrams, localization, and repeatable automation.
6. **Validate the request with a dry run.** Confirm endpoint, resolved model family, dimensions, quality, background, count, image roles, mask, and sanitized request metadata.
7. **Execute the API call.** Start with low or medium quality for exploration; use high quality for dense text, final diagrams, close portraits, identity-sensitive edits, and final assets.
8. **Inspect every output when vision is available.** Check prompt adherence, text accuracy, hierarchy, crop, geometry, visual artifacts, and reference preservation. Refine one concrete failure at a time.
9. **Return artifacts and provenance.** Report image paths and the run directory containing `prompt.txt`, `prompt_review.json`, `request.json`, `response_summary.json`, and `metadata.json`.

## Build prompts

For complex work, organize the prompt as a maintainable creative brief:

1. deliverable and intended use;
2. scene and background;
3. subject and action;
4. key visual details;
5. composition and viewpoint;
6. visual treatment, lighting, and palette;
7. exact in-image text and typography;
8. preservation rules, exclusions, and other constraints.

For edits, identify every input by index and role, then state invariants before changes:

```text
Image 1 = primary canvas. Image 2 = identity reference.
Preserve the face, silhouette, proportions, pose, camera angle, and crop exactly.
Change only the background to a warm ceramic-humanistic technology studio.
Keep everything else unchanged. Add no extra text or logos.
```

For literal text, quote the exact copy, specify placement and hierarchy, request it once verbatim, and prohibit extra text. For recurring identities, products, logos, or exact layouts, use approved reference images through edit mode rather than relying on prompt-only regeneration.

Read `references/gpt-image-2-prompt-guide.md` for the complete prompting model and `references/prompt-recipes.md` for task recipes.

## Compile and review

```bash
python scripts/build_prompt.py \
  --brief examples/briefs/open-source-project-hero.json \
  --profile project-hero \
  --lint \
  --strict \
  --output prompt.txt
```

```bash
python scripts/prompt_doctor.py \
  --prompt-file prompt.txt \
  --operation generate \
  --profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --quality high \
  --strict
```

Read `references/prompt-brief-schema.md` when constructing JSON briefs. The machine-readable schema is `assets/prompt-brief.schema.json`.

## Generate

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --prompt-profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --size 1536x1024 \
  --quality medium \
  --count 4 \
  --batch-mode sequential \
  --output-dir outputs/project-hero
```

Use `--dry-run --json` before the live call when the relay, alias, endpoint, or extra parameters are new.

## Edit

```bash
python scripts/edit_image.py \
  --image primary.jpg \
  --image identity-reference.png \
  --prompt-file edit-prompt.txt \
  --prompt-profile edit \
  --model image-2 \
  --model-family gpt-image-2 \
  --quality high \
  --output-dir outputs/revision-01
```

For a masked edit, add `--mask mask.png`. Treat the mask as model guidance, not a guaranteed pixel-perfect clipping boundary.

## Configure safely

Set configuration in an uncommitted `.env` or process environment:

```dotenv
IMAGE_API_KEY=replace_with_token
IMAGE_API_BASE_URL=https://relay.example.com/v1
IMAGE_API_MODEL=image-2
IMAGE_API_MODEL_FAMILY=gpt-image-2
```

Use `IMAGE_API_MODEL_FAMILY` whenever a third-party alias hides the underlying model. This keeps model-specific validation active.

Never place credentials in prompts, command arguments, source control, request metadata, or examples. Treat signed output URLs and custom authorization headers as secrets. Use `--extra-param` only for documented relay extensions; it cannot override validated standard request fields.

Read `references/api-compatibility.md` for request/response behavior and `references/troubleshooting.md` after a failed diagnosis.

## Complete the task

A successful API task must produce or explicitly report:

- the final prompt or compiled brief;
- prompt-review status and any deliberately accepted warnings;
- generated or edited image files;
- the run directory and sanitized metadata;
- any relay capability limitation that prevented part of the request.

Do not claim live generation succeeded when only prompt compilation, linting, or dry-run validation was performed.
