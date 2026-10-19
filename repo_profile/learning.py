"""Bounded sanitized usage receipts; no autonomous skill updates or remote writes."""
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

FIELDS = {'schemaVersion', 'taskId', 'model', 'repetition', 'condition', 'profileVersion',
          'status', 'inputTokens', 'outputTokens', 'wallSeconds', 'corrections', 'checks', 'evidence'}
SECRET = re.compile(r'(?:Bearer\s+\S+|(?:sk|ghp|github_pat|ntn)_[A-Za-z0-9_-]{12,}|password\s*=|secret\s*=)', re.I)


def validate(receipt):
    if not isinstance(receipt, dict) or set(receipt) - FIELDS:
        raise ValueError('Receipt contains unsupported fields; raw transcripts are not allowed')
    if type(receipt.get('schemaVersion')) is not int or receipt['schemaVersion'] != 1:
        raise ValueError('Receipt schemaVersion must be 1')
    for key in ('taskId', 'model', 'profileVersion', 'condition'):
        value = receipt.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 160 or SECRET.search(value):
            raise ValueError(f'Invalid receipt field: {key}')
    if receipt.get('status') not in ('passed', 'failed', 'needs-human', 'not-run'):
        raise ValueError('Unsupported status')
    for key in ('repetition', 'inputTokens', 'outputTokens', 'wallSeconds', 'corrections'):
        value = receipt.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{key} must be a finite nonnegative number')
        if key != 'wallSeconds' and not isinstance(value, int):
            raise ValueError(f'{key} must be an integer')
    if receipt['repetition'] < 1:
        raise ValueError('repetition must start at 1')
    evidence = receipt.get('evidence', [])
    if not isinstance(evidence, list) or len(evidence) > 20:
        raise ValueError('evidence must be a bounded locator list')
    for item in evidence:
        if not isinstance(item, str) or len(item) > 300 or '\n' in item or SECRET.search(item):
            raise ValueError('Invalid evidence locator')
    checks = receipt.get('checks', [])
    if not isinstance(checks, list) or len(checks) > 20:
        raise ValueError('checks must be a bounded receipt list')
    for item in checks:
        if not isinstance(item, dict) or set(item) != {'name', 'status'} or item['status'] not in ('passed', 'failed', 'not-run'):
            raise ValueError('Invalid check receipt')
        if not isinstance(item['name'], str) or len(item['name']) > 160 or SECRET.search(item['name']):
            raise ValueError('Invalid check name')
    if receipt['status'] == 'passed' and (not checks or any(c['status'] != 'passed' for c in checks)):
        raise ValueError('A passed task requires observed passed checks')
    return receipt


def read(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError('Usage file exceeds the bounded read limit')
    rows = [validate(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    identities = [(r['taskId'], r['model'], r['repetition'], r['condition']) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError('Duplicate observations would distort the comparison')
    return rows


def summarize(rows):
    for row in rows:
        validate(row)
    cohorts = {(r['condition'], r['profileVersion']) for r in rows}
    if len(cohorts) > 1:
        raise ValueError('A learning group requires one condition and profileVersion')
    successful = [r for r in rows if r['status'] == 'passed']
    first = [r for r in rows if r['repetition'] == 1]
    tasks = {(r['taskId'], r['model']) for r in rows}
    stable = sum(all(r['status'] == 'passed' for r in rows if (r['taskId'], r['model']) == task) for task in tasks)
    total_tokens = sum(r['inputTokens'] + r['outputTokens'] for r in rows)
    return {'observations': len(rows), 'passed': len(successful),
            'passAt1': sum(r['status'] == 'passed' for r in first) / len(first) if first else None,
            'allObservedRepetitionsPassRate': stable / len(tasks) if tasks else None,
            'totalTokens': total_tokens, 'tokensPerSuccessfulTask': total_tokens / len(successful) if successful else None,
            'totalWallSeconds': sum(r['wallSeconds'] for r in rows),
            'corrections': sum(r['corrections'] for r in rows)}


def compare(baseline, candidate):
    identity = lambda r: (r['taskId'], r['model'], r['repetition'])
    left, right = {identity(r) for r in baseline}, {identity(r) for r in candidate}
    if not left or left != right:
        raise ValueError('Comparison requires identical nonempty task/model/repetition coverage')
    if len(left) != len(baseline) or len(right) != len(candidate):
        raise ValueError('Each comparison arm must contain one observation per case')
    a, b = summarize(baseline), summarize(candidate)
    return {'comparable': True, 'baseline': a, 'candidate': b,
            'tokensDelta': b['totalTokens'] - a['totalTokens'],
            'passedDelta': b['passed'] - a['passed'],
            'improvementProven': False,
            'note': 'Behavioral acceptance and safety-case results must be reviewed before promotion.'}


def main():
    parser = argparse.ArgumentParser(description='Sanitized Repo profile usage evidence')
    sub = parser.add_subparsers(dest='command', required=True)
    record = sub.add_parser('record'); record.add_argument('--input', required=True); record.add_argument('--out', required=True)
    summary = sub.add_parser('summarize'); summary.add_argument('path')
    comparison = sub.add_parser('compare'); comparison.add_argument('baseline'); comparison.add_argument('candidate')
    args = parser.parse_args()
    try:
        if args.command == 'record':
            path = Path(args.input)
            if path.stat().st_size > 32_000:
                raise ValueError('Receipt is too large')
            row = validate(json.loads(path.read_text()))
            out = Path(args.out)
            if out.exists() and any((r['taskId'], r['model'], r['repetition'], r['condition']) ==
                                    (row['taskId'], row['model'], row['repetition'], row['condition']) for r in read(out)):
                raise ValueError('Observation already recorded')
            out.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, 'a') as stream:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            result = {'status': 'recorded', 'taskId': row['taskId']}
        elif args.command == 'summarize':
            result = summarize(read(args.path))
        else:
            result = compare(read(args.baseline), read(args.candidate))
        print(json.dumps(result))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
