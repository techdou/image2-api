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

## Per-provider size capability (实测 2026-07)

Different providers in the chain support different size sets. **Pick a provider that supports the requested size before calling, not after a 400.**

| Provider | model alias | 全 size 支持 | 实测通过 |
|---|---|---|---|
| **fushengyunsuan** | gpt-image-2 | ✅ 是 | 1024x1024, 1536x1024, 1024x1536, 1792x1024, 1024x1792, 2048x2048, 2048x1152 |
| **agnes** | agnes-image-2.1-flash | ⚠️ 部分 | 1024x1024 OK；其他 size 偶发 503（上游繁忙，不代表不支持），需重试或换 provider |
| **imagepro** | image-pro | ❌ 仅正方形 | 1024x1024, 2048x2048 OK；1536x1024, 1024x1536 报 400 |
| cunai | gpt-image-2 | 未测 | 用前 curl 探活 |
| jbbtoken / jbbtoken_vip / luminai | gpt-image-2 / vip-image | 未测 | 用前 curl 探活 |

### 用 size 选 provider 的策略

1. **需要横版/竖版/特殊比例（公众号横版、小红书竖版、3:2、16:9）**：优先用 `fushengyunsuan`（实测 7 种 size 全过）。
2. **agnes 上游频繁 503**：不要依赖 agnes 做主力 size 任务，可作 fallback。
3. **imagepro 只能正方形**：横/竖版请求会被拒（400），fallback_status 不会触发（400 不在 fallback 列表），所以请求会直接失败。如果要用非正方形 size，**不要把 imagepro 排在主位**。
4. **未知 provider 的 size 能力**：先 curl 探活再正式调用：
   ```bash
   curl -X POST "$URL" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"model":"<alias>","prompt":"test","size":"<W>x<H>","quality":"low","n":1}'
   ```
   HTTP 200 = 支持；HTTP 400 = 不支持该 size；HTTP 503/504 = 上游繁忙，重试或换 provider。
5. **provider 排序建议**（按 size 能力）：
   ```dotenv
   IMAGE_API_PROVIDERS=fushengyunsuan,cunai,imagepro,jbbtoken_vip,agnes,luminai,jbbtoken
   ```
   `fushengyunsuan` 主力（size 全 + 稳定），`imagepro` 作 fallback（正方形场景）。如果常用非正方形 size，考虑把 `imagepro` 后移或移除。

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

## Multi-provider fallback

When `IMAGE_API_PROVIDERS` is set in `.env`, the legacy single-provider
variables (`IMAGE_API_KEY`, `IMAGE_API_BASE_URL`, etc.) are ignored. Each
provider is fully self-contained under its own `IMAGE_API_<NAME>_*` set
and providers are tried in the order listed.

```dotenv
IMAGE_API_PROVIDERS=fenno,backup

IMAGE_API_FENNO_KEY=sk-...
IMAGE_API_FENNO_BASE_URL=https://api.fenno.ai/v1
IMAGE_API_FENNO_MODEL=gpt-image-2
IMAGE_API_FENNO_MODEL_FAMILY=gpt-image-2
IMAGE_API_FENNO_MAX_RETRIES=2

IMAGE_API_BACKUP_KEY=sk-...
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

Status codes **not** in the fallback set terminate the request immediately
(e.g. 400 means a malformed payload — switching providers will not help).

When every provider fails, the skill raises `ProviderChainError` whose
`.attempts` attribute is a list describing each provider's outcome.
Inspect `response_summary.json` for the `provider` field on each successful
response; the chain error message includes the per-provider failure summary.

Run `doctor.py` to confirm the chain layout:

```text
chain: 2 providers, fallback on status [429, 500, 502, 503, 504] network=True
  provider fenno (primary): https://api.fenno.ai/v1 model=gpt-image-2 key_set=True
  provider backup (standby): https://backup.example.com/v1 model=gpt-image-2 key_set=True
```

The ImageAPIClient API stays identical whether one or many providers are
configured; existing scripts and CI need no changes.
