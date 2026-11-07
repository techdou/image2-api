# OpenAI-compatible relay configuration

## Request routes

The client uses OpenAI Images API-shaped requests:

- generation: `POST {base_url}/images/generations` with JSON;
- edit: `POST {base_url}/images/edits` with multipart form data.

A typical root is:

```text
https://relay.example.com/v1
```

Use full endpoint overrides only when the provider does not follow that layout.

## Authentication and metadata safety

The default header is `Authorization: Bearer <IMAGE_API_KEY>`. Relay-specific headers can be supplied with `IMAGE_API_EXTRA_HEADERS`.

The run metadata records only whether a key is configured and the names of extra headers. It does not persist credential values. Base64 image payloads are omitted from response summaries. HTTP(S) response URLs retain only scheme, host, and path; query strings and fragments are removed because they often carry signatures or temporary credentials.

## Model aliases and capability families

A provider may expose an official model under a custom alias. Configure both the provider-facing name and the underlying family:

```dotenv
IMAGE_API_MODEL=image-2.6-pro
IMAGE_API_MODEL_FAMILY=gpt-image-2.6
```

Allowed families:

- `auto` — infer from recognized official model names;
- `gpt-image-2.6` — Flare/Sunburst capabilities, including animated GIF, native SVG and `xhigh|max`;
- `gpt-image-2.5` — Flare/Sunburst capabilities, including `xhigh|max`;
- `gpt-image-2` — GPT Image 2 capabilities;
- `gpt-image-1.5` — earlier GPT Image family;
- `generic` — conservative relay-portability behavior.

The official GPT Image 2.6 and 2.5 Flare and Sunburst model IDs, 2.5 snapshots, and GPT Image 2 IDs are recognized automatically. When `auto` cannot recognize a relay alias, the CLI warns instead of guessing its capability family.

## GPT Image 2.6 and 2.5 still-image checks

The local validator applies these current rules to Flare and Sunburst:

- quality: `low`, `medium`, `high`, `xhigh`, `max`, or `auto`;
- output format: PNG, JPEG, or WebP;
- background: `auto`, `opaque`, or `transparent`;
- transparent output requires PNG or WebP;
- output compression: 0-100, only for JPEG or WebP;
- output count: 1-10 per CLI run;
- custom size: each edge <= 3840 px, both edges multiples of 16, total pixels 655,360-8,294,400, and long:short ratio <= 3:1;
- outputs above 3,686,400 pixels (`2560x1440`) are accepted but reported as an experimental resolution tier.

Use `gpt-image-2.6-flare` for fast iteration and `gpt-image-2.6-sunburst` for detailed work or precise edits. Compare them with the same prompt, references, size, format and quality.

## Animated GIF output

Use `output_format=gif` with a GPT Image 2.6 model. Generation uses JSON and reference-guided animation uses multipart form data with still input images. GIF is an output format. Edit inputs remain PNG, JPEG or WebP.

| Request field | Supported values | Default |
|---|---|---|
| `frame_count` | 2–16 | 9 |
| `frame_duration_ms` | 20–2000 ms per frame, encoded to the nearest 10 ms | 200 |
| `size` | `auto` or positive dimensions that are multiples of 16 | `auto` for GIF |

The Images API applies its model-specific frame limits and total request pixel budget. If the provider rejects the size, use `auto` or reduce the dimensions, frames or batch size. GIF excludes masks, streaming, partial images, custom compression and the transparent background setting. The provider must enable GIF access for the project or relay.

```bash
python scripts/edit_image.py --image mascot.png \
  --model gpt-image-2.6-sunburst --output-format gif \
  --prompt "Preserve the mascot design and background. Animate a slow blink, then return to the original pose and loop." \
  --frame-count 6 --frame-duration-ms 160 --dry-run --json
```

With MCP, pass `image_paths`, `model`, `output_format`, `frame_count`, `frame_duration_ms` and `dry_run` to `edit_image`. Both entry points preserve the original animation bytes and reject a still image or single-frame GIF returned for an animation request. The CLI rejects GIF responses over 64 MiB, over 16 frames, or with frame or canvas dimensions exceeding 3840 px per edge or 8,294,400 pixels before decoding pixels.

## Native SVG output

Use GPT Image 2.6 Flare or Sunburst with `output_format=svg` on `POST /v1/images/generations`. The API uses the image model to produce a reference and returns an editable UTF-8 SVG document. A request accepts one image and excludes streaming, partial images and custom compression. The edits endpoint accepts raster inputs and returns raster output. Set the prompt's background requirements directly for vector artwork.

```bash
python scripts/generate_image.py --model gpt-image-2.6-sunburst --output-format svg \
  --prompt "Design a coffee-bean mark with editable geometric paths, two solid fills and clear negative space." \
  --dry-run --json
```

MCP uses `generate_image` with `output_format="svg"`. Omit the format to keep the default PNG output. The CLI saves the original SVG bytes, records its viewport metadata when present, and checks for common active elements and external references before saving. Use a vector editor or image viewer to inspect the file.

