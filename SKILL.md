---
name: image2-api
description: "This skill should be used for image generation, editing, or animated GIF creation with the OpenAI-compatible Images API or a configured relay. Trigger on GPT Image API models such as gpt-image-2.6-flare, gpt-image-2.6-sunburst and gpt-image-2, /v1/images/generations or /v1/images/edits, API prompt review, relay base URL setup, reference images and mask workflows. Prefer the registered image2-api MCP server when this channel is requested or established. Do not select for ordinary built-in image generation, OCR, or file format conversion."
metadata:
  version: "1.6.0"
  compatibility: "Python 3.10+ with requirements.txt. Optional MCP server requires mcp>=1.29,<3. Live image calls require provider access and credentials."
---

# Image 2 API

## Choose the operation

| Task | MCP tool | CLI |
|---|---|---|
| Generate from text | `generate_image` | `python scripts/generate_image.py` |
| Edit, composite, or animate still references | `edit_image` | `python scripts/edit_image.py` |
| Review a prompt offline | `check_prompt` | `python scripts/prompt_doctor.py` |
| Diagnose the configured API | `diagnose_api` | `python scripts/doctor.py` |

Use the registered MCP tool when available. Use the CLI for unregistered clients, structured brief compilation, or request options the tool does not expose. Run scripts from the skill root or use absolute paths. See [integration](references/integration.md) for installation and [agent routing](references/agent-routing.md) for activation examples.

## Choose the model and provider

- Use `gpt-image-2.6-flare` for fast iteration and `gpt-image-2.6-sunburst` for detailed work or precise edits. Honor a model explicitly requested by the user.
- Use `gpt-image-2.6` as the capability family for relay aliases backed by 2.6. The official IDs are recognized automatically. Existing 2.5, 2 and other relay configurations continue to use their configured model.
- Configure the key, base URL, model and family in the environment or an untracked `.env`. For multiple providers, define `IMAGE_API_PROVIDERS` and provider-specific settings. Read [API compatibility](references/api-compatibility.md) for endpoint overrides and fallback.
- Keep keys and signed URLs out of prompts, command arguments, logs and artifacts.

## Prepare and execute

1. Confirm deliverable, format, size, references and their order. For edits, identify the primary image first and state which details to preserve before describing the changes. For exact text, quote the copy and specify its position. Use PNG or WebP with `background=transparent` for alpha output.
2. For complex jobs, compile a brief with `python scripts/build_prompt.py`. Read the [brief schema](references/prompt-brief-schema.md), [prompt guide](references/gpt-image-prompt-guide.md), or [recipes](references/prompt-recipes.md) as needed.
3. Review the prompt and dry-run unfamiliar requests with `--dry-run --json` or MCP `dry_run=true`. Check the selected endpoint, provider model, format, parameters and local warnings. Use strict prompt review for production templates and exact text.
4. Execute with a quality suited to the task. Inspect the resulting files for prompt adherence, visible artifacts and reference preservation. Return the file paths, run directory and material warnings. Use [troubleshooting](references/troubleshooting.md) for errors.

## Animated GIFs

Use GPT Image 2.6 with `output_format=gif`. For text-to-GIF, use generate. To animate a still image, use edit with one or more PNG, JPEG or WebP reference images. Describe the starting pose, one clear motion, camera movement if needed, and how the subject returns to the starting pose.

Set `frame_count` (2–16, default 9) and `frame_duration_ms` (20–2000, default 200) when timing matters. Start with `size=auto` so the provider can fit the frame dimensions and count to its pixel budget. GIF requests require a provider that exposes animated output and exclude masks, streaming, partial images and custom compression.

```bash
python scripts/generate_image.py \
  --model gpt-image-2.6-flare --output-format gif \
  --prompt "A coffee-bean mascot waves once, lowers its hand to the initial pose, and loops smoothly. Fixed camera and background." \
  --frame-count 9 --frame-duration-ms 200 --dry-run --json
```

After checking the request, remove `--dry-run` to submit it. For MCP, use the same parameter names with underscores. Inspect motion and the loop seam in a GIF-capable viewer. The CLI saves the original multi-frame bytes and records the decoded frame count in `metadata.json`. See [GIF request rules and examples](references/api-compatibility.md#animated-gif-output).
