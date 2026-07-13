import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from image2lib.version import __version__


class SkillPackageTests(unittest.TestCase):
    def test_frontmatter_has_narrow_activation_boundary(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^name: image2-api$")
        self.assertIn("This skill should be used", text)
        self.assertIn("Do not select", text)
        self.assertIn("OpenAI-compatible", text)
        self.assertIn("ordinary built-in image generation", text)

    def test_version_is_consistent(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r'(?m)^\s+version: "([^"]+)"$', text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), __version__)

    def test_trigger_fixtures_cover_positive_and_negative(self):
        data = json.loads((ROOT / "evals/trigger-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(data["version"], __version__)
        expected = {case["expected"] for case in data["cases"]}
        self.assertTrue({"select", "do-not-select"}.issubset(expected))
        self.assertGreaterEqual(len(data["cases"]), 8)

    def test_skill_is_under_progressive_disclosure_limit(self):
        lines = (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 500)


if __name__ == "__main__":
    unittest.main()