See the [OpenAI SVG generation guide](https://developers.openai.com/api/docs/guides/image-generation#generate-svg-output).

## Format-aware fallback and partial results

GIF and SVG requests try profiles configured for GPT Image 2.6. A provider's explicit unsupported-format or missing-format-access error can advance the chain. Other 400/403 responses follow the normal fallback policy.

When a later image in a batch fails, JSON reports `ok=false`, `partial=true`, the saved image paths and the run directory. The CLI exits with status 1 and retains response summary and metadata for the run.

See the [OpenAI Image API guide](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output).

## GPT Image 2 request checks

GPT Image 2 keeps the same flexible-size geometry constraints but supports only `low`, `medium`, `high`, or `auto` quality. Transparent output is available in preview and must use PNG or WebP. The validator emits a preview warning rather than rejecting the request.

For edit/reference workflows, the skill removes `input_fidelity` from GPT Image 2 requests because the API does not allow changing it; GPT Image 2 processes image inputs at high fidelity automatically. The skill does not assume this rule for unrelated relay families.

## Defaults and relay caveats

The CLI uses `2048x2048` for still raster images, `auto` for GIF and SVG size, and `quality=high` for both. The configured default model remains `gpt-image-2` for backward compatibility with existing third-party relays; upgrading the skill does not assume that every relay already exposes Flare or Sunburst.

Third-party relays may cap resolution, remap model aliases, ignore transparency, reject `xhigh|max`, or omit edit/mask support even when the request shape is OpenAI-compatible. Verify requested vs actual output dimensions in `metadata.json`.

## Provider verification

When dimensions or transparency are important, test the configured relay with one candidate before using it in a batch. Compare the actual width and height in `metadata.json`. For alpha output, request PNG or WebP with `background=transparent`, describe the transparent background in the prompt, and inspect the alpha channel in the saved file. A successful HTTP response alone does not establish that the provider honored these options.

## Edit inputs and masks

- A request accepts 1-16 source/reference images.
- Each source image must be PNG, JPEG/JPG, or WebP and smaller than 50 MB.
- A mask must also be smaller than 50 MB.
- The mask and first source image must use the same file format and dimensions.
- The mask must contain an alpha channel and at least one transparent pixel.
- PNG and WebP are practical masked-edit formats; JPEG cannot satisfy the alpha-channel requirement.
- The client sends the mask using its actual MIME type instead of assuming PNG.

The mask guides the model's edit region but is not a pixel-perfect compositor boundary.

## Extra parameters

Use repeated `--extra-param KEY=VALUE` only for provider-documented extensions. Values are parsed as JSON when possible.

Standard request fields cannot be overridden through `--extra-param`. This prevents a custom parameter from bypassing validated values such as `model`, `prompt`, `size`, `quality`, `n`, images, or mask.

For a generic model family, provider-specific fields such as `input_fidelity` may be passed when documented. For `gpt-image-2`, the client removes `input_fidelity`; GPT Image 2.5 parameters are validated independently.

## Response shapes

Supported image entries include:

```json
{"data":[{"b64_json":"..."}]}
```

```json
{"data":[{"url":"https://..."}]}
```

The parser also recognizes common relay variants: `images`, `image`, `image_base64`, `base64`, `image_url`, data URLs, and direct string entries.

A response with no supported image entry fails explicitly. This commonly indicates an asynchronous job schema or a provider-specific response contract.

## Relay capability acceptance

Use this sequence for a new provider:

1. `python scripts/doctor.py`
2. generation `--dry-run --json`
3. `python scripts/doctor.py --probe` for a real low-quality request
4. one standard-size generation
5. one edit with a single source image
6. multiple references
7. mask support
8. flexible size
9. multiple outputs or sequential batching

Document any unsupported capability instead of assuming OpenAI compatibility implies full feature parity.

## Multi-provider fallback

When `IMAGE_API_PROVIDERS` is set in `.env`, the legacy single-provider
variables (`IMAGE_API_KEY`, `IMAGE_API_BASE_URL`, etc.) are ignored. Each
provider is fully self-contained under its own `IMAGE_API_<NAME>_*` set
and providers are tried in the order listed.

```dotenv
IMAGE_API_PROVIDERS=primary,backup

IMAGE_API_PRIMARY_KEY=replace_with_provider_token
IMAGE_API_PRIMARY_BASE_URL=https://primary.example.com/v1
IMAGE_API_PRIMARY_MODEL=gpt-image-2
IMAGE_API_PRIMARY_MODEL_FAMILY=gpt-image-2
IMAGE_API_PRIMARY_MAX_RETRIES=2

IMAGE_API_BACKUP_KEY=replace_with_provider_token
IMAGE_API_BACKUP_BASE_URL=https://backup.example.com/v1
IMAGE_API_BACKUP_MODEL=gpt-image-2
IMAGE_API_BACKUP_MODEL_FAMILY=gpt-image-2
IMAGE_API_BACKUP_MAX_RETRIES=2
```

A provider triggers fallback when:

- The HTTP response status code is in `IMAGE_API_FALLBACK_STATUS`
  (default `429, 500, 502, 503, 504`), **or**
- A network error occurs (timeout, connection refused, DNS failure) when
  `network_error` is included in the fallback status string (it is by default).

Within a single provider, the configured `IMAGE_API_<NAME>_MAX_RETRIES`
(default 2) internal retries are exhausted before moving on. So a primary
that fails twice with 503 will yield to the next provider.

Ordinary malformed requests stop the chain. For GIF and SVG, an explicit provider error about unsupported output or missing format access can also advance the chain.

When every provider fails, the skill raises `ProviderChainError` whose
`.attempts` attribute is a list describing each provider's outcome.
Inspect `response_summary.json` for the `provider` field on each successful
response; the chain error message includes the per-provider failure summary.

Run `doctor.py` to confirm the chain layout:

```text
chain: 2 providers, fallback on status [429, 500, 502, 503, 504] network=True
  provider primary (primary): https://primary.example.com/v1 model=gpt-image-2 key_set=True
  provider backup (standby): https://backup.example.com/v1 model=gpt-image-2 key_set=True
```

The ImageAPIClient API stays identical whether one or many providers are
configured; existing scripts and CI need no changes.
