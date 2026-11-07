import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from struct import pack_into
from unittest.mock import patch

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
    validate_svg_bytes,
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

    def test_gif_is_reopened_and_all_valid_frames_are_decoded(self):
        frames = [Image.new("RGB", (32, 32), color) for color in ("red", "blue")]
        buffer = BytesIO()
        frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
        data = buffer.getvalue()
        info = validate_image_bytes(data, "test.gif", require_animated_gif=True)
        self.assertEqual(info.frame_count, 2)
        with self.assertRaisesRegex(ValueError, "truncated"):
            validate_image_bytes(data[:-1], "test.gif", require_animated_gif=True)

    def test_gif_limits_are_enforced_before_pillow_opens_the_payload(self):
        frames = [Image.new("RGB", (16, 16), (index * 12, 0, 0)) for index in range(17)]
        buffer = BytesIO()
        frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
        data = buffer.getvalue()
        oversized = bytearray(data)
        pack_into("<H", oversized, 6, 3841)
        with patch("image2lib.validation.Image.open") as open_image:
            with self.assertRaisesRegex(ValueError, "16 frames"):
                validate_image_bytes(data, "test.gif", require_animated_gif=True)
            with self.assertRaisesRegex(ValueError, "frame dimensions"):
                validate_image_bytes(bytes(oversized), "test.gif", require_animated_gif=True)
            with patch("image2lib.validation.MAX_GIF_BYTES", len(data) - 1):
                with self.assertRaisesRegex(ValueError, "response limit"):
                    validate_image_bytes(data, "test.gif", require_animated_gif=True)
            open_image.assert_not_called()

    def test_svg_preserves_vector_viewport_and_rejects_active_content(self):
        start = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 24">'
        safe = start + '<style>.shape{fill:url(#gradient)}</style><path d="M 0 0 L 10 10" /></svg>'
        info = validate_svg_bytes(safe.encode(), "test.svg")
        self.assertEqual(info["view_box"], "0 0 48 24")
        self.assertEqual(info["format"], "svg")
        invalid = [
            "<html/>",
            '<!DOCTYPE svg [<!ENTITY sample "text">]>' + start + "</svg>",
            '<?xml-stylesheet href="https://example.com/style.css"?>' + start + "</svg>",
            start + '<script>alert(1)</script></svg>',
            start + '<path onload="alert(1)"/></svg>',
            start + '<use href="https://example.com/file.svg#icon"/></svg>',
            start + '<style>path{fill:url(https://example.com/file.svg)}</style></svg>',
        ]
        for svg in invalid:
            with self.subTest(svg=svg), self.assertRaises(ValueError):
                validate_svg_bytes(svg.encode(), "test.svg")

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

    def test_mask_format_must_match_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            mask = root / "mask.png"
            Image.new("RGB", (128, 128), (255, 255, 255)).save(source, format="JPEG")
            Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(mask)
            validate_input_image(mask, is_mask=True)
            with self.assertRaisesRegex(ValueError, "must match"): 
                validate_mask_compatibility(source, mask)

    def test_webp_mask_pair_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.webp"
            mask = root / "mask.webp"
            Image.new("RGBA", (128, 128), (255, 255, 255, 255)).save(source, format="WEBP")
            Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(mask, format="WEBP", lossless=True)
            validate_input_image(mask, is_mask=True)
            validate_mask_compatibility(source, mask)

    def test_fully_opaque_mask_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "mask.png"
            Image.new("RGBA", (128, 128), (0, 0, 0, 255)).save(mask)
            with self.assertRaises(ValueError):
                validate_input_image(mask, is_mask=True)

    def test_mask_at_fifty_megabytes_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "mask.png"
            with mask.open("wb") as handle:
                handle.truncate(MAX_MASK_BYTES)
            with self.assertRaisesRegex(ValueError, "smaller than 50 MB"):
                validate_input_image(mask, is_mask=True)

    def test_mask_dimension_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            mask = root / "mask.png"
            Image.new("RGBA", (128, 128), (255, 255, 255, 255)).save(source, format="PNG")
            Image.new("RGBA", (64, 128), (0, 0, 0, 0)).save(mask)
            with self.assertRaisesRegex(ValueError, "must match"):
                validate_mask_compatibility(source, mask)

    def test_more_than_sixteen_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, "at most 16"):
            validate_input_images([f"missing-{index}.png" for index in range(17)])

    def test_image2_transparent_png_allowed_with_preview_warning(self):
        warnings = validate_generation_options(
            model="gpt-image-2",
            model_family="gpt-image-2",
            size="1024x1024",
            quality="high",
            background="transparent",
            output_format="png",
            output_compression=None,
            count=1,
        )
        self.assertTrue(any("preview" in warning for warning in warnings))

    def test_transparent_jpeg_rejected(self):
        with self.assertRaisesRegex(ValueError, "png or webp"):
            validate_generation_options(
                model="gpt-image-2.5-flare",
                model_family="auto",
                size="1024x1024",
                quality="high",
                background="transparent",
                output_format="jpeg",
                output_compression=None,
                count=1,
            )

    def test_gpt_image_25_supports_xhigh_and_max(self):
        for quality in ("xhigh", "max"):
            warnings = validate_generation_options(
                model="gpt-image-2.5-sunburst",
                model_family="auto",
                size="2048x1152",
                quality=quality,
                background="transparent",
                output_format="webp",
                output_compression=90,
                count=1,
            )
            self.assertEqual(warnings, [])

    def test_gpt_image_2_rejects_xhigh(self):
        with self.assertRaisesRegex(ValueError, "not supported"):
            validate_generation_options(
                model="gpt-image-2",
                model_family="auto",
                size="1024x1024",
                quality="xhigh",
                background="auto",
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

    def test_image25_4k_size_warns_experimental(self):
        warnings = validate_generation_options(
            model="gpt-image-2.5-flare",
            model_family="auto",
            size="3840x2160",
            quality="high",
            background="auto",
            output_format="png",
            output_compression=None,
            count=1,
        )
        self.assertTrue(any("experimental" in warning for warning in warnings))

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
