#!/usr/bin/env python3
"""Installed skill entrypoint; imports only the packaged runtime requested."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    if len(sys.argv) < 2:
        print('Usage: repo_profile.py runtime|integrations|learn <arguments>', file=sys.stderr)
        return 2
    module = {'runtime': 'repo_runtime', 'integrations': 'repo_integrations',
              'learn': 'repo_profile.learning'}.get(sys.argv.pop(1))
    if module is None:
        print('Unknown Repo profile component', file=sys.stderr)
        return 2
    import runpy
    runpy.run_module(module, run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
