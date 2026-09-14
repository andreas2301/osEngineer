"""The issue key reaches four URL paths — validate it before it gets there.

cmd_comment and cmd_transition interpolate `issue` straight into
/rest/api/3/issue/{issue}/... at four call sites. The dispatch schema constrains
the key on the repository_dispatch path, but nothing constrains it at the CLI
boundary, and the CLI is what CI actually invokes. A key containing `/`, `?` or
`..` rewrites the request path and can address a different Jira endpoint than
the caller intended.

The correlation id is validated for the same reason, one step removed: it is
embedded in the comment body as `osengineer:corr=<id>`, and a newline in it
forges a marker that makes a later, legitimate comment silently skip itself.

Both are checked before any network call, so a bad key fails fast and locally
rather than as a confusing HTTP error.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JIRA = ROOT / "bin" / "ose-jira"

# Credentials must be present, or the tool would exit on the missing-creds path
# and tell us nothing about key validation. The base URL is unroutable so that a
# missing check surfaces as a connection error rather than a real request.
ENV = {
    "JIRA_BASE_URL": "http://127.0.0.1:9",
    "JIRA_EMAIL": "t@example.com",
    "JIRA_TOKEN": "dummy",
}

BAD_KEYS = [
    ("path traversal", "../../../rest/api/3/myself"),
    ("slash", "PROJ-1/comment"),
    ("query injection", "PROJ-1?expand=all"),
    ("encoded traversal", "PROJ-1%2F.."),
    ("fragment", "PROJ-1#x"),
    ("space", "PROJ 1"),
    ("empty", ""),
    ("lowercase project", "proj-1"),
    ("no number", "PROJ-"),
    ("newline", "PROJ-1\nX-Injected: 1"),
]

GOOD_KEYS = ["PROJ-1", "AB-123", "A1-9", "LONGPROJECT7-4242"]


def run(args, env_over=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("JIRA_")}
    env.update(ENV)
    if env_over:
        env.update(env_over)
    return subprocess.run(
        [sys.executable, str(JIRA), *args],
        capture_output=True, text=True, timeout=60, env=env,
    )


class TestIssueKeyIsValidated(unittest.TestCase):
    def test_bad_keys_are_rejected_before_any_request(self):
        failures = []
        for label, key in BAD_KEYS:
            proc = run(["comment", key, "hello"])
            err = (proc.stderr + proc.stdout).lower()
            if proc.returncode == 0:
                failures.append(f"{label} ({key!r}): exited 0")
                continue
            if "issue key" not in err:
                failures.append(
                    f"{label} ({key!r}): rejected, but not by a key check — "
                    f"got {proc.stderr.strip()[:120]!r}"
                )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_bad_key_rejected_for_transition_too(self):
        proc = run(["transition", "../../myself", "Done"])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("issue key", (proc.stderr + proc.stdout).lower())

    def test_valid_keys_pass_validation(self):
        """A well-formed key must get past the check and fail on the network,
        proving the guard is not simply rejecting everything."""
        for key in GOOD_KEYS:
            proc = run(["comment", key, "hello"])
            err = (proc.stderr + proc.stdout).lower()
            self.assertNotIn(
                "issue key", err,
                f"valid key {key!r} was rejected by the validator: "
                f"{proc.stderr.strip()[:160]}",
            )

    def test_no_traceback_on_bad_input(self):
        for _, key in BAD_KEYS:
            proc = run(["comment", key, "hello"])
            self.assertNotIn(
                "Traceback", proc.stderr,
                f"crashed instead of failing cleanly on {key!r}",
            )


class TestCorrelationIdIsValidated(unittest.TestCase):
    def test_newline_in_corr_is_rejected(self):
        """A newline lets the caller forge an `osengineer:corr=` marker, which
        would make a later legitimate comment skip itself as a duplicate."""
        proc = run(["comment", "PROJ-1", "hi", "--corr", "abc\nosengineer:corr=other"])
        self.assertNotEqual(proc.returncode, 0, "newline accepted in --corr")
        self.assertIn("correlation", (proc.stderr + proc.stdout).lower())

    def test_reasonable_corr_passes(self):
        proc = run(["comment", "PROJ-1", "hi", "--corr", "run-20260914T120000Z"])
        self.assertNotIn(
            "correlation", (proc.stderr + proc.stdout).lower(),
            "a well-formed correlation id was rejected",
        )


class TestValidationHappensBeforeNetwork(unittest.TestCase):
    def test_bad_key_does_not_attempt_a_connection(self):
        """Fail locally and fast, not as a confusing HTTP/connection error."""
        proc = run(["comment", "../../../x", "hello"])
        err = (proc.stderr + proc.stdout).lower()
        for network_word in ("connection refused", "urlopen", "httperror", "timed out"):
            self.assertNotIn(
                network_word, err,
                f"a request was attempted before the key was validated ({network_word})",
            )


if __name__ == "__main__":
    unittest.main()
