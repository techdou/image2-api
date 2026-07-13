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

A provider may expose GPT Image 2 under an alias such as `image-2`. Configure both fields:

```dotenv
IMAGE_API_MODEL=image-2
IMAGE_API_MODEL_FAMILY=gpt-image-2
```

Allowed families:

- `auto` — infer from recognized official model names;
- `gpt-image-2` — apply GPT Image 2-specific validation to an alias;
- `gpt-image-1.5` — identify the earlier GPT Image family;
- `generic` — use conservative relay-portability checks.

When `auto` cannot recognize an alias, the CLI emits a warning instead of silently pretending the model is GPT Image 2.

## GPT Image 2 request checks

The local validator applies these current model rules:

- quality: `low`, `medium`, `high`, or `auto`;
- output format: PNG, JPEG, or WebP;
- background: `auto` or `opaque`; official GPT Image 2 does not support transparent output;
- output compression: 0–100, only for JPEG or WebP;
- output count: 1–10 per CLI run;
- custom dimensions: GPT Image 2 accepts any resolution satisfying these constraints (per OpenAI image-generation guide): each edge ≤ 3840 px; both edges multiples of 16; total pixels 655,360–8,294,400; long-to-short edge ratio ≤ 3:1; 1K/2K/4K tiers map roughly to longest edge ~1024 / ~2048 / ~3840; common sizes include 1024×1024, 1536×1024, 1024×1536, 2048×2048, 2048×1152, 3840×2160, 2160×3840; aspect ratios are flexible (1:1, 2:3, 3:2, 16:9, 9:16, etc.);
- this skill defaults to 2880×2880 (max legal square, 8,294,400 px) since most relays bill per-call, not per-pixel; for 16:9 use `3840x2160`, for 9:16 use `2160x3840`, for 4:5 use `2304x2880`; override with `--size` when a smaller output is desired;
- `input_fidelity` is removed for GPT Image 2 because the model processes image inputs at high fidelity automatically.

Third-party relays may cap resolution or remap sizes. GPT Image 2 natively supports up to 4K (3840px longest edge); verify a relay passes through your requested size by checking actual output dimensions in `metadata.json`.

## Edit inputs and masks

- A request accepts 1–16 source/reference images.
- Each source image must be PNG, JPEG/JPG, or WebP and smaller than 50 MB.
- The mask must be a PNG smaller than 4 MB.
- The mask must have an alpha channel and at least one transparent pixel.
- The mask dimensions must match the first source image.
- The first source image does not need to use the same file format as the PNG mask.

The mask guides the model's edit region but is not a pixel-perfect compositor boundary.

## Extra parameters

Use repeated `--extra-param KEY=VALUE` only for provider-documented extensions. Values are parsed as JSON when possible.

Standard request fields cannot be overridden through `--extra-param`. This prevents a custom parameter from bypassing validated values such as `model`, `prompt`, `size`, `quality`, `n`, images, or mask.

For a generic model family, provider-specific fields such as `input_fidelity` may be passed when documented. For `gpt-image-2`, the client removes `input_fidelity`.

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
