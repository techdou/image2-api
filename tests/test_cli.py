import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_generate_dry_run_without_key_writes_prompt_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("IMAGE_API_KEY", None)
            env.pop("OPENAI_API_KEY", None)
            run_dir = Path(tmp) / "run"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/generate_image.py"),
                    "--prompt",
                    "Create a simple ceramic sphere on a quiet opaque background.",
                    "--size",
                    "1024x1024",
                    "--output-dir",
                    str(run_dir),
                    "--dry-run",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue((run_dir / "request.json").is_file())
            self.assertTrue((run_dir / "prompt_review.json").is_file())

    def test_prompt_doctor_strict_fails_on_warning(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/prompt_doctor.py"),
                "--prompt",
                "A deer mascot, masterpiece, best quality, 8K",
                "--profile",
                "ip-character",
                "--strict",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("strict mode", payload["error"])

    def test_build_prompt_json_output(self):
        brief = ROOT / "examples/briefs/open-source-project-hero.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_prompt.py"),
                "--brief",
                str(brief),
                "--profile",
                "project-hero",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["review"]["profile"], "project-hero")
        self.assertIn("Scene and background:", payload["prompt"])

    def test_alias_family_rejects_transparent_background(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/generate_image.py"),
                "--prompt",
                "Create a logo with a distinctive silhouette.",
                "--model",
                "image-2",
                "--model-family",
                "gpt-image-2",
                "--background",
                "transparent",
                "--dry-run",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertIn("transparent", payload["error"])

    def test_extra_param_cannot_override_prompt(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/generate_image.py"),
                "--prompt",
                "Create a ceramic sphere on an opaque background.",
                "--extra-param",
                "prompt=override",
                "--dry-run",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertIn("cannot override", payload["error"])


if __name__ == "__main__":
    unittest.main()
