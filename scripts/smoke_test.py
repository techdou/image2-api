#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

from PIL import Image

from image2lib.client import ImageAPIClient, entry_to_bytes, extract_image_entries
from image2lib.config import APIConfig
from image2lib.validation import validate_image_bytes, validate_input_image


def make_png() -> bytes:
    image = Image.new("RGB", (512, 512), (232, 228, 220))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


PNG_BYTES = make_png()
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


def make_gif() -> bytes:
    first = Image.new("RGB", (32, 32), "brown")
    second = Image.new("RGB", (32, 32), "orange")
    buffer = BytesIO()
    first.save(buffer, format="GIF", save_all=True, append_images=[second], duration=160, loop=0)
    return buffer.getvalue()


GIF_BYTES = make_gif()
GIF_B64 = base64.b64encode(GIF_BYTES).decode("ascii")
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="8"/></svg>'
SVG_B64 = base64.b64encode(SVG_BYTES).decode("ascii")


class Handler(BaseHTTPRequestHandler):
    server_version = "Image2Mock/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", "mock-request-123")
        self.end_headers()
        self.wfile.write(body)

    def _animated_response(self, fields: dict) -> None:
        expected = {
            "model": "gpt-image-2.6-flare",
            "size": "auto",
            "frame_count": "2",
            "frame_duration_ms": "160",
        }
        if any(str(fields.get(name)) != value for name, value in expected.items()):
            self._json({"error": {"message": "incorrect GIF request fields"}}, status=400)
            return
        data = [{"b64_json": GIF_B64}]
        if str(fields.get("n")) == "2":
            data.append({"b64_json": PNG_B64})
        self._json({"data": data})

    def do_GET(self) -> None:
        if self.path == "/files/mock.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG_BYTES)))
            self.end_headers()
            self.wfile.write(PNG_BYTES)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if self.path == "/v1/images/generations":
            payload = json.loads(raw or b"{}")
            if payload.get("output_format") == "gif":
                self._animated_response(payload)
            elif payload.get("output_format") == "svg":
                if payload.get("n") != 1 or payload.get("model") != "gpt-image-2.6-sunburst":
                    self._json({"error": {"message": "incorrect SVG request fields"}}, status=400)
                    return
                self._json({"data": [{"b64_json": SVG_B64}]})
            elif "url response" in payload.get("prompt", "").lower():
                host, port = self.server.server_address
                self._json({"data": [{"url": f"http://{host}:{port}/files/mock.png"}]})
            else:
                self._json({"data": [{"b64_json": PNG_B64}], "usage": {"total_tokens": 1}})
            return
        if self.path == "/v1/images/edits":
            if b"multipart/form-data" not in self.headers.get("Content-Type", "").encode():
                self._json({"error": {"message": "multipart required"}}, status=400)
                return
            content_type = self.headers["Content-Type"]
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\n\r\n".encode() + raw
            )
            fields = {
                part.get_param("name", header="Content-Disposition"): part.get_content()
                for part in message.iter_parts()
                if part.get_filename() is None
            }
            if fields.get("output_format") == "gif":
                self._animated_response(fields)
            else:
                self._json({"data": [{"b64_json": PNG_B64}]})
            return
        self._json({"error": {"message": "not found"}}, status=404)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    config = APIConfig(
        api_key="test-token",
        base_url=f"http://{host}:{port}/v1",
        model="gpt-image-2",
        timeout=10,
        max_retries=0,
        verify_ssl=True,
    )
    client = ImageAPIClient(config)
    try:
        result = client.generate({"model": config.model, "prompt": "base64 response", "n": 1})
        data = entry_to_bytes(client, extract_image_entries(result.payload)[0])
        validate_image_bytes(data, "base64.png")

        result = client.generate({"model": config.model, "prompt": "URL response", "n": 1})
        data = entry_to_bytes(client, extract_image_entries(result.payload)[0])
        validate_image_bytes(data, "url.png")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            source.write_bytes(PNG_BYTES)
            validate_input_image(source)
            result = client.edit(
                {"model": config.model, "prompt": "Preserve the object and change the background.", "n": 1},
                [source],
            )
            data = entry_to_bytes(client, extract_image_entries(result.payload)[0])
            validate_image_bytes(data, "edit.png")

            root = Path(__file__).resolve().parents[1]
            env = os.environ.copy()
            env.update(
                {
                    "IMAGE_API_KEY": "test-token",
                    "IMAGE_API_BASE_URL": config.base_url,
                    "IMAGE_API_MODEL": config.model,
                    "IMAGE_API_MAX_RETRIES": "0",
                    "IMAGE_API_CLEAN_INTERMEDIATES": "0",
                }
            )
            gen_dir = tmp_path / "cli-generate"
            gen = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts/generate_image.py"),
                    "--prompt",
                    "A mock CLI image",
                    "--size",
                    "1024x1024",
                    "--output-dir",
                    str(gen_dir),
                    "--json",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            if gen.returncode != 0:
                raise RuntimeError(f"Generate CLI failed: {gen.stderr or gen.stdout}")
            gen_payload = json.loads(gen.stdout)
            if not gen_payload.get("images") or not Path(gen_payload["images"][0]).is_file():
                raise RuntimeError("Generate CLI did not create an image file.")

            edit_dir = tmp_path / "cli-edit"
            edit = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts/edit_image.py"),
                    "--image",
                    str(source),
                    "--prompt",
                    "Preserve the sphere and change the background.",
                    "--size",
                    "1024x1024",
                    "--output-dir",
                    str(edit_dir),
                    "--json",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            if edit.returncode != 0:
                raise RuntimeError(f"Edit CLI failed: {edit.stderr or edit.stdout}")
            edit_payload = json.loads(edit.stdout)
            if not edit_payload.get("images") or not Path(edit_payload["images"][0]).is_file():
                raise RuntimeError("Edit CLI did not create an image file.")

            for operation, inputs in (("generate", []), ("edit", ["--image", str(source)])):
                run_dir = tmp_path / f"gif-{operation}"
                result = subprocess.run(
                    [
                        sys.executable, str(root / f"scripts/{operation}_image.py"),
                        *inputs, "--prompt", "The mascot waves and returns to its starting pose.",
                        "--model", "gpt-image-2.6-flare", "--output-format", "gif",
                        "--frame-count", "2", "--frame-duration-ms", "160",
                        "--output-dir", str(run_dir), "--json",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                gif_path = Path(json.loads(result.stdout)["images"][0])
                metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
                if gif_path.suffix != ".gif" or gif_path.read_bytes() != GIF_BYTES:
                    raise RuntimeError(f"{operation} did not preserve the GIF output.")
                if metadata["images"][0]["frame_count"] != 2:
                    raise RuntimeError(f"{operation} did not report the decoded frame count.")

                partial_dir = tmp_path / f"partial-{operation}"
                partial = subprocess.run(
                    [
                        sys.executable, str(root / f"scripts/{operation}_image.py"),
                        *inputs, "--prompt", "Make the mascot wave and loop.",
                        "--model", "gpt-image-2.6-flare", "--output-format", "gif",
                        "--frame-count", "2", "--frame-duration-ms", "160",
                        "--count", "2", "--batch-mode", "single",
                        "--output-dir", str(partial_dir), "--json",
                    ],
                    cwd=root,
                    env={**env, "IMAGE_API_CLEAN_INTERMEDIATES": "1"},
                    capture_output=True,
                    text=True,
                )
                payload = json.loads(partial.stdout)
                meta = json.loads((partial_dir / "metadata.json").read_text(encoding="utf-8"))
                if partial.returncode != 1 or payload["ok"] or not payload["partial"]:
                    raise RuntimeError(f"{operation} did not report a partial failure: {payload}")
                if len(payload["images"]) != 1 or meta["image_count"] != 1 or not meta["partial"]:
                    raise RuntimeError(f"{operation} did not report the successfully saved GIF.")
                if Path(payload["images"][0]).read_bytes() != GIF_BYTES:
                    raise RuntimeError(f"{operation} did not preserve the first GIF.")
                if not (partial_dir / "response_summary.json").is_file():
                    raise RuntimeError(f"{operation} did not retain diagnostics for the partial failure.")

            svg_dir = tmp_path / "svg"
            svg = subprocess.run(
                [
                    sys.executable, str(root / "scripts/generate_image.py"),
                    "--prompt", "Draw a coffee-bean symbol with editable shapes.",
                    "--model", "gpt-image-2.6-sunburst", "--output-format", "svg",
                    "--output-dir", str(svg_dir), "--json",
                ],
                cwd=root,
                env={**env, "IMAGE_API_CLEAN_INTERMEDIATES": "1"},
                capture_output=True,
                text=True,
                check=True,
            )
            svg_path = Path(json.loads(svg.stdout)["images"][0])
            if svg_path.suffix != ".svg" or svg_path.read_bytes() != SVG_BYTES:
                raise RuntimeError("Generate CLI did not preserve the SVG through cleanup.")

        print(
            "Smoke test passed: base64 and URL responses, multipart edit, validation, "
            "still and GIF generate/edit CLIs, partial GIF batches, and native SVG export."
        )
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
