#!/usr/bin/env python3
# osengineer_git_cmd.py — token-walk git command classifier.
# Determines whether a shell command invokes a specific git subcommand.
# Handles: bare `git commit`, `git -C path commit`, `VAR=x git commit`,
# `/usr/bin/git commit`.

import re
from pathlib import Path

ARGUMENT_TAKING_FLAGS = {
    "-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--exec-path", "--html-path", "--man-path", "--info-path", "--list-cmds",
}

BOOLEAN_FLAGS = {
    "-p", "--paginate", "--no-pager",
    "--no-replace-objects", "--bare",
    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
    "--icase-pathspecs", "--no-optional-locks",
    "-P", "--no-lazy-fetch",
    "--version", "--help",
}


def tokenize(cmd):
    tokens = []
    i = 0
    length = len(cmd)
    while i < length:
        while i < length and cmd[i].isspace():
            i += 1
        if i >= length:
            break
        token = ""
        while i < length and not cmd[i].isspace():
            if cmd[i] == "'":
                i += 1
                while i < length and cmd[i] != "'":
                    token += cmd[i]
                    i += 1
                if i < length:
                    i += 1
            elif cmd[i] == '"':
                i += 1
                while i < length and cmd[i] != '"':
                    token += cmd[i]
                    i += 1
                if i < length:
                    i += 1
            else:
                token += cmd[i]
                i += 1
        if token:
            tokens.append(token)
    return tokens


def is_git_subcommand(cmd, sub):
    if not cmd or not sub:
        return False
    tokens = tokenize(cmd)
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    if i >= len(tokens):
        return False
    git_token = tokens[i]
    i += 1
    if Path(git_token).name != "git":
        return False
    while i < len(tokens):
        t = tokens[i]
        eq_idx = t.find("=")
        flag_name = t[:eq_idx] if eq_idx != -1 else t
        if flag_name in ARGUMENT_TAKING_FLAGS:
            i += 1 if eq_idx != -1 else 2
            continue
        if t in BOOLEAN_FLAGS:
            i += 1
            continue
        break
    if i >= len(tokens):
        return False
    return tokens[i] == sub


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        print(is_git_subcommand(sys.argv[1], sys.argv[2]))
