# image2-api

面向 Agent 的生图 API Skill。通过 OpenAI 兼容的 Images API 或用户配置的中转生成、编辑图片，支持 CLI 和可选的 stdio MCP 服务。普通生图使用已配置的模型，默认输出 PNG。明确要求时，可用 GPT Image 2.6 生成原生 GIF 或可编辑 SVG。

[English quick start](#english-quick-start) · [Skill 入口](SKILL.md) · [变更记录](CHANGELOG.md)

## 安装和配置

需要 Python 3.10+。提示词审查、请求干跑和配置检查均在本地执行。真实调用需要可访问的 API 及对应凭证。

```bash
git clone https://github.com/techdou/image2-api.git
cd image2-api
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 可用 `Copy-Item .env.example .env`。在本机编辑 `.env`，填写 API 地址、密钥和服务商实际提供的模型。使用第三方模型别名时，将 `IMAGE_API_MODEL_FAMILY` 设为对应的模型系列。多服务商配置见 [API 兼容性说明](references/api-compatibility.md#multi-provider-fallback)。

```bash
python scripts/doctor.py --json
```

该命令只检查本地配置。需要真实探测时，`python scripts/doctor.py --probe` 会发出一次低画质生图请求，可能产生费用。

## CLI 用法

从仓库根目录执行。先检查离线请求计划，确认模型、输出格式和参数后，再移除 `--dry-run` 发送请求。

### 编译和审查提示词

```bash
python scripts/build_prompt.py --brief examples/briefs/logo-mark.json --output output/prompt.txt
python scripts/prompt_doctor.py --prompt-file output/prompt.txt --profile logo
```

使用 `--prompt-file output/prompt.txt` 将已审查的提示词传给生成脚本。结构化字段见 [提示词 Schema](references/prompt-brief-schema.md)。

### 生成默认 PNG

```bash
python scripts/generate_image.py \
  --prompt "Warm ivory background with a simple coffee-bean illustration." \
  --dry-run --json
```

### 编辑图片

```bash
python scripts/edit_image.py --image input.png \
  --prompt "Keep the subject and composition. Change the background to warm ivory." \
  --dry-run --json
```

按顺序重复 `--image` 可传多张图，第一张是主图。可用 `--mask` 指定编辑区域。透明输出使用 PNG 或 WebP 并设置 `--background transparent`。

### 生成原生 GIF

```bash
python scripts/generate_image.py --model gpt-image-2.6-flare \
  --output-format gif --frame-count 9 --frame-duration-ms 200 \
  --prompt "A coffee-bean mascot waves once and returns to its starting pose. Fixed camera, seamless loop." \
  --dry-run --json
```

从静态参考图生成 GIF 时，使用 `edit_image.py --image input.png` 和同样的 GIF 参数。GIF 编辑不使用蒙版。尺寸与帧参数见 [GIF 说明](references/api-compatibility.md#animated-gif-output)。

### 导出原生 SVG

```bash
python scripts/generate_image.py --model gpt-image-2.6-sunburst \
  --output-format svg \
  --prompt "Draw a coffee-bean logo with editable paths and two flat colors." \
  --dry-run --json
```

原生 SVG 每次生成一份。编辑接口接收参考图，但不提供 SVG 输出。所用项目或中转需支持对应模型和输出格式。[SVG 说明](references/api-compatibility.md#native-svg-output)

## 安装为 Agent Skill

```bash
python scripts/install_skill.py --target codex --scope user
```

Codex 用户级技能位于 `~/.agents/skills/image2-api/`。使用安装副本时，在对应目录配置本地 `.env`，或通过宿主传入环境变量。安装到指定项目可用 `--scope project --project-dir /path/to/project`。其他宿主的安装路径和调用边界见 [Agent 集成](references/integration.md) 与 [路由说明](references/agent-routing.md)。

## 接入 MCP

```bash
python -m pip install "mcp>=1.29,<3"
```

在支持 stdio 的客户端中注册服务。将以下内容放入客户端的 MCP 服务配置，并替换脚本的绝对路径。若在虚拟环境中安装依赖，`command` 应指向该环境的 Python。

```json
{
  "image2-api": {
    "type": "stdio",
    "command": "python",
    "args": ["/absolute/path/to/image2-api/mcp_server.py"]
  }
}
```

| Tool | 用途 |
| --- | --- |
| `generate_image` | 从文字生成 PNG、JPEG、WebP、GIF 或 SVG |
| `edit_image` | 编辑图片、使用参考图或生成参考图驱动的 GIF |
| `check_prompt` | 离线审查已有提示词 |
| `diagnose_api` | 离线检查本地 provider 配置 |

生成和编辑支持 `dry_run=true`。请求、响应摘要和产物记录在运行目录中。CLI 默认写入 `output/`，MCP 默认写入 `~/.agents/image2-api-output/`。请求计划包含提示词，引用路径也可能出现在本地记录中。

## 目录与提交边界

| 路径 | 内容 |
| --- | --- |
| `SKILL.md`、`agents/` | Skill 入口与公开的 Agent 元数据 |
| `mcp_server.py`、`scripts/` | MCP 服务、CLI 和共享实现 |
| `assets/`、`examples/` | 结构化提示词 schema 和公开示例 |
| `references/` | Skill 运行所需的公开参考 |
| `tests/`、`evals/` | 离线测试与 Agent 路由评测 |
| `.env.example` | 仅含占位值的公开配置模板 |

真实密钥、私有配置、内部文档和测试记录留在本地。内部资料统一放入被忽略的 `internal/`，开发工具配置目录与运行产物也由 [.gitignore](.gitignore) 排除。新增公开 Markdown 文件时，先确认发布范围，再按路径加入白名单。提交前检查 `git diff --cached`，确认暂存区只包含预期发布内容。

## 验证

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
python scripts/smoke_test.py
```

冒烟测试使用本地模拟 API。安装官方 Agent Skills 校验工具后，可执行 `skills-ref validate "$PWD"`。Agent 匹配测试说明见 [评测用例](evals/README.md)。

## English quick start

`image2-api` is an Agent Skill for generating and editing images through a configured OpenAI-compatible Images API. Install `requirements.txt`, copy `.env.example` to `.env`, and set your provider URL, token, and model. Run `python scripts/doctor.py --json` for a local configuration check and use `--dry-run --json` to inspect a request without calling the API. PNG is the default. Native GIF and SVG are opt-in and require compatible GPT Image 2.6 access. See the [API reference](references/api-compatibility.md) and [integration guide](references/integration.md).

## License

[MIT](LICENSE)
