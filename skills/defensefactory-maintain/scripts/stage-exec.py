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
from factorycore.artifact_binding import expand_artifacts
from factorycore.core import sha
from factorycore.runtime_plan import selected_subject
from factorycore.evidence_records import write_json, now, dependency


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
    parser.add_argument('--comparison', help='Comparison ID admitted in the published opening; no relabeling')
    parser.add_argument('--runtime-plan', type=Path, help='Frozen runtime-plan receipt; --id selects its probe and argv')
    parser.add_argument('--purpose', default='Captured direct producer; no named-test acceptance implied')
    parser.add_argument('--protocol', choices=('command', 'go-test-json', 'factory-jsonl-v1'))
    parser.add_argument('--required-test', action='append', default=[])
    parser.add_argument('--evaluators', type=Path, help='Previously frozen relative-path/SHA-256 JSON map')
    parser.add_argument('--source-repo', type=Path, help='Observe clean Git source at the selected subject before/after a build')
    parser.add_argument('--produces', action='append', default=[], metavar='NAME=NEW_FILE')
    parser.add_argument('--use-artifact', action='append', default=[], metavar='NAME=BINDING_JSON')
    parser.add_argument('--assertions', type=Path, help='Frozen named exit-code/diagnostic assertion list JSON')
    parser.add_argument('--env', action='append', default=[], help='Explicit nonsecret KEY=VALUE override')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if not args.opening:
            raise ValueError('Retrieve a ticket-backed stage opening before running a case producer')
        registered=os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT')
        if registered and Path(registered).resolve() not in args.output.resolve().parents:
            raise ValueError('Write command captures inside DEFENSEFACTORY_EVIDENCE_ROOT')
        opening_path = Path(args.opening).expanduser().resolve()
        opening = json.loads(opening_path.read_text())
        cwd = args.cwd.resolve()
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        challenge = json.loads(args.challenge.read_text()) if args.challenge else None
        subject = selected_subject(opening, args.comparison)
        if args.comparison and (args.challenge or args.variant):
            raise ValueError('Use an admitted comparison OR a challenge variant')
        runtime = json.loads(args.runtime_plan.read_text()) if args.runtime_plan else None
        evaluators = json.loads(args.evaluators.read_text()) if args.evaluators else {}
        execution = {'format': args.protocol or 'command'}
        if execution['format'] == 'command':
            execution.update(reason=args.purpose, success_criteria='Direct producer exits zero; no test acceptance granted')
        else:
            execution['required_tests'] = args.required_test
        if args.assertions:
            if args.protocol or args.required_test:
                raise ValueError('Assertions file supplies its own frozen protocol and names')
            criteria = json.loads(args.assertions.read_text())
            execution = {'format':'process-assertions-v1','assertions':criteria,'required_tests':[c['name'] for c in criteria]}
        if runtime:
            if args.assertions or args.protocol or args.required_test or args.challenge:
                raise ValueError('Runtime declaration supplies protocol/argv; do not override it')
            probe = next(p for p in runtime['probes'] if p['id'] == args.id)
            if args.comparison != probe.get('comparison_id'):
                raise ValueError('Select the runtime probe comparison explicitly')
            command = command or probe['argv']
            execution = probe['execution']
        if challenge:
            plan = challenge['plan']
            if args.support and args.variant is None:
                raise ValueError('Support producers must explicitly select --variant baseline or the actual derived variant')
            if args.variant not in (None, 'baseline'):
                subject = next(v['subject'] for v in plan['variants'] if v['id'] == args.variant)
            if not args.support:
                if args.protocol or args.required_test or args.evaluators or args.assertions:
                    raise ValueError('Challenge evaluation uses its frozen plan; do not override the evaluator/protocol')
                command = command or plan['argv']
                execution, evaluators = plan['execution'], plan['evaluators']
        elif args.variant not in (None, 'baseline'):
            raise ValueError('A derived variant needs the saved challenge declaration; baseline setup uses --support')
        if not command:
            raise ValueError('Supply a direct producer argv after --')
        def bindings(items):
            result = {}
            for value in items:
                name, separator, file = value.partition('=')
                if not separator or not name or name in result:
                    raise ValueError('Use unique NAME=FILE bindings')
                result[name] = str(Path(file).resolve())
            return result
        produced, used = bindings(args.produces), bindings(args.use_artifact)
        invoker_command=list(command)
        command = expand_artifacts(command, used)
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
        specification['invoker_argv']=invoker_command
        if args.comparison:
            specification.update(comparison_id=args.comparison, purpose=args.purpose)
        if runtime:
            specification.update(runtime_plan_reference=str(args.runtime_plan.resolve()),runtime_plan_sha256=identity(runtime))
        if args.assertions:
            specification['evaluator_files'][str(args.assertions.resolve())] = sha(args.assertions.read_bytes())
        if args.source_repo:
            specification['source_repository'] = str(args.source_repo.resolve())
        if produced:
            specification['produces_artifacts'] = produced
        if used:
            specification['uses_artifacts'] = used
        if challenge:
            specification.update(challenge_plan_reference=str(args.challenge.resolve()),
                challenge_plan_sha256=identity(challenge),
                challenge_role='support' if args.support else 'evaluation', purpose=args.purpose)
        record = stage_command(opening, specification, args.output.resolve(), challenge)
        print(json.dumps({'receipt': str(args.output.resolve() / 'execution.json'),
                          'result': record['result'], 'producer_exit_code': record['exit_code']}))
        code = record['exit_code']
        if execution['format'] == 'process-assertions-v1':
            return 0 if record['result'] == 'satisfied_within_scope' else 1
        return code if isinstance(code, int) and 0 < code < 256 else 0 if record['result'] == 'satisfied_within_scope' else 1
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
        # Rejections are evidence too. Do not overwrite an existing capture or write outside a registered root.
        registered = os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT')
        destination = args.output.resolve()
        if not destination.exists() and (not registered or Path(registered).resolve() in destination.parents):
            destination.mkdir(parents=True,mode=0o700)
            dependencies=[]
            for name,source in [('opening',args.opening),('runtime-plan',args.runtime_plan),('requested-assertions',args.assertions)]:
                if source and Path(source).is_file():
                    snapshot=destination/(name+'.input')
                    snapshot.write_bytes(Path(source).read_bytes());snapshot.chmod(0o600)
                    dependencies.append(dependency(name,snapshot))
            write_json(destination/'admission-failure.json', {'record_type':'stage_admission_failure',
                'check_id':args.id,'result':'inconclusive','error':str(exc),'captured_at':now(),
                'opening_reference':args.opening,'requested_argv':args.command,
                'stage_start_sha256':identity(opening) if 'opening' in locals() else None,
                'evidence_dependencies':dependencies,
                'requested_options':{key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items() if key not in ('command','env')},
                'environment_override_names':[value.partition('=')[0] for value in args.env],
                'runtime_plan_reference':str(args.runtime_plan) if args.runtime_plan else None})
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
