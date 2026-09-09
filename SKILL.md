---
name: image2-api
description: This skill should be used when the user asks to generate, edit, localize, composite, or batch-create images through an OpenAI-compatible Images API or a third-party GPT Image relay. Trigger on explicit mentions of gpt-image-2.5, gpt-image-2, Flare, Sunburst, an image model alias, custom base URL, /v1/images/generations, /v1/images/edits, API-based image generation, prompt compilation or review for an API call, reference images, masks, or reproducible image run metadata. Do not select it solely for ordinary built-in image generation when no API or relay workflow is requested.
compatibility: Requires Python 3.10+, packages in requirements.txt, and network access for live API calls. Prompt compilation, linting, dry runs, validation, and tests work offline.
metadata:
  version: "1.4.0"
  format: "agentskills.io"
---

# Image 2 API

Use this skill only for an explicit OpenAI-compatible Images API or third-party relay workflow. Keep ordinary host-product image generation outside this skill unless the user specifically requests API execution, relay configuration, model-specific prompt preparation, or reproducible local artifacts.

## Route the request

| Request | Command |
|---|---|
| Compile structured requirements into a GPT Image prompt | `python scripts/build_prompt.py` |
| Review an existing prompt without calling the API | `python scripts/prompt_doctor.py` |
| Generate from text | `python scripts/generate_image.py` |
| Edit, localize, composite, or use reference images/masks | `python scripts/edit_image.py` |
| Compare generated candidates | `python scripts/make_contact_sheet.py` |
| Diagnose configuration or probe a relay | `python scripts/doctor.py` |
| Validate this skill package | `python scripts/validate_skill.py` |

## Choose the model

For official GPT Image 2.5 workflows:

- **Flare** — `gpt-image-2.5-flare`: choose when speed and iteration rate are the priority.
- **Sunburst** — `gpt-image-2.5-sunburst`: choose when demanding final quality, editing precision, or subject preservation are the priority.

For an existing GPT Image 2 workflow that already meets quality requirements, test Flare first and compare latency with the same prompt, references, dimensions, format, and explicit quality. When GPT Image 2 quality is insufficient, test Sunburst first. Do not silently override an explicitly requested model.

Keep the default relay configuration backward compatible. A third-party alias should set `IMAGE_API_MODEL_FAMILY=gpt-image-2.5` or `gpt-image-2` explicitly so capability validation remains active.

## Configuration modes

This skill supports two configuration modes. Pick one.

- **Single-provider (default).** Set `IMAGE_API_KEY`, `IMAGE_API_BASE_URL`, `IMAGE_API_MODEL`, `IMAGE_API_MODEL_FAMILY`.
- **Multi-provider with automatic fallback.** Set `IMAGE_API_PROVIDERS=fenno,backup` plus an `IMAGE_API_<NAME>_*` block per provider. The skill tries providers in order; a configured 429/5xx or network failure moves to the next provider.

See `references/api-compatibility.md` for the full schema. Read `references/agent-routing.md` when the activation boundary is unclear.

## Execute the workflow

1. **Resolve the skill root.** Run scripts from this directory or invoke them by absolute path. Store user assets outside the installed skill directory.
2. **Classify the operation.** Choose `generate`, `edit`, prompt-only, or diagnostic.
3. **Resolve the model family.** Official Flare/Sunburst names map to `gpt-image-2.5`; aliases should declare their underlying family.
4. **Inspect inputs.** Confirm reference-image order, mask presence, exact text, identity/brand invariants, output purpose, model alias, output format, and intended size.
5. **Compile or write the prompt.** Prefer a structured visual brief for complex assets. Use concrete visual decisions rather than legacy quality keywords.
6. **Review locally.** Run `prompt_doctor.py` or use the generation/edit command's default `--prompt-lint warn`. Use strict mode for production templates, exact text, diagrams, localization, and repeatable automation.
7. **Dry-run the request.** Confirm endpoint, resolved model family, dimensions, quality, background, output format, count, image roles, mask, and sanitized metadata.
8. **Execute the API call.** Start with low/medium for exploration. Raise quality only when a concrete requirement is unmet; GPT Image 2.5 additionally supports `xhigh` and `max`.
9. **Inspect every output.** Check prompt adherence, text accuracy, hierarchy, crop, geometry, visual artifacts, reference preservation, and real alpha transparency when requested.
10. **Return artifacts and provenance.** Report image paths and the run directory containing `prompt.txt`, `prompt_review.json`, `request.json`, `response_summary.json`, and `metadata.json`.

