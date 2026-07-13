import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from image2lib.prompting import (
    build_prompt,
    infer_profile_from_prompt,
    lint_prompt,
    resolve_prompt_context,
)


class PromptTests(unittest.TestCase):
    def test_build_prompt_uses_labeled_sections(self):
        prompt = build_prompt(
            {
                "profile": "ip-character",
                "deliverable": "Square IP illustration",
                "subject": "A ceramic deer spirit",
                "composition": "Centered full-body character with safe margins",
                "constraints": ["No text", "No neon"],
            }
        )
        self.assertIn("Create the following asset: Square IP illustration.", prompt)
        self.assertIn("Main subject:\nA ceramic deer spirit.", prompt)
        self.assertIn("Composition and hierarchy:", prompt)
        self.assertIn("- No text.", prompt)
        self.assertIn("- No neon.", prompt)

    def test_edit_prompt_orders_preserve_before_changes(self):
        prompt = build_prompt(
            {
                "operation": "edit",
                "profile": "edit",
                "references": {"Image 1": "Primary canvas", "Image 2": "Style reference"},
                "preserve": ["face and camera angle"],
                "changes": ["replace only the background"],
                "constraints": ["keep everything else unchanged"],
            },
            operation="edit",
        )
        self.assertLess(prompt.index("Preserve exactly:"), prompt.index("Change only:"))
        self.assertIn("Image 1", prompt)
        self.assertIn("Image 2", prompt)

    def test_text_dict_quotes_exact_copy(self):
        prompt = build_prompt(
            {
                "deliverable": "Launch poster",
                "text": {
                    "exact": ["VibeCanvas", "Create. Edit. Review."],
                    "placement": "Right side",
                },
            }
        )
        self.assertIn('"VibeCanvas"', prompt)
        self.assertIn('"Create. Edit. Review."', prompt)
        self.assertIn("exactly and verbatim", prompt)

    def test_empty_brief(self):
        with self.assertRaises(ValueError):
            build_prompt({})

    def test_legacy_suffix_warned(self):
        report = lint_prompt(
            "A deer mascot, masterpiece, best quality, 8K, trending on ArtStation",
            profile="ip-character",
        )
        codes = {issue.code for issue in report.issues}
        self.assertIn("legacy-quality-suffix", codes)
        self.assertEqual(report.status, "warn")

    def test_edit_invariants_and_roles_warned(self):
        report = lint_prompt(
            "Put the product on the table.",
            operation="edit",
            profile="edit",
            image_count=2,
        )
        codes = {issue.code for issue in report.issues}
        self.assertIn("missing-edit-invariants", codes)
        self.assertIn("edit-scope-not-surgical", codes)
        self.assertIn("multi-image-roles-missing", codes)

    def test_transparent_background_is_error_for_image2(self):
        report = lint_prompt(
            "Create a logo on a transparent background.",
            profile="logo",
            model="gpt-image-2",
        )
        self.assertIn("transparent-unsupported", {issue.code for issue in report.issues})
        self.assertEqual(report.status, "fail")

    def test_text_low_quality_warning(self):
        report = lint_prompt(
            'Create a poster with the exact headline "VibeCanvas".',
            profile="ad",
            quality="low",
        )
        self.assertIn("text-low-quality", {issue.code for issue in report.issues})


    def test_edit_profile_resolves_edit_operation(self):
        profile, operation = resolve_prompt_context(
            {"profile": "edit", "preserve": "identity", "changes": "change only background"},
            profile="edit",
        )
        self.assertEqual((profile, operation), ("edit", "edit"))

    def test_logo_scalability_warning(self):
        report = lint_prompt(
            "Create a beautiful logo with a blue circle.",
            profile="logo",
        )
        self.assertIn("logo-scalability-missing", {issue.code for issue in report.issues})

    def test_translation_map_warning(self):
        report = lint_prompt(
            "Translate the text to Japanese. Keep everything else unchanged.",
            operation="edit",
            profile="translation",
            image_count=1,
        )
        self.assertIn("translation-map-missing", {issue.code for issue in report.issues})

    def test_profile_inference_from_prompt(self):
        profile = infer_profile_from_prompt(
            "Create a polished repository hero for a GitHub README and social preview."
        )
        self.assertEqual(profile, "project-hero")

    def test_translation_map_is_compiled(self):
        prompt = build_prompt(
            {
                "operation": "edit",
                "profile": "translation",
                "references": {"Image 1": "Primary poster"},
                "preserve": ["typography, placement, spacing, layout"],
                "translation": {"HELLO": "こんにちは"},
                "changes": ["translate only the mapped text"],
                "constraints": ["keep everything else unchanged"],
            },
            operation="edit",
        )
        self.assertIn("Text replacement map:", prompt)
        self.assertIn("HELLO: こんにちは", prompt)

    def test_uppercase_words_are_not_treated_as_exact_copy(self):
        report = lint_prompt(
            "Create a poster with title TECHDOU at the top.",
            profile="ad",
        )
        self.assertIn("text-not-verbatim", {issue.code for issue in report.issues})

    def test_product_mockup_infers_product_not_ui(self):
        profile = infer_profile_from_prompt(
            "Create a photorealistic product mockup and ecommerce packaging render."
        )
        self.assertEqual(profile, "product")

    def test_alias_family_enforces_transparency(self):
        report = lint_prompt(
            "Create a simple logo on a transparent background with a distinctive silhouette.",
            profile="logo",
            model="image-2",
            model_family="gpt-image-2",
        )
        self.assertIn("transparent-unsupported", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
