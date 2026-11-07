---
name: image2-api
description: "Generate or edit images through the OpenAI-compatible Images API, a GPT Image relay, or image2-api MCP. Use when the user names this API, an exact API model, or a relay, or continues an established image API workflow. Supports native GIF, editable SVG, API prompt review, dry runs, and provider diagnostics. Leave ordinary built-in image generation, local conversion, and deterministic diagrams to their usual tools."
license: MIT
metadata:
  version: "1.6.0"
---

# Image 2 API

## Route the request

Use this workflow when the user invokes the skill, requests an image API or relay, or refers back to an established image API workflow. The presence of an installed MCP server alone does not establish that workflow. See [routing examples](references/agent-routing.md) for ambiguous requests and format constraints.

| Intent | Tool on the registered `image2-api` server | CLI from the skill root |
|---|---|---|
| Generate an image from text | `generate_image` | `python scripts/generate_image.py` |
| Edit an image or generate with visual references | `edit_image` | `python scripts/edit_image.py` |
| Review an existing prompt offline | `check_prompt` | `python scripts/prompt_doctor.py` |
| Compile a structured brief | | `python scripts/build_prompt.py` |
| Inspect provider configuration offline | `diagnose_api` | `python scripts/doctor.py` |

Use the matching tool on the registered `image2-api` server when available. Use the CLI if that server is unavailable or the request needs options the tool does not expose, such as strict prompt review or transparent edits. Keep any transport the user explicitly requires. Check the tool schema or script `--help` before adding optional arguments. See [setup and requirements](references/integration.md).

## Choose format and model

- **Still image.** Use the configured image model and default PNG. Preserve a model or format the user explicitly requests. For transparency, use PNG or WebP with `background=transparent`.
- **GIF.** Select `output_format=gif` with a GIF-capable GPT Image 2.6 provider. Use generate for text-only requests and edit for still references. Describe the motion and loop. Pass `frame_count` and `frame_duration_ms` when timing matters. GIF edits take references without a mask. Start with `size=auto` unless dimensions are specified.
- **SVG.** Select `output_format=svg` only for an explicit SVG or editable vector deliverable in this API workflow. Use GPT Image 2.6 with generate and one output. If a source image must drive the result, surface the SVG edit limitation before generating. Keep the user's source and output requirements intact.
- **Model selection.** Use `gpt-image-2.6-flare` for fast iteration and `gpt-image-2.6-sunburst` for detailed work when a 2.6 model is needed and the provider supports it. For a relay alias, set the documented capability family. See [request parameters and examples](references/api-compatibility.md).

## Prepare and execute

1. Confirm the intended deliverable and material constraints. For edits, pass the primary canvas first and state what to preserve. Keep literal image text in the requested language. Use the [prompt guide](references/gpt-image-prompt-guide.md), [recipes](references/prompt-recipes.md), or [brief schema](references/prompt-brief-schema.md) only as needed.
2. Keep prompt-only, configuration inspection, and dry-run requests offline. A dry run uses MCP `dry_run=true` or CLI `--dry-run --json`, writes a local request plan, and returns no image. Use it before live generation when the provider, alias, endpoint or format is unfamiliar.
3. Submit a live request when the user asks for actual generation or editing through this workflow. Keep credentials out of prompts, arguments, and output. Use `doctor.py --probe` only for a requested live probe. CLI `--test` is a live low-quality call.
4. Return actual output paths, the run directory, and relevant warnings. Report dry runs as validation. If a batch partly succeeds, report saved paths and the failure. Check the result before repeating a live request through another transport. Use [troubleshooting](references/troubleshooting.md) as needed.