## Build prompts

For complex work, organize the prompt as a maintainable creative brief:

1. deliverable and intended use;
2. scene and background;
3. subject and action;
4. key visible details;
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

For literal text, quote the exact copy, specify placement and hierarchy, request it once verbatim, and prohibit extra text. For recurring identities, products, logos, or exact layouts, use approved reference images through edit mode rather than prompt-only regeneration.

Read `references/gpt-image-prompt-guide.md` for prompting/model-selection guidance and `references/prompt-recipes.md` for task recipes.

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
  --model gpt-image-2.5-sunburst \
  --model-family gpt-image-2.5 \
  --quality high \
  --strict
```

Read `references/prompt-brief-schema.md` when constructing JSON briefs. The machine-readable schema is `assets/prompt-brief.schema.json`.

## Generate

GPT Image 2 and 2.5 support flexible `WIDTHxHEIGHT` sizes when both edges are multiples of 16, each edge is at most 3840 px, the long:short ratio is at most 3:1, and total pixels are 655,360-8,294,400. Above 3,686,400 pixels (`2560x1440`) is an experimental resolution tier. Third-party relays may impose stricter limits.

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --prompt-profile project-hero \
  --model gpt-image-2.5-flare \
  --model-family gpt-image-2.5 \
  --size 1536x1024 \
  --quality high \
  --count 4 \
  --batch-mode sequential \
  --output-dir output/project-hero
```

For transparent assets, set `--background transparent` and use `--output-format png` or `webp`. GPT Image 2 transparency is a preview capability; GPT Image 2.5 supports transparent backgrounds directly.

Use `--dry-run --json` before a live call when the relay, alias, endpoint, model family, or extra parameters are new.

## Edit

```bash
python scripts/edit_image.py \
  --image primary.png \
  --image identity-reference.png \
  --prompt-file edit-prompt.txt \
  --prompt-profile edit \
  --model gpt-image-2.5-sunburst \
  --model-family gpt-image-2.5 \
  --quality high \
  --output-dir output/revision-01
```

For a masked edit, add `--mask mask.png`. The mask and first image must have the same format and dimensions, each must be below 50 MB, and the mask must contain an alpha channel with a transparent edit region. PNG or WebP are practical masked-edit formats because JPEG has no alpha channel. Treat the mask as model guidance, not a guaranteed pixel-perfect clipping boundary.

## Configure safely

Set configuration in an uncommitted `.env` or process environment:

```dotenv
IMAGE_API_KEY=replace_with_token
IMAGE_API_BASE_URL=https://relay.example.com/v1
IMAGE_API_MODEL=image-2
IMAGE_API_MODEL_FAMILY=gpt-image-2
```

For a relay alias that maps to GPT Image 2.5:

```dotenv
IMAGE_API_MODEL=image-2.5-pro
IMAGE_API_MODEL_FAMILY=gpt-image-2.5
```

Never place credentials in prompts, command arguments, source control, request metadata, or examples. Treat signed output URLs and custom authorization headers as secrets. Use `--extra-param` only for documented relay extensions; it cannot override validated standard request fields.

Read `references/api-compatibility.md` for request/response behavior and `references/troubleshooting.md` after a failed diagnosis.

## Complete the task

A successful API task must produce or explicitly report:

- the final prompt or compiled brief;
- prompt-review status and deliberately accepted warnings;
- generated or edited image files;
- the run directory and sanitized metadata;
- any relay capability limitation that prevented part of the request.

Do not claim live generation succeeded when only prompt compilation, linting, or dry-run validation was performed.
