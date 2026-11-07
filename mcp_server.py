"""image2-api MCP server (stdio)

把 image2-api skill 的核心脚本封装成 MCP tools，供 ZCode 等 MCP 客户端调用。
设计原则：
- 薄封装：subprocess 调 scripts/*.py，不复制/重写业务逻辑，脚本升级即生效；
- 凭证隔离：.env 由脚本自身 dotenv 加载，本 server 不读不传 key；
- 结构化返回：脚本 --json 输出直接解析回传，路径/告警/warnings 原样可见；
- 本地 fail-fast：size 像素规则、输入文件存在性在调用前校验，省一次 API 往返；
- 长 prompt 走临时文件（--prompt-file），避开 Windows 命令行长度限制。

依赖 mcp>=1.29,<3（支持 MCP Python SDK 1.x 和 2.x）。客户端注册示例（stdio，路径按实际安装位置替换）：
  command: python
  args: ["<abs-path-to-skill>/mcp_server.py"]
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp.types import ToolAnnotations

try:
    from mcp.server.mcpserver import MCPServer as Server
except ModuleNotFoundError as exc:
    if exc.name != "mcp.server.mcpserver":
        raise
    from mcp.server.fastmcp import FastMCP as Server

    RO = ToolAnnotations(readOnlyHint=True)
    RW = ToolAnnotations(readOnlyHint=False)
else:
    RO = ToolAnnotations(read_only_hint=True)
    RW = ToolAnnotations(read_only_hint=False)

SKILL_DIR = Path(__file__).resolve().parent
SCRIPTS = SKILL_DIR / "scripts"
DEFAULT_OUTPUT_ROOT = Path.home() / ".agents" / "image2-api-output"

mcp = Server(
    "image2-api",
    instructions=(
        "OpenAI-compatible image generation/editing channel (GPT Image 2.6, multi-provider "
        "fallback). generate_image for text-to-image, edit_image for editing/composite/"
        "reference-guided work (declare invariants first in the prompt), check_prompt "
        "for free offline prompt review, diagnose_api for connectivity issues. "
        "For native GIF or SVG output, explicitly select the format and a GPT Image 2.6 model."
    ),
)


def _fail(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _run(script: str, args: list[str], prompt: str | None = None) -> dict:
    """运行 skill 脚本并返回 {ok, result|error, warnings?}。prompt 走临时文件。"""
    prompt_file = None
    if prompt is not None:
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", encoding="utf-8", delete=False)
        f.write(prompt)
        f.close()
        prompt_file = f.name
        args = ["--prompt-file", prompt_file, *args]
    cmd = [sys.executable, str(SCRIPTS / script), *args, "--json"]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(SKILL_DIR),  # 脚本按 skill 根目录解析 .env 与相对路径
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{script} timed out after 600s"}
    finally:
        if prompt_file:
            Path(prompt_file).unlink(missing_ok=True)
    out = r.stdout.strip()
    data = None
    if out.startswith("{"):
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            pass
    warnings = (r.stderr or "").strip()[:1500] or None
    if r.returncode == 0:
        resp = {"ok": True, "result": data if data is not None else out}
        if warnings:
            resp["warnings"] = warnings
        return resp
    error = data.get("error") if isinstance(data, dict) else None
    return {"ok": False, "error": (error or r.stderr or out or "unknown error")[:2000],
            "result": data}


def _outdir(sub: str | None) -> str:
    if sub:
        d = Path(sub).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return str(d.resolve())
    DEFAULT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix=time.strftime("%Y%m%d_%H%M%S_"), dir=DEFAULT_OUTPUT_ROOT)


def _request_options(
    model: str, model_family: str, frame_count: int | None, frame_duration_ms: int | None, dry_run: bool
) -> list[str]:
    options = {
        "model": model,
        "model-family": model_family,
        "frame-count": frame_count,
        "frame-duration-ms": frame_duration_ms,
    }
    args = []
    for flag, value in options.items():
        if value is not None and value != "":
            args.extend((f"--{flag}", str(value)))
    if dry_run:
        args.append("--dry-run")
    return args


@mcp.tool(annotations=RW)
def generate_image(
    prompt: str,
    size: str = "",
    quality: str = "auto",
    count: int = 1,
    background: str = "auto",
    output_format: str = "png",
    prompt_profile: str = "auto",
    output_dir: str = "",
    model: str = "",
    model_family: str = "",
    frame_count: int | None = None,
    frame_duration_ms: int | None = None,
    dry_run: bool = False,
) -> dict:
    """AI 文生图（GPT Image 2.6 / 2.5 / 2，多 provider 自动 fallback）。

    prompt: 图像描述（英文效果最佳；复杂需求按 brief 结构写：主体/场景/风格/构图/画内文字）。
    size: auto 或宽x高，如 1536x1024。静态位图默认 2K 方图，GIF 和 SVG 默认 auto。
    quality: low|medium|high|xhigh|max|auto；探索期 low/medium，成品再调高。
    count: 生成张数 1-10。
    background: auto|opaque|transparent（transparent 需 png/webp）。
    output_format: png|jpeg|webp|gif|svg。默认 png。显式选择 svg 时使用 GPT Image 2.6，count 必须为 1。
    model/model_family: 可选模型名与别名能力系列，默认使用已配置的 provider。
    frame_count/frame_duration_ms: GIF 帧数与单帧毫秒数。
    dry_run: 仅校验请求，跳过网络调用。
    prompt_profile: 任务画像（photorealistic/illustration/logo/ad/infographic/...），auto 自动判断。
    output_dir: 输出目录（绝对或相对家目录），默认 ~/.agents/image2-api-output/<时间戳_唯一后缀>/。

    返回 {ok, result: {images: [路径...], ...}, warnings?}；images 为生成文件的绝对路径。
    """
    if not prompt.strip():
        return _fail("prompt is empty")
    if count < 1 or count > 10:
        return _fail(f"count must be 1-10, got {count}")
    args = _request_options(model, model_family, frame_count, frame_duration_ms, dry_run)
    if size:
        args += ["--size", size]
    args += ["--quality", quality, "--count", str(count),
             "--background", background, "--output-format", output_format,
             "--prompt-profile", prompt_profile,
             "--output-dir", _outdir(output_dir)]
    return _run("generate_image.py", args, prompt=prompt)


@mcp.tool(annotations=RW)
def edit_image(
    prompt: str,
    image_paths: list[str],
    mask_path: str = "",
    size: str = "",
    quality: str = "high",
    output_format: str = "png",
    prompt_profile: str = "edit",
    output_dir: str = "",
    model: str = "",
    model_family: str = "",
    frame_count: int | None = None,
    frame_duration_ms: int | None = None,
    dry_run: bool = False,
) -> dict:
    """AI 图片编辑/合成/参考图生成。多图按顺序传：图1为主画布，图2+为参考（身份/风格/布局）。

    prompt: 编辑指令。先声明不变量（如"保留人脸、姿态与构图，只换背景为..."），再写改动。
    image_paths: 输入图片绝对路径列表（1-N 张）。
    mask_path: 可选蒙版（与第一张图同尺寸同格式、含 alpha 透明编辑区，png/webp）。
    size: auto 或宽x高，留空使用脚本默认。
    quality: 编辑类默认 high 保主体还原。
    output_format: png|jpeg|webp|gif。GIF 使用 GPT Image 2.6，编辑时提供静态参考图。
    model/model_family: 可选模型名与别名能力系列，默认使用已配置的 provider。
    frame_count/frame_duration_ms: GIF 帧数与单帧毫秒数。
    dry_run: 仅校验请求，跳过网络调用。
    prompt_profile: 默认 edit；翻译/合成可用 translation/composite。
    output_dir: 同 generate_image。

    返回 {ok, result: {images: [路径...], ...}, warnings?}。
    """
    if not image_paths:
        return _fail("image_paths is empty; edit needs at least one input image")
    missing = [p for p in image_paths if not Path(p).is_file()]
    if missing:
        return _fail(f"input image(s) not found: {missing}")
    if mask_path and not Path(mask_path).is_file():
        return _fail(f"mask not found: {mask_path}")
    args = _request_options(model, model_family, frame_count, frame_duration_ms, dry_run)
    for p in image_paths:
        args += ["--image", p]
    if mask_path:
        args += ["--mask", mask_path]
    args += ["--quality", quality, "--output-format", output_format,
             "--prompt-profile", prompt_profile,
             "--output-dir", _outdir(output_dir)]
    if size:
        args += ["--size", size]
    return _run("edit_image.py", args, prompt=prompt)


@mcp.tool(annotations=RO)
def check_prompt(prompt: str, operation: str = "generate", profile: str = "general",
                 model_family: str = "gpt-image-2.6", quality: str = "high") -> dict:
    """Prompt 体检（离线只读，不调 API 不花钱）：检查结构完整性、画内文字声明、尺寸/质量匹配等，返回改进建议。

    operation: generate|edit；profile: 任务画像（general/illustration/logo/ad/...）。
    """
    return _run("prompt_doctor.py", [
        "--operation", operation, "--profile", profile,
        "--model-family", model_family, "--quality", quality], prompt=prompt)


@mcp.tool(annotations=RO)
def diagnose_api() -> dict:
    """诊断 API 配置连通性（只读）：检查 .env 各 provider 凭证完整性并探测端点（key 不回显）。生图报错时先跑这个。"""
    return _run("doctor.py", [])


if __name__ == "__main__":
    mcp.run()
