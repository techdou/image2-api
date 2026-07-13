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
- custom dimensions: both edges are positive multiples of 16, each edge is below 3840 px, aspect ratio is at most 3:1, and total pixels are 655,360–8,294,400;
- resolutions above the 2560×1440 reliability boundary are treated as experimental;
- `input_fidelity` is removed for GPT Image 2 because the model processes image inputs at high fidelity automatically.

Third-party relays may implement a narrower size set. Prefer `1024x1024`, `1536x1024`, and `1024x1536` until flexible sizes are proven.

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
