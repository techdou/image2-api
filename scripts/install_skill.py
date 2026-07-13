#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def target_dir(target: str, scope: str, project_dir: Path) -> Path:
    if scope == "user":
        base = Path.home()
        return base / (".claude/skills" if target == "claude" else ".agents/skills") / "image2-api"
    base = project_dir.resolve()
    return base / (".claude/skills" if target == "claude" else ".agents/skills") / "image2-api"


def main() -> int:
    p = argparse.ArgumentParser(description="Install image2-api into a user or project skill directory.")
    p.add_argument("--target", choices=["agents", "codex", "opencode", "openclaw", "claude"], default="agents")
    p.add_argument("--scope", choices=["user", "project"], default="user")
    p.add_argument("--project-dir", default=".")
    p.add_argument("--link", action="store_true", help="Try a symlink; fall back to copy on failure.")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    source = Path(__file__).resolve().parents[1]
    normalized_target = "claude" if args.target == "claude" else "agents"
    destination = target_dir(normalized_target, args.scope, Path(args.project_dir))
    if destination.exists() or destination.is_symlink():
        if not args.force:
            print(f"Error: destination exists: {destination}. Use --force to replace it.")
            return 1
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if args.link:
        try:
            os.symlink(source, destination, target_is_directory=True)
            print(f"Linked {source} -> {destination}")
            return 0
        except OSError as exc:
            print(f"Symlink unavailable ({exc}); falling back to copy.")

    ignore = shutil.ignore_patterns(".env", ".venv", "venv", "__pycache__", "*.pyc", "outputs")
    shutil.copytree(source, destination, ignore=ignore)
    (destination / "outputs").mkdir(exist_ok=True)
    (destination / "outputs" / ".gitkeep").touch()
    print(f"Installed to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
