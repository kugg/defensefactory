#!/usr/bin/env python3
"""Capture one direct producer with an existing ticket opening; no shell or retry."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'factorycore').is_dir() else HERE.parent))
from factorycore.core import identity
from factorycore.trial_controls import stage_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opening', default=os.environ.get('DEFENSEFACTORY_STAGE_OPENING'))
    parser.add_argument('--id', required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New capture directory; never overwritten')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--challenge', type=Path)
    parser.add_argument('--variant', help='Declared variant, or baseline; required explicitly for support producers')
    parser.add_argument('--support', action='store_true')
    parser.add_argument('--purpose', default='Captured direct producer; no named-test acceptance implied')
    parser.add_argument('--protocol', choices=('command', 'go-test-json', 'factory-jsonl-v1'))
    parser.add_argument('--required-test', action='append', default=[])
    parser.add_argument('--evaluators', type=Path, help='Previously frozen relative-path/SHA-256 JSON map')
    parser.add_argument('--env', action='append', default=[], help='Explicit nonsecret KEY=VALUE override')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if not args.opening:
            raise ValueError('Retrieve a ticket-backed stage opening before running a case producer')
        opening_path = Path(args.opening).expanduser().resolve()
        opening = json.loads(opening_path.read_text())
        cwd = args.cwd.resolve()
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        challenge = json.loads(args.challenge.read_text()) if args.challenge else None
        subject = opening['scope']['subject']
        evaluators = json.loads(args.evaluators.read_text()) if args.evaluators else {}
        execution = {'format': args.protocol or 'command'}
        if execution['format'] == 'command':
            execution.update(reason=args.purpose, success_criteria='Direct producer exits zero; no test acceptance granted')
        else:
            execution['required_tests'] = args.required_test
        if challenge:
            plan = challenge['plan']
            if args.support and args.variant is None:
                raise ValueError('Support producers must explicitly select --variant baseline or the actual derived variant')
            if args.variant not in (None, 'baseline'):
                subject = next(v['subject'] for v in plan['variants'] if v['id'] == args.variant)
            if not args.support:
                if args.protocol or args.required_test or args.evaluators:
                    raise ValueError('Challenge evaluation uses its frozen plan; do not override the evaluator/protocol')
                command = command or plan['argv']
                execution, evaluators = plan['execution'], plan['evaluators']
        elif args.variant not in (None, 'baseline') or args.support:
            raise ValueError('A derived/support command needs the saved challenge declaration')
        if not command:
            raise ValueError('Supply a direct producer argv after --')
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in evaluators):
            raise ValueError('Evaluator manifest paths must be relative to cwd')
        environment = {}
        for item in args.env:
            key, separator, value = item.partition('=')
            if not separator or not key:
                raise ValueError('Environment override must be KEY=VALUE; never pass a secret')
            environment[key] = value
        specification = {'id': args.id, 'subject': subject,
            'performed_by': opening['scope']['performed_by'], 'argv': command, 'cwd': str(cwd),
            'timeout_seconds': args.timeout, 'execution': execution, 'environment': environment,
            'evaluator_files': {str((cwd / name).resolve()): digest for name, digest in evaluators.items()},
            'stage_start_reference': str(opening_path), 'stage_start_sha256': identity(opening)}
        if challenge:
            specification.update(challenge_plan_reference=str(args.challenge.resolve()),
                challenge_plan_sha256=identity(challenge),
                challenge_role='support' if args.support else 'evaluation', purpose=args.purpose)
        record = stage_command(opening, specification, args.output.resolve(), challenge)
        print(json.dumps({'receipt': str(args.output.resolve() / 'execution.json'),
                          'result': record['result'], 'producer_exit_code': record['exit_code']}))
        code = record['exit_code']
        return code if isinstance(code, int) and 0 < code < 256 else 0 if record['result'] == 'satisfied_within_scope' else 1
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
