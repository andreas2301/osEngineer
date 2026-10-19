"""Provider hosts, API version and secret-reference schemes are configuration."""
import unittest

from repo_integrations import IntegrationClient, IntegrationError
from repo_integrations.client import validate_config

PROJECT = "11111111-1111-1111-1111-111111111111"
PAGE = "22222222-2222-2222-2222-222222222222"


def cfg(**providers):
    return {"schemaVersion": 1, "readOnly": True, "limits": {"pageSize": 2}, "providers": providers}


class ProviderEndpoints(unittest.TestCase):
    def capture(self, config):
        calls = []

        def transport(*args):
            calls.append(args)
            if args[0] == "POST":
                return {"data": {"issues": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
            if isinstance(args[0], list):
                return []
            return {"object": "list", "results": [], "has_more": False, "next_cursor": None}
        return IntegrationClient(config, http_transport=transport, cli_transport=transport,
                                 environ={"T": "x"}, available=lambda _: True), calls

    def test_defaults_are_unchanged(self):
        client, calls = self.capture(cfg(
            github={"enabled": True, "repoAllowlist": ["o/r"]},
            linear={"enabled": True, "tokenEnv": "T", "projectIds": [PROJECT]},
            notion={"enabled": True, "tokenEnv": "T", "pageAllowlist": [PAGE]}))
        for name in ("github", "linear", "notion"):
            client.read(name)
        self.assertEqual(calls[0][0][:4], ["gh", "api", "--hostname", "github.com"])
        self.assertEqual(calls[1][1], "https://api.linear.app/graphql")
        self.assertTrue(calls[2][1].startswith(f"https://api.notion.com/v1/blocks/{PAGE}/children"))
        self.assertEqual(calls[2][2]["Notion-Version"], "2022-06-28")

    def test_self_hosted_endpoints_and_api_version(self):
        client, calls = self.capture(cfg(
            github={"enabled": True, "repoAllowlist": ["o/r"], "host": "ghe.example.com"},
            linear={"enabled": True, "tokenEnv": "T", "projectIds": [PROJECT],
                    "endpoint": "https://linear.example.com/graphql"},
            notion={"enabled": True, "tokenEnv": "T", "pageAllowlist": [PAGE],
                    "endpoint": "https://notion.example.com/v1", "apiVersion": "2025-09-03"}))
        for name in ("github", "linear", "notion"):
            client.read(name)
        self.assertEqual(calls[0][0][3], "ghe.example.com")
        self.assertEqual(calls[1][1], "https://linear.example.com/graphql")
        self.assertTrue(calls[2][1].startswith("https://notion.example.com/v1/blocks/"))
        self.assertEqual(calls[2][2]["Notion-Version"], "2025-09-03")

    def test_endpoint_settings_are_validated(self):
        bad = [
            {"github": {"host": "https://github.com"}},
            {"github": {"host": "-x"}},
            {"linear": {"endpoint": "http://plain.example.com"}},
            {"notion": {"apiVersion": "latest"}},
            {"github": {"apiVersion": "2022-06-28"}},
            {"linear": {"host": "x.example.com"}},
        ]
        for providers in bad:
            with self.subTest(providers=providers), self.assertRaises(IntegrationError):
                validate_config(cfg(**providers))


class SecretSchemes(unittest.TestCase):
    def test_op_is_the_default_scheme(self):
        validate_config(cfg(github={"secretRefs": ["op://vault/item/field"]}))
        with self.assertRaises(IntegrationError):
            validate_config(cfg(github={"secretRefs": ["vault://secret/app/key"]}))

    def test_vault_scheme_can_be_enabled(self):
        config = cfg(secrets={"enabled": True, "schemes": ["op", "vault"]},
                     github={"secretRefs": ["vault://secret/app/key", "op://v/i/f"]})
        validate_config(config)
        status = lambda tools: {r["provider"]: r["status"] for r in IntegrationClient(
            config, environ={}, available=lambda name: name in tools).doctor()["capabilities"]}["secrets"]
        self.assertEqual(status({"op", "vault"}), "metadata-only")
        self.assertEqual(status({"op"}), "unavailable")

    def test_unknown_or_empty_scheme_rejected(self):
        for schemes in (["sops"], [], "op", ["op", "op"]):
            with self.subTest(schemes=schemes), self.assertRaises(IntegrationError):
                validate_config(cfg(secrets={"schemes": schemes}))


if __name__ == "__main__":
    unittest.main()
