#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys

from image2lib.client import ImageAPIClient, ImageAPIError, entry_to_bytes, extract_image_entries
from image2lib.config import APIConfig, MODEL_FAMILIES
from image2lib.validation import validate_image_bytes


def main() -> int:
    p = argparse.ArgumentParser(description="Validate image relay configuration and optionally send a low-quality probe.")
    p.add_argument("--probe", action="store_true", help="Send a real low-quality request; may incur charges.")
    p.add_argument("--model")
    p.add_argument("--model-family", choices=MODEL_FAMILIES)
    p.add_argument("--base-url")
    p.add_argument("--endpoint")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    checks: dict[str, object] = {"dependencies": {}, "config": {}, "probe": None, "warnings": []}
    ok = True
    for name in ["httpx", "PIL", "dotenv"]:
        try:
            module = importlib.import_module(name)
            checks["dependencies"][name] = getattr(module, "__version__", "installed")
        except ImportError:
            checks["dependencies"][name] = "missing"
            ok = False

    try:
        config = APIConfig.from_env(
            base_url=args.base_url,
            model=args.model,
            model_family=args.model_family,
            generations_url=args.endpoint,
        )
        warnings = config.validate(require_key=args.probe)
        checks["config"] = config.safe_dict()
        checks["warnings"] = warnings
        if args.probe:
            payload = {
                "model": config.model,
                "prompt": "A simple centered matte gray ceramic sphere on a plain white background, no text.",
                "n": 1,
                "size": "1024x1024",
                "quality": "low",
                "background": "auto",
                "output_format": "png",
                "moderation": "auto",
            }
            client = ImageAPIClient(config)
            result = client.generate(payload)
            entries = extract_image_entries(result.payload)
            image_bytes = entry_to_bytes(client, entries[0])
            info = validate_image_bytes(image_bytes, "probe.png")
            checks["probe"] = {
                "ok": True,
                "status_code": result.status_code,
                "request_id": result.request_id,
                "attempts": result.attempts,
                "image": info.to_dict(),
            }
    except (ValueError, OSError, ImageAPIError) as exc:
        ok = False
        checks["error"] = str(exc)

    checks["ok"] = ok
    if args.json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
    else:
        print("image2-api doctor")
        print(f"Status: {'OK' if ok else 'FAILED'}")
        for name, value in checks["dependencies"].items():
            print(f"Dependency {name}: {value}")
        if checks.get("config"):
            for key, value in checks["config"].items():
                print(f"{key}: {value}")
        for warning in checks.get("warnings", []):
            print(f"Warning: {warning}", file=sys.stderr)
        if checks.get("probe"):
            print("Probe: OK")
        if checks.get("error"):
            print(f"Error: {checks['error']}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
