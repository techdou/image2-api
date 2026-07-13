import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from image2lib.config import APIConfig, build_endpoint, normalize_base_url, parse_extra_headers, resolve_model_family


class ConfigTests(unittest.TestCase):
    def test_normalize_base_url(self):
        self.assertEqual(normalize_base_url("https://example.com/v1/"), "https://example.com/v1")

    def test_build_generation_endpoint(self):
        self.assertEqual(
            build_endpoint("https://example.com/v1", "generation"),
            "https://example.com/v1/images/generations",
        )

    def test_switch_full_endpoint_kind(self):
        self.assertEqual(
            build_endpoint("https://example.com/v1/images/generations", "edit"),
            "https://example.com/v1/images/edits",
        )

    def test_parse_headers(self):
        self.assertEqual(parse_extra_headers('{"X-Test":123}'), {"X-Test": "123"})

    def test_alias_model_family(self):
        self.assertEqual(resolve_model_family("image-2", "gpt-image-2"), "gpt-image-2")

    def test_unrecognized_auto_alias_is_generic(self):
        self.assertEqual(resolve_model_family("image-2", "auto"), "generic")

    def test_unrecognized_alias_warns(self):
        config = APIConfig(api_key="", model="image-2", model_family="auto")
        warnings = config.validate(require_key=False)
        self.assertTrue(any("IMAGE_API_MODEL_FAMILY" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
