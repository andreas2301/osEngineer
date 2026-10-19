#!/usr/bin/env python3
# osEngineer-session-start.py — Claude SessionStart hook.
#
# Loads .osengineer/state.yml on session start and emits a banner showing
# phase / team / budget / open handoffs / auto-nudge (if 5+ phases since
# last evolution).

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from osengineer_common import emit_context, find_osengineer_root, state_banner, fail_strict, read_payload


def main():
    data = read_payload()
    cwd = data.get("cwd") or os.getcwd()
    repo_root = find_osengineer_root(cwd)
    if not repo_root:
        return
    banner = state_banner(repo_root)
    if banner:
        emit_context("SessionStart", banner)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Strict: a malformed payload or any hook fault blocks (exit 2).
        fail_strict(Path(__file__).name, 'SessionStart', exc)
