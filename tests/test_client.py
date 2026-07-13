import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from image2lib.client import APIResult, extract_image_entries
from image2lib.utils import merge_extra_params, redact
from image2lib.validation import (
    MAX_MASK_BYTES,
    validate_generation_options,
    validate_image_bytes,
    validate_input_image,
    validate_input_images,
    validate_mask_compatibility,
)


class ClientTests(unittest.TestCase):
    def test_extract_base64(self):
        entries = extract_image_entries({"data": [{"b64_json": "abc"}]})
        self.assertEqual(entries[0]["b64_json"], "abc")

    def test_extract_url_variant(self):
        entries = extract_image_entries({"images": [{"image_url": "https://example.com/a.png"}]})
        self.assertEqual(entries[0]["url"], "https://example.com/a.png")

    def test_validate_image(self):
        image = Image.new("RGB", (128, 128), (255, 255, 255))
        buf = BytesIO()
        image.save(buf, format="PNG")
        info = validate_image_bytes(buf.getvalue(), "test.png")
        self.assertEqual((info.width, info.height), (128, 128))

    def test_valid_mask_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            mask = root / "mask.png"
            Image.new("RGBA", (128, 128), (255, 255, 255, 255)).save(source)
            mask_image = Image.new("RGBA", (128, 128), (0, 0, 0, 255))
            for x in range(32, 96):
                for y in range(32, 96):
                    mask_image.putpixel((x, y), (0, 0, 0, 0))
            mask_image.save(mask)
            validate_input_image(mask, is_mask=True)
            validate_mask_compatibility(source, mask)

    def test_jpeg_source_with_png_mask_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            mask = root / "mask.png"
            Image.new("RGB", (128, 128), (255, 255, 255)).save(source, format="JPEG")
            Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(mask)
            validate_input_image(mask, is_mask=True)
            validate_mask_compatibility(source, mask)

    def test_fully_opaque_mask_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "mask.png"
            Image.new("RGBA", (128, 128), (0, 0, 0, 255)).save(mask)
            with self.assertRaises(ValueError):
                validate_input_image(mask, is_mask=True)

    def test_mask_over_four_megabytes_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "mask.png"
            mask.write_bytes(b"x" * MAX_MASK_BYTES)
            with self.assertRaisesRegex(ValueError, "smaller than 4 MB"):
                validate_input_image(mask, is_mask=True)

    def test_mask_dimension_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            mask = root / "mask.png"
            Image.new("RGB", (128, 128), (255, 255, 255)).save(source, format="JPEG")
            Image.new("RGBA", (64, 128), (0, 0, 0, 0)).save(mask)
            with self.assertRaisesRegex(ValueError, "must match"):
                validate_mask_compatibility(source, mask)

    def test_more_than_sixteen_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, "at most 16"):
            validate_input_images([f"missing-{index}.png" for index in range(17)])

    def test_image2_transparent_rejected(self):
        with self.assertRaises(ValueError):
            validate_generation_options(
                model="gpt-image-2",
                model_family="gpt-image-2",
                size="1024x1024",
                quality="high",
                background="transparent",
                output_format="png",
                output_compression=None,
                count=1,
            )

    def test_alias_uses_image2_constraints_when_family_is_set(self):
        with self.assertRaisesRegex(ValueError, "transparent"):
            validate_generation_options(
                model="image-2",
                model_family="gpt-image-2",
                size="1024x1024",
                quality="high",
                background="transparent",
                output_format="png",
                output_compression=None,
                count=1,
            )

    def test_image2_arbitrary_size_constraints(self):
        warnings = validate_generation_options(
            model="gpt-image-2",
            model_family="gpt-image-2",
            size="2048x1152",
            quality="high",
            background="auto",
            output_format="png",
            output_compression=None,
            count=1,
        )
        self.assertEqual(warnings, [])

    def test_extra_param_cannot_override_standard_field(self):
        with self.assertRaisesRegex(ValueError, "cannot override"):
            merge_extra_params({"model": "image-2"}, ["model=other"], reserved={"model"})

    def test_signed_url_is_sanitized_in_summary(self):
        summary = APIResult(
            payload={"data": [{"url": "https://cdn.example.com/a.png?sig=secret#fragment"}]},
            request_id="r1",
            status_code=200,
            attempts=1,
        ).safe_summary()
        self.assertEqual(summary["payload"]["data"][0]["url"], "https://cdn.example.com/a.png")

    def test_redact_secret_header_value(self):
        self.assertEqual(redact({"token": "abc"})["token"], "***REDACTED***")


if __name__ == "__main__":
    unittest.main()
