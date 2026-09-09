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
IMAGE_API_MODEL=image-2.5-pro
IMAGE_API_MODEL_FAMILY=gpt-image-2.5
```

Allowed families:

- `auto` — infer from recognized official model names;
- `gpt-image-2.5` — Flare/Sunburst capabilities, including `xhigh|max`;
- `gpt-image-2` — GPT Image 2 capabilities;
- `gpt-image-1.5` — earlier GPT Image family;
- `generic` — conservative relay-portability behavior.

Official names recognized automatically include `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst`, their `2026-09-08` snapshots, and GPT Image 2 names. When `auto` cannot recognize a relay alias, the CLI warns instead of guessing its capability family.

## GPT Image 2.5 request checks

The local validator applies these current rules to Flare and Sunburst:

- quality: `low`, `medium`, `high`, `xhigh`, `max`, or `auto`;
- output format: PNG, JPEG, or WebP;
- background: `auto`, `opaque`, or `transparent`;
- transparent output requires PNG or WebP;
- output compression: 0-100, only for JPEG or WebP;
- output count: 1-10 per CLI run;
- custom size: each edge <= 3840 px, both edges multiples of 16, total pixels 655,360-8,294,400, and long:short ratio <= 3:1;
- outputs above 3,686,400 pixels (`2560x1440`) are accepted but reported as an experimental resolution tier.

Use `gpt-image-2.5-flare` when speed is the primary goal and `gpt-image-2.5-sunburst` when demanding quality/editing precision is the primary goal. Compare them with the same prompt, references, size, format, and explicit quality before changing multiple variables at once.

## GPT Image 2 request checks

GPT Image 2 keeps the same flexible-size geometry constraints but supports only `low`, `medium`, `high`, or `auto` quality. Transparent output is available in preview and must use PNG or WebP. The validator emits a preview warning rather than rejecting the request.

For edit/reference workflows, the skill removes `input_fidelity` from GPT Image 2 requests because the API does not allow changing it; GPT Image 2 processes image inputs at high fidelity automatically. The skill does not assume this rule for unrelated relay families.

## Defaults and relay caveats

The CLI default remains `2048x2048` and `quality=high`. The configured default model remains `gpt-image-2` for backward compatibility with existing third-party relays; upgrading the skill does not assume that every relay already exposes Flare or Sunburst.

Third-party relays may cap resolution, remap model aliases, ignore transparency, reject `xhigh|max`, or omit edit/mask support even when the request shape is OpenAI-compatible. Verify requested vs actual output dimensions in `metadata.json`.

## Per-provider size capability (2026-07 全测，2026-09-09 复测)

Different providers in the chain support different size sets. **Pick a provider that supports the requested size before calling, not after a 400.**

| Provider | model alias | 全 size 支持 | 实测通过 |
|---|---|---|---|
| **happyevering** | gpt-image-2.5-sunburst (另有 gpt-image-2.5-flare / gpt-image-2-4k) | ✅ 非方形已验证 (2.5) | 2026-09-10 实测 1536x1024 通过，输出尺寸与请求一致 |
| **fushengyunsuan** | gpt-image-2 | ✅ 是 | 2026-07 全测 7 种通过（1024x1024, 1536x1024, 1024x1536, 1792x1024, 1024x1792, 2048x2048, 2048x1152）；2026-09-09 复测 1536x1024 通过，输出尺寸与请求一致 |
| **cunai** | gpt-image-2 | ✅ 非方形已验证 | 2026-09-09 实测 1536x1024 通过，输出尺寸与请求一致（此前"未测"，现已验证） |
| **imagepro** | image-pro | ❌ 仅正方形 | 非正方形（1536x1024）报 400（2026-09-09 复测仍如此）；正方形请求被接受但 **size 参数对输出无效**：2026-09-09 请求 1024x1024 实际返回 2048x2048，输出尺寸固定 2048 方形 |

### 用 size 选 provider 的策略

1. **需要横版/竖版/特殊比例（公众号横版、小红书竖版、3:2、16:9）**：优先用 `happyevering`（2.5 sunburst，2026-09-10 已验证非方形+透明）；`fushengyunsuan`（2026-07 实测 7 种全过，2026-09 复测通过）与 `cunai`（2026-09-09 已验证非方形）作替补。
2. **imagepro 只能正方形，且 size 参数对输出无效**：横/竖版请求会被拒（400），fallback_status 不会触发（400 不在 fallback 列表），所以请求会直接失败。正方形请求虽被接受，实际输出固定 2048x2048——要精确控制输出尺寸不要用 imagepro。非正方形 size 场景**不要把 imagepro 排在主位**。
4. **未知 provider 的 size 能力**：先 curl 探活再正式调用：
   ```bash
   curl -X POST "$URL" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"model":"<alias>","prompt":"test","size":"<W>x<H>","quality":"low","n":1}'
   ```
   HTTP 200 = 支持；HTTP 400 = 不支持该 size；HTTP 503/504 = 上游繁忙，重试或换 provider。
5. **provider 排序建议**（按 size 能力）：
   ```dotenv
   IMAGE_API_PROVIDERS=happyevering,fushengyunsuan,cunai,imagepro
   ```
   `fushengyunsuan` 主力（size 全 + 稳定），`imagepro` 作 fallback（正方形场景）。如果常用非正方形 size，考虑把 `imagepro` 后移或移除。

## Per-provider transparency capability (2026-08 对照实验，2026-09-09 复测)

Transparent output is native to `gpt-image-2.5` (PNG/WebP) and officially supported in preview by `gpt-image-2`. Relay passthrough still varies — **probe before relying on it**:

| Provider | transparent 实测 | 结果 |
|---|---|---|
| **happyevering** | ✅ 可用 (2.5) | 2026-09-10 实测（sunburst）：prompt 含词 + `background=transparent`，返回 RGBA 真透明（1536x1024，alpha 0–254） |
| **fushengyunsuan** | ✅ 可用（有前提） | prompt 显式写 `transparent background` 时 3/3 返回 RGBA（背景 alpha=0、边缘自然羽化）；prompt 不写时 9/9 返回 RGB。`background=transparent` **参数字段未被可靠透传**，决定性通道是 prompt 文本。2026-09-09 复测：prompt 含词 + 参数齐全，1/1 返回 RGBA 真透明，结论仍成立 |
| **cunai** | ✅ 可用 | 2026-09-09 实测：prompt 含词 + `background=transparent` + png，返回 RGBA 真透明（1536x1024） |
| **imagepro** | ❌ 不支持 | prompt 含 transparent + 参数齐全仍返回无 alpha 图像。2026-09-09 复测升级确认：连 `output_format=png` 都被忽略，返回的是 JPEG（RGB）——参数与 prompt 均被忽略，且输出格式不可控 |

### 透明任务工作流

1. **prompt 必须显式写明**，如 `... isolated object on transparent background, no shadow`——这是 fushengyunsuan 实测的决定性变量（单变量对照实验 2026-08-24：同 payload 同 UA，含词 RGBA、不含词 RGB）。同时带 `--background transparent`（对真透传 provider 生效，官方语义正确）。
2. 生成命令带 `--output-format png`（JPEG 无 alpha 通道，本地校验已拦截该组合）。
3. 验收必须查 alpha 通道，不能只看 HTTP 200（`imagepro` 会假装成功）：
   ```python
   from PIL import Image
   img = Image.open("output.png")
   assert img.mode == "RGBA", f"relay ignored transparent: mode={img.mode}"
   lo, _ = img.getchannel("A").getextrema()
   assert lo < 255, "no transparent pixels in output"
   ```
4. 透明输出失败时的排查顺序：先确认 prompt 含 `transparent background` → 换已验证 provider → 隔段时间重试（上游存在能力不一致的节点池，间歇性波动）。不要归因于 UA、`moderation` 等请求字段——已用对照实验排除（2026-08-24）。

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
