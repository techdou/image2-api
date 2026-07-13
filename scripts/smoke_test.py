#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
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
            if "url response" in payload.get("prompt", "").lower():
                host, port = self.server.server_address
                self._json({"data": [{"url": f"http://{host}:{port}/files/mock.png"}]})
            else:
                self._json({"data": [{"b64_json": PNG_B64}], "usage": {"total_tokens": 1}})
            return
        if self.path == "/v1/images/edits":
            if b"multipart/form-data" not in self.headers.get("Content-Type", "").encode():
                self._json({"error": {"message": "multipart required"}}, status=400)
                return
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

        print(
            "Smoke test passed: base64 and URL responses, multipart edit, validation, "
            "and end-to-end generate/edit CLIs."
        )
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
