import argparse
import json
import sys
from . import detect
from .install import install, uninstall, DEFAULT_POLICY, DEFAULT_PLAN_DIR


def main():
    parser = argparse.ArgumentParser(description='Repo profile skill installer')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('install', 'uninstall', 'detect', 'doctor'):
        sub = commands.add_parser(name)
        sub.add_argument('--repo', required=True)
        if name == 'install':
            sub.add_argument('--policy-file', default=DEFAULT_POLICY)
            sub.add_argument('--plan-dir', default=DEFAULT_PLAN_DIR)
        if name == 'detect':
            sub.add_argument('--write', action='store_true', help='write the proposed profile.json')
    args = parser.parse_args()
    try:
        if args.command == 'install':
            result = install(args.repo, policy=args.policy_file, plan_dir=args.plan_dir)
        elif args.command == 'uninstall':
            result = uninstall(args.repo)
        elif args.command == 'detect':
            result = detect.write(args.repo) if args.write else detect.report(args.repo)
            result = {'status': 'written' if args.write else 'detected', **result}
        else:
            result = detect.report(args.repo)
            pending = [r['fact'] for r in result['facts'] if r['status'] in ('unhandled', 'unconfigured')]
            result = {'status': 'needs-attention' if pending else 'ok', 'pending': pending,
                      'facts': result['facts'], 'unhandled': result['unhandled']}
            print(json.dumps(result))
            return 1 if pending else 0
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
