# image2-api | 图片生成 API Skill

[English](#english) | [中文](#中文导读)

`image2-api` is an Agent Skill for generating and editing images through an OpenAI-compatible Images API or third-party GPT Image relay. It provides first-class GPT Image 2.5 Flare/Sunburst support, capability-based model validation, `xhigh`/`max`, current transparency rules, and updated mask compatibility checks while preserving GPT Image 2 relay compatibility.

---

## 中文导读

**这是什么**：一个 Agent Skill，通过 OpenAI 兼容的 Images API（或第三方 GPT Image 中转）生成、编辑图片。自 1.5.0 起同时以 MCP server 形式交付，是 AI 生图/改图的**首选渠道**——尤其当画内文字、精确尺寸、透明背景、参考图控制有要求时；也承接 API/中转配置、模型别名、prompt 编译审查等显式工作流。

**快速上手**：

```bash
# 1. 装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 配置秘钥（.env 已被 gitignore，不会上传）
cp .env.example .env
# 编辑 .env，填入 IMAGE_API_KEY 和 IMAGE_API_BASE_URL

# 3. 自检配置（不花额度）
python scripts/doctor.py

# 4. 生成一张图（先 dry-run 校验）
python scripts/generate_image.py --prompt-file prompt.txt --dry-run --json
```

**主要能力**：文生图 · 图生图/编辑/合成/蒙版 · GPT Image 2.5 Flare/Sunburst · 结构化 brief → GPT Image prompt 编译 · prompt 审查 · capability-based 模型校验 · 第三方模型别名支持 · 干跑校验 · 重试与响应归一 · 批量候选 + 接触印样 · Agent Skills 结构校验 · 离线单测 · stdio MCP server（4 tools）。

**MCP 调用（可选）**：`pip install "mcp>=2"` 后把 `mcp_server.py` 注册为 stdio server，即可在 ZCode 等 MCP 客户端直调 4 个 tools：`generate_image` / `edit_image` / `check_prompt`（离线体检）/ `diagnose_api`（连通诊断）。与 CLI 路径等价；凭证仍由脚本自身从 `.env` 加载，不经过 server。详见 SKILL.md「MCP server」一节。

**文档地图**（`references/` 目录）：`agent-routing` 触发边界 · `gpt-image-prompt-guide` prompt 设计与 Flare/Sunburst 选型 · `prompt-recipes` 配方 · `api-compatibility` API 细节 · `troubleshooting` 排错。

**秘钥安全**：真实 `.env`、虚拟环境、IDE 配置、`outputs/` 运行产物均已按 [.gitignore](.gitignore) 排除；推送前已扫描确认无硬编码凭据。

---

Since 1.5.0 this skill also ships as an MCP server and is the preferred channel for image generation/editing requests — especially when in-image text, exact sizes, transparent backgrounds, or reference-image control matter. Use the CLI below for API/relay configuration, model aliases, prompt compilation, and reproducible run metadata.

## What it provides

- Text-to-image calls through `/images/generations`
- Image editing, localization, compositing, multiple references, and masks through `/images/edits`
- Structured JSON brief → GPT Image creative-brief compilation
- Prompt profiles and deterministic prompt review
- GPT Image 2.5 Flare/Sunburst plus third-party model alias support through `IMAGE_API_MODEL_FAMILY`
- Capability-aware validation for quality, flexible sizes, transparency, and legacy parameter differences
- Dry-run request validation before network execution
- Base64 and URL response normalization
- Retry handling and sanitized response summaries
- Image integrity, dimension, format, and SHA-256 metadata
- Sequential candidate generation and contact sheets
- stdio MCP server (`mcp_server.py`) exposing 4 structured tools
- Agent Skills structural validation and trigger fixtures
- Offline unit tests and a local mock relay smoke test

## Package layout

```text
image2-api/
├── SKILL.md
├── README.md
├── mcp_server.py
├── assets/
│   └── prompt-brief.schema.json
├── evals/
│   └── trigger-cases.json
├── examples/
│   ├── briefs/
│   └── prompts/
├── references/
├── scripts/
│   ├── image2lib/
│   ├── build_prompt.py
│   ├── prompt_doctor.py
│   ├── generate_image.py
│   ├── edit_image.py
│   ├── doctor.py
│   ├── validate_skill.py
│   └── smoke_test.py
└── tests/
```

## Install dependencies

```bash
python -m pip install -r requirements.txt
```

Python 3.10 or newer is recommended. Prompt compilation, linting, dry runs, package validation, and tests work without a live API.

## Configure a relay

Copy `.env.example` to `.env` and keep it out of source control:

```dotenv
IMAGE_API_KEY=replace_with_token
IMAGE_API_BASE_URL=https://relay.example.com/v1
IMAGE_API_MODEL=image-2
IMAGE_API_MODEL_FAMILY=gpt-image-2
```

`IMAGE_API_MODEL_FAMILY` is important when the provider renames the model. Use `gpt-image-2.5` for aliases backed by Flare/Sunburst, `gpt-image-2` for GPT Image 2, or `generic` only when the upstream capability is genuinely unknown.

Check configuration without spending credits:

```bash
python scripts/doctor.py
```

Send a real low-quality probe only when desired:

```bash
python scripts/doctor.py --probe
```

## GPT Image 2.5 model selection

For new official OpenAI workflows:

- `gpt-image-2.5-flare` — speed-first, high-quality everyday generation and rapid iteration.
- `gpt-image-2.5-sunburst` — quality-first, especially when precise editing and subject preservation matter.

Both support generation, editing, transparent backgrounds, flexible sizes, and `low|medium|high|xhigh|max|auto`. Keep the default relay model unchanged unless your provider actually exposes a 2.5 alias; this avoids breaking existing third-party configurations.

## Compile a normalized prompt

```bash
python scripts/build_prompt.py \
  --brief examples/briefs/open-source-project-hero.json \
  --profile project-hero \
  --lint \
  --strict \
  --output prompt.txt
```

Print the machine-readable brief schema:

```bash
python scripts/build_prompt.py --print-schema
```

The same schema is stored at `assets/prompt-brief.schema.json`.

## Review an existing prompt

```bash
python scripts/prompt_doctor.py \
  --prompt-file prompt.txt \
  --profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --quality high \
  --strict
```

Prompt review is local and deterministic. It catches common omissions and contradictions; it cannot guarantee artistic quality or perfect model compliance.

## Generate images

Validate first:

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --prompt-profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --size 1536x1024 \
  --quality medium \
  --dry-run \
  --json
```

Execute with an existing relay alias:

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
  --output-dir output/project-hero
```

Official GPT Image 2.5 example:

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --model gpt-image-2.5-flare \
  --model-family gpt-image-2.5 \
  --size 2048x1152 \
  --quality xhigh \
  --background transparent \
  --output-format png \
  --dry-run --json
```

Sequential mode is more portable than relying on relay support for `n > 1`.

## Edit with references or a mask

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

Masked edit:

```bash
python scripts/edit_image.py \
  --image source.png \
  --mask mask.png \
  --prompt-file edit-prompt.txt \
  --model-family gpt-image-2
```

Source/reference images may be PNG, JPEG, or WebP and must be smaller than 50 MB. For a masked edit, the mask and first source image must use the same format and dimensions, the mask must contain an alpha channel with a transparent edit region, and the mask must also be smaller than 50 MB. PNG or WebP are practical choices because JPEG cannot carry alpha. A request accepts at most 16 input images.

## Outputs

Each run directory preserves:

```text
prompt.txt
prompt_review.json
request.json
response_summary.json
metadata.json
image_01.png
...
```

Credentials are never written to these files. Base64 payloads are omitted from summaries, and URL query strings/fragments are stripped because signed URLs may contain secrets.

## Install as an Agent Skill

Standard user-level location:

```bash
python scripts/install_skill.py --target agents --scope user
```

Claude Code user-level location:

```bash
python scripts/install_skill.py --target claude --scope user
```

Project-local location:

```bash
python scripts/install_skill.py \
  --target agents \
  --scope project \
  --project-dir /path/to/project
```

The installed directory is always named `image2-api`, matching the `name` in `SKILL.md`.

## Run as an MCP server

Requires `mcp>=2` (`pip install "mcp>=2"`). Register as a stdio server (path per your install location):

```json
"image2-api": {
  "type": "stdio",
  "command": "python",
  "args": ["<abs-path-to-skill>/mcp_server.py"]
}
```

Tools: `generate_image` · `edit_image` (references/mask via `image_paths`/`mask_path`) · `check_prompt` (offline, free) · `diagnose_api` (read-only, keys never echoed).

Design notes: thin subprocess wrapper over `scripts/*.py --json` (upgrades to the scripts flow through automatically); credentials stay in `.env` loaded by the scripts themselves; prompts go through a temp file to avoid Windows command-line length limits; size rules and input existence are validated locally before any API call; `readOnlyHint` annotations mark the two read-only tools. Default output root: `~/.agents/image2-api-output/<timestamp>/`. The CLI workflow below and the MCP tools are equivalent paths.

## Validate and test

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python -m compileall scripts tests
```

When the reference validator is installed, also run:

```bash
skills-ref validate .
```

Use `evals/trigger-cases.json` to test skill-selection quality in the target Agent runtime. The local validator checks the fixtures but does not emulate a proprietary router.

## Documentation map

- `references/agent-routing.md` — positive and negative activation rules
- `references/gpt-image-prompt-guide.md` — GPT Image 2.5/2 prompt design and Flare/Sunburst selection
- `references/prompt-recipes.md` — profile-specific patterns
- `references/prompt-brief-schema.md` — brief authoring guide
- `references/api-compatibility.md` — endpoints, model family, limits, relay differences
- `references/integration.md` — installation and Agent execution loop
- `references/troubleshooting.md` — failure diagnosis
- `references/agent-skills-compliance.md` — package-format notes
- `references/sources.md` — official sources and interpretation notes

## Known boundaries

- No live third-party relay is validated until a real key, base URL, and model alias are supplied.
- A relay may accept the OpenAI request shape while ignoring options or omitting edit/mask support.
- The client handles synchronous image responses; asynchronous provider-job polling is not implemented.
- Prompt linting and file validation cannot judge anatomy, semantics, typography accuracy, composition, or identity preservation. Inspect actual outputs with vision.
