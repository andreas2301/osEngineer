import argparse
import json
import sys
from .install import install, uninstall, DEFAULT_POLICY, DEFAULT_PLAN_DIR


def main():
    parser = argparse.ArgumentParser(description='Repo profile skill installer')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('install', 'uninstall'):
        sub = commands.add_parser(name)
        sub.add_argument('--repo', required=True)
        if name == 'install':
            sub.add_argument('--policy-file', default=DEFAULT_POLICY)
            sub.add_argument('--plan-dir', default=DEFAULT_PLAN_DIR)
    args = parser.parse_args()
    try:
        result = install(args.repo, policy=args.policy_file, plan_dir=args.plan_dir) if args.command == 'install' else uninstall(args.repo)
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
