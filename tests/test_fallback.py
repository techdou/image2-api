import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from image2lib.client import (
    ImageAPIError,
    ImageAPIClient,
    ProviderChainError,
)
from image2lib.config import APIConfig, ProviderChain, ProviderProfile


def _profile(name: str, url: str) -> ProviderProfile:
    return ProviderProfile(
        name=name,
        api_key=f"key-{name}",
        base_url=url,
        model="gpt-image-2",
        model_family="gpt-image-2",
        timeout=5.0,
        max_retries=0,
    )


def _config_with_chain(*profiles: ProviderProfile) -> APIConfig:
    chain = ProviderChain(profiles=list(profiles), fallback_status={429, 500, 502, 503, 504})
    primary = profiles[0]
    return APIConfig(
        api_key=primary.api_key,
        base_url=primary.base_url,
        model=primary.model,
        model_family=primary.model_family,
        timeout=primary.timeout,
        max_retries=primary.max_retries,
        chain=chain,
    )


def _mock_response(status: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.is_error = status >= 400
    resp.headers = {}
    resp.text = ""
    resp.json.return_value = body or {}
    resp.raise_for_status = MagicMock()
    return resp


class FallbackTests(unittest.TestCase):
    def _patched_client(self, config: APIConfig, side_effects: list):
        """Patch httpx.Client used inside ImageAPIClient. Each entry in
        side_effects is either a callable returning a response, or an
        Exception class/instance — exceptions are raised, not returned.
        """
        client = ImageAPIClient(config)
        effects_iter = iter(side_effects)
        def dispatch(*a, **kw):
            item = next(effects_iter)
            if isinstance(item, BaseException) or (
                isinstance(item, type) and issubclass(item, BaseException)
            ):
                raise item
            return item
        with patch("image2lib.client.httpx.Client") as MockClient:
            mock_http = MagicMock()
            mock_http.request.side_effect = dispatch
            mock_http.__enter__ = MagicMock(return_value=mock_http)
            mock_http.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_http
            yield client

    def test_falls_back_on_503(self):
        config = _config_with_chain(
            _profile("primary", "https://primary.example.com/v1"),
            _profile("backup", "https://backup.example.com/v1"),
        )
        ok = _mock_response(200, {"data": [{"b64_json": "abc"}]})
        bad = _mock_response(503, {"error": {"message": "no accounts"}})
        gen = self._patched_client(config, [bad, ok])
        client = next(gen)
        result = client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.provider_name, "backup")
        try:
            gen.__next__()  # close patch
        except StopIteration:
            pass

    def test_no_fallback_on_400(self):
        config = _config_with_chain(
            _profile("primary", "https://primary.example.com/v1"),
            _profile("backup", "https://backup.example.com/v1"),
        )
        bad = _mock_response(400, {"error": {"message": "bad request"}})
        gen = self._patched_client(config, [bad])
        client = next(gen)
        with self.assertRaises(ImageAPIError) as ctx:
            client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        self.assertEqual(ctx.exception.status_code, 400)
        try:
            gen.__next__()
        except StopIteration:
            pass

    def test_no_fallback_on_401(self):
        config = _config_with_chain(
            _profile("primary", "https://primary.example.com/v1"),
            _profile("backup", "https://backup.example.com/v1"),
        )
        bad = _mock_response(401, {"error": {"message": "unauthorized"}})
        gen = self._patched_client(config, [bad])
        client = next(gen)
        with self.assertRaises(ImageAPIError) as ctx:
            client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        self.assertEqual(ctx.exception.status_code, 401)
        try:
            gen.__next__()
        except StopIteration:
            pass

    def test_all_providers_fail_raises_chain_error(self):
        config = _config_with_chain(
            _profile("primary", "https://primary.example.com/v1"),
            _profile("backup", "https://backup.example.com/v1"),
            _profile("third", "https://third.example.com/v1"),
        )
        bad1 = _mock_response(503, {"error": {"message": "no accounts"}})
        bad2 = _mock_response(500, {"error": {"message": "server error"}})
        bad3 = _mock_response(429, {"error": {"message": "rate limited"}})
        gen = self._patched_client(config, [bad1, bad2, bad3])
        client = next(gen)
        with self.assertRaises(ProviderChainError) as ctx:
            client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        err = ctx.exception
        self.assertEqual(len(err.attempts), 3)
        self.assertEqual(err.attempts[0]["provider"], "primary")
        self.assertEqual(err.attempts[0]["status_code"], 503)
        self.assertEqual(err.attempts[1]["provider"], "backup")
        self.assertEqual(err.attempts[2]["provider"], "third")
        try:
            gen.__next__()
        except StopIteration:
            pass

    def test_fallback_on_network_error(self):
        import httpx

        config = _config_with_chain(
            _profile("primary", "https://primary.example.com/v1"),
            _profile("backup", "https://backup.example.com/v1"),
        )
        ok = _mock_response(200, {"data": [{"b64_json": "abc"}]})
        gen = self._patched_client(config, [httpx.ConnectError("boom"), ok])
        client = next(gen)
        result = client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        self.assertEqual(result.provider_name, "backup")
        try:
            gen.__next__()
        except StopIteration:
            pass

    def test_single_provider_mode_no_chain(self):
        # No chain set -> behaves as before, single provider.
        config = APIConfig(
            api_key="key",
            base_url="https://primary.example.com/v1",
            model="gpt-image-2",
            model_family="gpt-image-2",
            timeout=5.0,
            max_retries=0,
        )
        ok = _mock_response(200, {"data": [{"b64_json": "abc"}]})
        gen = self._patched_client(config, [ok])
        client = next(gen)
        result = client.generate({"model": "gpt-image-2", "prompt": "x", "n": 1})
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.provider_name)
        try:
            gen.__next__()
        except StopIteration:
            pass


