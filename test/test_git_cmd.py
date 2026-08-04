import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
from osengineer_git_cmd import is_git_subcommand, tokenize


class TestTokenize(unittest.TestCase):
    def test_splits_on_whitespace(self):
        self.assertEqual(tokenize("git commit"), ["git", "commit"])

    def test_handles_single_quotes(self):
        self.assertEqual(tokenize("git commit -m 'hello world'"), ["git", "commit", "-m", "hello world"])

    def test_handles_double_quotes(self):
        self.assertEqual(tokenize('git commit -m "hello world"'), ["git", "commit", "-m", "hello world"])

    def test_handles_env_prefix(self):
        self.assertEqual(tokenize("GIT_PAGER=cat git log"), ["GIT_PAGER=cat", "git", "log"])


class TestIsGitSubcommand(unittest.TestCase):
    def test_detects_bare_git_commit(self):
        self.assertTrue(is_git_subcommand("git commit", "commit"))

    def test_detects_git_c_path_commit(self):
        self.assertTrue(is_git_subcommand("git -C /foo/bar commit", "commit"))

    def test_detects_env_prefixed_git_commit(self):
        self.assertTrue(is_git_subcommand("GIT_PAGER=cat git commit", "commit"))

    def test_detects_full_path_git_commit(self):
        self.assertTrue(is_git_subcommand("/usr/bin/git commit", "commit"))

    def test_rejects_git_log_when_looking_for_commit(self):
        self.assertFalse(is_git_subcommand("git log", "commit"))

    def test_rejects_non_git_command(self):
        self.assertFalse(is_git_subcommand("ls -la", "commit"))

    def test_handles_no_pager_flag(self):
        self.assertTrue(is_git_subcommand("git --no-pager commit", "commit"))


if __name__ == "__main__":
    unittest.main()
