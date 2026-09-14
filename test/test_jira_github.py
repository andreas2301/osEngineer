"""Jira and GitHub as systems of record, with the smallest client that works.

Every Jira operation in the repo today is an MCP tool name inside an example
markdown file. Headless CI has no MCP server, so a headless run cannot report
anything back to a ticket.

Constraints this encodes:

  * Zero dependencies. urllib/json/base64 from the stdlib, no requests.
  * Credentials come from the environment ONLY — never from argv, where they
    would land in the process table and in CI logs.
  * Comments are idempotent. Jira returns comments oldest-first and paginates,
    so a naive first-page check silently duplicates on long tickets; posting is
    keyed by a correlation marker that must be searched across all pages.
  * Ticket text is untrusted input. It is never interpolated into a shell
    command or a workflow `run:` body.
"""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JIRA = ROOT / "bin" / "ose-jira"


def read(p):
    return p.read_text() if p.exists() else ""


class TestJiraClientExists(unittest.TestCase):
    def test_client_present_and_executable(self):
        self.assertTrue(
            JIRA.exists(),
            "bin/ose-jira does not exist; a headless run cannot report to a "
            "ticket, and every Jira operation in the repo is an MCP tool name "
            "in an example file that CI cannot reach",
        )
        self.assertTrue(os.access(JIRA, os.X_OK), "bin/ose-jira is not executable")

    def test_zero_dependencies(self):
        body = read(JIRA)
        for banned in ("import requests", "from requests", "import httpx", "import jira"):
            self.assertNotIn(banned, body, f"zero-dependency policy: {banned}")
        self.assertIn("urllib", body, "expected a stdlib urllib client")

    def test_only_two_verbs(self):
        body = read(JIRA)
        self.assertIn("comment", body)
        self.assertIn("transition", body)


class TestCredentialsComeFromEnvironment(unittest.TestCase):
    def test_no_token_flag_in_argv(self):
        body = read(JIRA)
        offenders = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(body.splitlines(), 1)
            if re.search(r'["\']--(token|password|api-key|apikey)\b', line)
        ]
        self.assertEqual(
            offenders, [],
            "a credential is accepted as a command-line flag, which exposes it "
            "in the process table and in CI logs:\n" + "\n".join(offenders),
        )

    def test_reads_env_vars(self):
        body = read(JIRA)
        self.assertTrue(
            "JIRA_TOKEN" in body or "JIRA_API_TOKEN" in body,
            "no JIRA token environment variable is read",
        )
        self.assertIn("JIRA_BASE_URL", body)

    def test_refuses_without_credentials(self):
        if not JIRA.exists():
            self.skipTest("client not written yet")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("JIRA_", "ATLASSIAN_"))}
        proc = subprocess.run(
            [sys.executable, str(JIRA), "comment", "PROJ-1", "hello"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        self.assertNotEqual(
            proc.returncode, 0,
            "the client ran without credentials instead of failing loudly",
        )
        self.assertNotIn("Traceback", proc.stderr, "should fail cleanly, not crash")


class TestCommentIdempotency(unittest.TestCase):
    def test_uses_a_correlation_marker(self):
        body = read(JIRA)
        self.assertIn(
            "osengineer:corr", body,
            "comments carry no correlation marker, so a retried CI job posts "
            "duplicate comments on the ticket",
        )

    def test_pages_through_comments(self):
        body = read(JIRA)
        self.assertTrue(
            any(t in body for t in ("startAt", "orderBy", "maxResults")),
            "the duplicate check reads only the first page; Jira returns "
            "comments oldest-first and paginates, so on a long ticket the "
            "marker is never seen and every run comments again",
        )


class TestUntrustedTicketText(unittest.TestCase):
    def test_no_shell_interpolation_of_ticket_text(self):
        body = read(JIRA)
        offenders = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(body.splitlines(), 1)
            if "shell=True" in line
        ]
        self.assertEqual(
            offenders, [],
            "subprocess with shell=True near ticket text is a command "
            "injection vector:\n" + "\n".join(offenders),
        )


class TestDispatchPayloadSchema(unittest.TestCase):
    SCHEMA = ROOT / "specs" / "SCHEMAS" / "dispatch-payload.schema.json"

    def test_schema_exists(self):
        self.assertTrue(
            self.SCHEMA.exists(),
            "no specs/SCHEMAS/dispatch-payload.schema.json — the inbound "
            "repository_dispatch envelope is unvalidated",
        )

    def test_schema_is_valid_json_and_lowercase_types(self):
        import json
        if not self.SCHEMA.exists():
            self.skipTest("schema not written yet")
        data = json.loads(self.SCHEMA.read_text())
        bad = []

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "type" and isinstance(v, str) and v != v.lower():
                        bad.append((path, v))
                    walk(v, f"{path}/{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")

        walk(data)
        self.assertEqual(bad, [], f"JSON Schema types must be lowercase: {bad}")

    def test_caps_top_level_keys(self):
        import json
        if not self.SCHEMA.exists():
            self.skipTest("schema not written yet")
        data = json.loads(self.SCHEMA.read_text())
        props = data.get("properties", {})
        self.assertLessEqual(
            len(props), 10,
            "GitHub caps repository_dispatch client_payload at 10 top-level "
            f"keys; this schema declares {len(props)}",
        )


class TestDocumentedIntegrationPath(unittest.TestCase):
    def test_rest_vs_mcp_is_documented(self):
        doc = ROOT / "integrations" / "jira-rest.md"
        self.assertTrue(
            doc.exists(),
            "integrations/jira-rest.md missing — REST is the CI path and MCP "
            "the workstation path; that split needs writing down",
        )


if __name__ == "__main__":
    unittest.main()