class FallbackEnvConfigTests(unittest.TestCase):
    """Smoke tests for ProviderChain.from_env."""

    def test_returns_none_when_not_configured(self):
        with patch.dict("os.environ", {}, clear=False):
            from image2lib import config as cfg_mod
            # Remove the var if it happens to be set in the test env.
            import os
            os.environ.pop("IMAGE_API_PROVIDERS", None)
            self.assertIsNone(ProviderChain.from_env())

    def test_parses_two_providers(self):
        env = {
            "IMAGE_API_PROVIDERS": "fenno,backup",
            "IMAGE_API_FENNO_BASE_URL": "https://api.fenno.ai/v1",
            "IMAGE_API_FENNO_KEY": "sk-fenno",
            "IMAGE_API_FENNO_MODEL": "gpt-image-2",
            "IMAGE_API_BACKUP_BASE_URL": "https://backup.example.com/v1",
            "IMAGE_API_BACKUP_KEY": "sk-backup",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            # Make sure these don't pollute the test from earlier writes.
            os.environ.pop("IMAGE_API_KEY", None)
            os.environ.pop("IMAGE_API_BASE_URL", None)
            os.environ.pop("IMAGE_API_MODEL", None)
            chain = ProviderChain.from_env()
            self.assertIsNotNone(chain)
            self.assertEqual([p.name for p in chain.profiles], ["fenno", "backup"])
            self.assertEqual(chain.profiles[0].api_key, "sk-fenno")
            self.assertEqual(chain.profiles[1].api_key, "sk-backup")

    def test_raises_when_provider_missing_base_url(self):
        env = {
            "IMAGE_API_PROVIDERS": "fenno",
            "IMAGE_API_FENNO_KEY": "sk-fenno",
            # IMAGE_API_FENNO_BASE_URL deliberately missing
        }
        with patch.dict("os.environ", env, clear=False):
            with self.assertRaisesRegex(ValueError, "BASE_URL is not set"):
                ProviderChain.from_env()

    def test_custom_fallback_status(self):
        env = {
            "IMAGE_API_PROVIDERS": "a,b",
            "IMAGE_API_A_BASE_URL": "https://a.example.com/v1",
            "IMAGE_API_B_BASE_URL": "https://b.example.com/v1",
            "IMAGE_API_FALLBACK_STATUS": "503,network_error",
        }
        with patch.dict("os.environ", env, clear=False):
            chain = ProviderChain.from_env()
            self.assertEqual(chain.fallback_status, {503})
            self.assertTrue(chain.fallback_on_network_error)

    def test_invalid_fallback_status_rejected(self):
        env = {
            "IMAGE_API_PROVIDERS": "a,b",
            "IMAGE_API_A_BASE_URL": "https://a.example.com/v1",
            "IMAGE_API_B_BASE_URL": "https://b.example.com/v1",
            "IMAGE_API_FALLBACK_STATUS": "not-a-code",
        }
        with patch.dict("os.environ", env, clear=False):
            with self.assertRaisesRegex(ValueError, "Invalid IMAGE_API_FALLBACK_STATUS"):
                ProviderChain.from_env()


if __name__ == "__main__":
    unittest.main()