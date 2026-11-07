# Agent routing

## Establish the API scope

Treat explicit invocation, a request to use the OpenAI-compatible Images API, an exact GPT Image API model in an execution request, a named image relay, or continuation of a previously selected image API workflow as sufficient. Use the most recent user preference if they change channels. An API or MCP tool merely being available does not select it.

An output format, reference image, mask, or desire for reproducibility can affect how a request is run. Those details alone do not select this provider. Use the host's ordinary image workflow for general illustration or editing. Use a suitable local workflow for converting existing assets, assembling a GIF from supplied frames, drawing a deterministic diagram, or exporting an existing SVG.

| Request | Selection and action |
|---|---|
| “用我的中转生成一张头图” | Load this skill. Generate a PNG with the configured relay model. |
| “同上，再出一张横版” after an image API request | Keep that provider and generate a PNG with the requested size or aspect ratio. |
| “把这张产品图做成 GIF，用刚才的 API” | Edit with a local still reference. Set GIF and use a provider that supports it. |
| “用 image2-api 生成可编辑的 Logo SVG” | Generate with SVG output, count 1, and a supported 2.6 model. |
| “用 image2-api，把这张已有 Logo 原样输出 SVG” | Explain that native SVG generation does not take the source as an edit input. Ask which requirement can change only if needed to proceed. |
| “先帮我看看这段发给生图 API 的 prompt，别调用” | Review the prompt offline. |
| “看看我的生图中转配置有没有问题” | Inspect local configuration. Run a live probe only if requested. |
| “把现成 PNG 转 SVG” or “画一个准确的 Mermaid 架构图” | Use a conversion or diagram workflow. |

## Select the callable entry point

- **Generate or edit.** The MCP generation tool accepts `count` and `background`. Use the edit CLI if an edit needs either option. Pass actual local paths through `image_paths` and `mask_path` when supported. If the attachment is not accessible as a file, obtain a local copy before calling the edit tool.
- **Review or compile.** Use `check_prompt` for a prompt review. Use `scripts/prompt_doctor.py` if the review needs `--strict`, `--image-count`, `--mask`, `--size`, or `--background`. Use `scripts/build_prompt.py` for a structured brief.
- **Validate or diagnose.** Use `dry_run=true` to inspect a specific request. `diagnose_api` inspects local configuration and does not test network connectivity. The CLI `scripts/doctor.py --probe` generates a live low-quality PNG and can incur charges.
- **Read the result.** MCP returns the CLI result under `result`. Read `result.images` and `result.run_dir` for successful outputs or partial results. Read `result.dry_run` before claiming an image exists. When `ok=false`, preserve any partial results and check the error before deciding whether another live call is appropriate.
