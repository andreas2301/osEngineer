import contextlib
import io
import json
import unittest
from unittest.mock import patch

from repo_integrations import IntegrationClient, IntegrationError
from repo_integrations.client import _NoRedirect, validate_config
from repo_integrations.__main__ import main

PROJECT = "11111111-1111-1111-1111-111111111111"
PAGE = "22222222-2222-2222-2222-222222222222"
SHA = "a" * 40


def config(name="linear", **limits):
    settings = {"enabled": True, "tokenEnv": "TEST_TOKEN"}
    settings.update({"linear": {"projectIds": [PROJECT]}, "notion": {"pageAllowlist": [PAGE]},
                     "github": {"repoAllowlist": ["owner/repo"]}}.get(name, {}))
    return {"schemaVersion": 1, "readOnly": True, "limits": {"pageSize": 2, **limits},
            "providers": {name: settings}}


def linear(nodes=None, more=False, cursor=None):
    return {"data": {"issues": {"nodes": nodes or [],
                               "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}}


def issue(number, title="task"):
    return {"identifier": f"TEST-{number}", "title": title, "state": {"name": "Backlog"}}


def block(number, text="text", children=False):
    return {"id": str(number), "type": "paragraph", "has_children": children,
            "paragraph": {"rich_text": [{"plain_text": text}]}}


def notion(nodes=None, more=False, cursor=None):
    return {"object": "list", "results": nodes or [], "has_more": more, "next_cursor": cursor}


def pr(number):
    return {"number": number, "title": "PR", "head": {"sha": SHA}, "draft": False}


class ConnectorTests(unittest.TestCase):
    def client(self, name="linear", responses=None, **limits):
        calls = []
        responses = iter(responses or [])
        def transport(*args):
            calls.append(args)
            return next(responses)
        client = IntegrationClient(config(name, **limits), http_transport=transport,
                                   cli_transport=transport, environ={"TEST_TOKEN": "sensitive-value"},
                                   available=lambda _: True, clock=lambda: "fixed-time")
        return client, calls

    def test_doctor_never_invokes_transports(self):
        client, calls = self.client()
        self.assertEqual(client.doctor()["capabilities"][0]["status"], "available-unverified")
        self.assertEqual(calls, [])

    def test_metadata_only_op_and_unsupported_are_honest(self):
        cfg = config("secrets")
        cfg["providers"]["observability"] = {"enabled": True}
        client = IntegrationClient(cfg, available=lambda _: True, environ={})
        rows = {x["provider"]: x for x in client.doctor()["capabilities"]}
        self.assertEqual(rows["secrets"]["status"], "metadata-only")
        self.assertEqual(rows["observability"]["status"], "unsupported-reader")
        with self.assertRaises(IntegrationError):
            client.read("secrets")

    def test_config_forbids_tokens_urls_and_writes(self):
        for field in ["token", "url", "apiKey", "allowWrites", "command"]:
            cfg = config()
            cfg["providers"]["linear"][field] = "sensitive-value"
            with self.subTest(field=field), self.assertRaises(IntegrationError):
                validate_config(cfg)
        cfg = config()
        cfg["readOnly"] = False
        with self.assertRaises(IntegrationError):
            validate_config(cfg)

    def test_config_requires_real_scope(self):
        cfg = config()
        cfg["providers"]["linear"]["projectIds"] = []
        with self.assertRaises(IntegrationError):
            validate_config(cfg)

    def test_scope_rejects_cli_injection(self):
        cfg = config("github")
        cfg["providers"]["github"]["repoAllowlist"] = ["--hostname evil/repo"]
        with self.assertRaises(IntegrationError):
            validate_config(cfg)

    def test_limits_reject_bool_and_large_values(self):
        for value in [True, 0, 101, "2"]:
            with self.subTest(value=value), self.assertRaises(IntegrationError):
                validate_config(config(pageSize=value))

    def test_linear_pagination_and_auth(self):
        client, calls = self.client(responses=[linear([issue(1)], True, "a"), linear([issue(2)])])
        row = client.read("linear")
        self.assertTrue(row["complete"])
        self.assertEqual(row["fetchedAt"], "fixed-time")
        self.assertEqual(len(row["items"]), 2)
        self.assertEqual(calls[1][3]["variables"]["after"], "a")
        self.assertEqual(calls[0][2]["Authorization"], "sensitive-value")
        self.assertNotIn("mutation", calls[0][3]["query"])
        self.assertEqual(calls[0][3]["variables"]["project"], PROJECT)

    def test_linear_error_not_empty(self):
        client, _ = self.client(responses=[{"errors": [{"message": "sensitive-value"}], "data": None}])
        with self.assertRaises(IntegrationError) as caught:
            client.read("linear")
        self.assertNotIn("sensitive-value", str(caught.exception))

    def test_linear_missing_pageinfo_fails_closed(self):
        client, _ = self.client(responses=[{"data": {"issues": {"nodes": []}}}])
        with self.assertRaisesRegex(IntegrationError, "completeness"):
            client.read("linear")

    def test_linear_missing_cursor_fails_closed(self):
        client, _ = self.client(responses=[linear([], True)])
        with self.assertRaisesRegex(IntegrationError, "cursor"):
            client.read("linear")

    def test_linear_repeated_cursor_fails(self):
        client, _ = self.client(responses=[linear([], True, "x"), linear([], True, "x")])
        with self.assertRaisesRegex(IntegrationError, "advance"):
            client.read("linear")

    def test_linear_empty_complete_is_real_empty(self):
        client, _ = self.client(responses=[linear()])
        self.assertEqual(client.read("linear")["items"], [])

    def test_linear_bound_reports_incomplete(self):
        client, calls = self.client(responses=[linear([issue(1)], True, "x")], maxPages=1)
        self.assertFalse(client.read("linear")["complete"])
        self.assertEqual(len(calls), 1)

    def test_redacts_credentials_and_caps_text(self):
        client, _ = self.client(responses=[linear([issue(1, "sensitive-value ghp_otherSecret " + "x" * 100)])], maxTextChars=40)
        row = client.read("linear")
        self.assertNotIn("sensitive-value", json.dumps(row))
        self.assertNotIn("ghp_otherSecret", json.dumps(row))
        self.assertLessEqual(len(row["items"][0]["title"]), 40)

    def test_item_output_bound_is_not_full_coverage(self):
        client, _ = self.client(responses=[linear([issue(1), issue(2)])], maxItems=1)
        row = client.read("linear")
        self.assertEqual(len(row["items"]), 1)
        self.assertEqual(row["omittedItems"], 1)
        self.assertFalse(row["complete"])

    def test_unread_scopes_mark_incomplete(self):
        client, _ = self.client(responses=[linear([issue(1)])], maxItems=1)
        client.config["providers"]["linear"]["projectIds"].append(PAGE)
        self.assertFalse(client.read("linear")["complete"])

    def test_missing_credentials_never_call_http(self):
        client, calls = self.client()
        client.env = {}
        with self.assertRaises(IntegrationError):
            client.read("linear")
        self.assertEqual(calls, [])

    def test_transport_failure_does_not_leak_secret(self):
        client, _ = self.client()
        def broken(*_):
            raise RuntimeError("sensitive-value")
        client.http = broken
        with self.assertRaises(IntegrationError) as caught:
            client.read("linear")
        self.assertNotIn("sensitive-value", str(caught.exception))

    def test_notion_pages_bound_and_children_scope(self):
        client, calls = self.client("notion", [notion([block(1, children=True)], True, "a/b"), notion([block(2)])])
        row = client.read("notion")
        self.assertTrue(row["complete"])
        self.assertFalse(row["scopes"][0]["descendantsRead"])
        self.assertTrue(row["items"][0]["hasChildren"])
        self.assertIn("start_cursor=a%2Fb", calls[1][1])
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer sensitive-value")

    def test_notion_error_and_unknown_pagination(self):
        for response in [{"object": "error", "message": "sensitive-value"}, {"results": []}]:
            client, _ = self.client("notion", [response])
            with self.subTest(response=response), self.assertRaises(IntegrationError):
                client.read("notion")

    def test_notion_requires_cursor(self):
        client, _ = self.client("notion", [notion([], True)])
        with self.assertRaises(IntegrationError):
            client.read("notion")

    def test_notion_bound_reports_incomplete(self):
        client, _ = self.client("notion", [notion([block(1)], True, "x")], maxPages=1)
        self.assertFalse(client.read("notion")["complete"])

    def test_redirect_cannot_forward_credentials(self):
        with self.assertRaises(IntegrationError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://attacker.example")

    def test_github_reads_only_configured_repo_and_head(self):
        client, calls = self.client("github", [[pr(1), pr(2)], []])
        row = client.read("github")
        self.assertTrue(row["complete"])
        self.assertEqual(row["items"][0]["head"], SHA)
        self.assertEqual(calls[0][0][:6], ["gh", "api", "--hostname", "github.com", "--method", "GET"])
        self.assertIn("repos/owner/repo/pulls", calls[0][0][6])
        self.assertEqual(len(calls), 2)

    def test_head_identity_survives_tiny_text_budget(self):
        client, _ = self.client("github", [[pr(1)]], maxTextChars=1)
        self.assertEqual(client.read("github")["items"][0]["head"], SHA)

    def test_github_full_last_page_is_unknown_not_complete(self):
        client, _ = self.client("github", [[pr(1), pr(2)]], maxPages=1)
        self.assertFalse(client.read("github")["complete"])

    def test_github_error_not_empty(self):
        client, _ = self.client("github", [{"message": "error"}])
        with self.assertRaises(IntegrationError):
            client.read("github")

    def test_github_missing_head_fails_closed(self):
        client, _ = self.client("github", [[{"number": 1}]])
        with self.assertRaises(IntegrationError):
            client.read("github")

    def test_malformed_nested_data_fails_safely(self):
        client, _ = self.client(responses=[{"data": "sensitive-value"}])
        with self.assertRaises(IntegrationError) as caught:
            client.read("linear")
        self.assertNotIn("sensitive-value", str(caught.exception))

    def test_unknown_provider_never_uses_transport(self):
        client, calls = self.client()
        with self.assertRaises(IntegrationError):
            client.read("https://attacker.example")
        self.assertEqual(calls, [])

    def test_cli_default_preflight_does_not_read(self):
        output = io.StringIO()
        with patch("repo_integrations.__main__.load_config", return_value=config()), patch.object(IntegrationClient, "read", side_effect=AssertionError("network")), contextlib.redirect_stdout(output):
            self.assertEqual(main(["preflight", "--config", "ignored"]), 0)
        self.assertEqual(json.loads(output.getvalue())["evidence"], [])

    def test_cli_incomplete_returns_nonzero(self):
        with patch("repo_integrations.__main__.load_config", return_value=config()), patch.object(IntegrationClient, "read", return_value={"complete": False}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["preflight", "--config", "ignored", "--provider", "linear"]), 1)

    def test_cli_error_is_compact_and_nonzero(self):
        with patch("repo_integrations.__main__.load_config", side_effect=IntegrationError("invalid config")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor", "--config", "ignored"]), 1)
        self.assertFalse(json.loads(output.getvalue())["complete"])


if __name__ == "__main__":
    unittest.main()
