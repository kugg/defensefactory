#!/usr/bin/env python3
"""Prepare/run one foreground OpenCode trial with frozen inputs and raw thinking events.

No ticket reset, retry loop, scheduler, credential read or skill installation.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'factorycore').exists() else HERE.parent))
from factorycore.assessment_resolution import session_usage
from factorycore.preflight import package_inventory
from factorycore.installation import default_config, load_config, opencode_config
from factorycore.trial_controls import stage_start, instant
from factorycore.evidence_inventory import inventory as handoff_inventory
from factorycore.trial_monitor import qualify as monitor_trial


def validate_opening(opening, packages):
    """Caller-supplied native records: ordering/correspondence, not authentication."""
    rebuilt = stage_start(opening['preparation'], opening['publication'], opening['retrieval'])
    if ({k: v for k, v in opening.items() if k != 'opened_at'} !=
            {k: v for k, v in rebuilt.items() if k != 'opened_at'}):
        raise ValueError('Stage opening changed or incomplete')
    if not instant(opening['retrieval']['retrieved_at']) <= instant(opening['opened_at']) <= instant(rebuilt['opened_at']):
        raise ValueError('Stage opening has invalid recorded order')
    if Path(opening['scope']['package']).resolve() not in {Path(p).resolve() for p in packages.values()}:
        raise ValueError('Opening must bind an actually selected stage package')


def prepare(prompt, project, skills, destination, launcher, model, installed, preferences=None, opening=None):
    if not isinstance(model, str) or not model.strip():
        raise ValueError('Select a provisioned provider/model with --model or OPENCODE_MODEL')
    prompt, project, skills = Path(prompt).resolve(), Path(project).resolve(), Path(skills).resolve()
    if not prompt.is_file() or not project.is_dir():
        raise ValueError('Existing explicit prompt and project required')
    packages = {p.name: str(p) for p in skills.glob('defensefactory*') if p.is_dir()}
    if 'defensefactory' not in packages:
        raise ValueError('Explicit factory packages required')
    inventory = package_inventory(packages)
    if opening is not None:
        validate_opening(opening, packages)
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    files = {'prompt.txt': prompt.read_bytes(), 'opencode-trial.py': Path(__file__).read_bytes(),
             'skill-inventory.json': json.dumps(inventory, indent=2).encode()}
    environment = {'DEFENSEFACTORY_EVIDENCE_ROOT':str(target/'evidence'),
                   'DEFENSEFACTORY_EVENT_LOG':str(target/'agent.jsonl'),
                   'DEFENSEFACTORY_HANDOFF_ROOT':str(target/'handoffs'),
                   'DEFENSEFACTORY_PUBLICATION_ROOT':str(target/'publication')}
    if preferences is not None:
        files['factory-config.json'] = (json.dumps(preferences, indent=2) + '\n').encode()
        files['opencode.json'] = (json.dumps(opencode_config(preferences), indent=2) + '\n').encode()
        environment.update({'DEFENSEFACTORY_CONFIG': str(target / 'factory-config.json'),
                       'OPENCODE_CONFIG': str(target / 'opencode.json'),
                       'OPENCODE_CONFIG_DIR': str(Path(preferences['skills_directory']).parent)})
    if opening is not None:
        files['stage-opening.json'] = (json.dumps(opening, indent=2) + '\n').encode()
        environment['DEFENSEFACTORY_STAGE_OPENING'] = str(target / 'stage-opening.json')
    for name, raw in files.items():
        (target / name).write_bytes(raw)
        (target / name).chmod(0o400)
    argv = [str(Path(launcher).expanduser().resolve()), 'run', '--auto', '--format', 'json',
            '--thinking', '--model', model, '--dir', str(project), files['prompt.txt'].decode()]
    manifest = {'model': model, 'argv': argv, 'environment': environment, 'installed_skills': str(Path(installed).expanduser().resolve()),
                'packages': packages, 'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
                'scope': 'One fresh session. No resume, automatic retry, ticket reset or lifecycle action by runner.'}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (target / 'manifest.json').chmod(0o400)
    return target, manifest


def execute(target, manifest, otel_log=None):
    target = Path(target)
    for name, digest in manifest['files'].items():
        if hashlib.sha256((target / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Captured runner input changed: ' + name)
    if 'stage-opening.json' not in manifest['files']:
        raise ValueError('Manual kickoff required: publish/read back the stage scope, retrieve its opening from the ticket, then pass --opening before --run')
    validate_opening(json.loads((target / 'stage-opening.json').read_text()), manifest['packages'])
    Path(manifest['environment']['DEFENSEFACTORY_EVIDENCE_ROOT']).mkdir(mode=0o700,exist_ok=False)
    for name in ('DEFENSEFACTORY_HANDOFF_ROOT','DEFENSEFACTORY_PUBLICATION_ROOT'):
        Path(manifest['environment'][name]).mkdir(mode=0o700,exist_ok=False)
    inputs=target/'evidence/invocation-inputs';inputs.mkdir(mode=0o700)
    for name in [*manifest['files'],'manifest.json']:
        shutil.copy2(target/name,inputs/name)
    for name, path in manifest['packages'].items():
        if (Path(manifest['installed_skills']) / name).resolve() != Path(path).resolve():
            raise ValueError('Installed skill differs from selected release: ' + name)
    captured = json.loads((target / 'skill-inventory.json').read_text())
    if package_inventory(manifest['packages']) != captured:
        raise ValueError('Skill files changed after preparation')
    timestamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (target / 'invocation-start.json').open('x') as f:
        json.dump({'started_at': timestamp(), 'requested_model': manifest['model']}, f)
    proc = None
    awake = None
    code = None
    interrupted = False
    error = None
    try:
        if Path('/usr/bin/caffeinate').exists():
            awake = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-s', '-w', str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with (target / 'agent.jsonl').open('xb') as log:
            os.chmod(target / 'agent.jsonl', 0o600)
            proc = subprocess.Popen(manifest['argv'], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                                    env={**os.environ, **manifest.get('environment', {})})
            code = proc.wait()
    except KeyboardInterrupt:
        interrupted = True
    except OSError as exc:
        error = str(exc)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            code = proc.returncode
        if awake is not None:
            awake.terminate()
            awake.wait(timeout=3)
    events = []
    log = target / 'agent.jsonl'
    if log.exists():
        for line in log.read_text(errors='replace').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
    sessions = sorted({e['sessionID'] for e in events if e.get('sessionID')})
    runner_code = 130 if interrupted else code if code else 1 if len(sessions) != 1 or error or any(e.get('type') == 'error' for e in events) else 0
    result = {'finished_at': timestamp(), 'producer_exit_code': code, 'runner_exit_code': runner_code,
              'observed_sessions': sessions, 'requested_model': manifest['model'],
              'interrupted': interrupted, 'startup_error': error,
              'reasoning_events': sum(e.get('type') == 'reasoning' for e in events),
              'factory_acceptance': 'not_evaluated',
              'snapshot_unchanged': all(hashlib.sha256((target / n).read_bytes()).hexdigest() == h for n, h in manifest['files'].items())}
    # Always leave a durable audit after the worker exits, including unfinished/failed work.
    requirements=target/'evidence/handoff-requirements.json'
    try:
        audit=handoff_inventory([target/'evidence',target/'handoffs',target/'publication'],target/'postflight',events=log,
            workspace=Path(manifest['argv'][manifest['argv'].index('--dir')+1]),
            opening=json.loads((target/'stage-opening.json').read_text()),
            requirements=json.loads(requirements.read_text()) if requirements.exists() else None,finalized=True)
        result['postflight_inventory']=str(target/'postflight/inventory.json')
        result['whole_attempt_handoff_ready']=audit['whole_attempt_handoff_ready']
        result['whole_attempt_handoff_reason']=audit.get('whole_attempt_handoff_reason')
        result['whole_attempt_handoff_problems']=audit['problems']
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result['whole_attempt_handoff_ready']=False
        result['whole_attempt_handoff_reason']='postflight_audit_failed'
        result['whole_attempt_handoff_problems']=[str(exc)]
        result['postflight_error']=str(exc)
    with (target / 'invocation-result.json').open('x') as f:
        json.dump(result, f, indent=2)
    if len(sessions) == 1:
        with (target / 'usage.json').open('x') as f:
            json.dump(session_usage(str(log), sessions[0]), f, indent=2)
    monitor = monitor_trial(log, result, otel_log=otel_log)
    with (target / 'monitor-report.json').open('x') as f:
        json.dump(monitor, f, indent=2)
    result['monitor_report'] = str(target / 'monitor-report.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--skills', help='Explicit skill directory, or use installed profile')
    parser.add_argument('--destination', required=True, help='New private invocation directory')
    parser.add_argument('--config', help='Factory profile; otherwise DEFENSEFACTORY_CONFIG or the default installed profile')
    parser.add_argument('--opening', type=Path, help='Ticket-retrieved operator-prepared stage-start receipt; required for --run')
    parser.add_argument('--launcher', default=os.environ.get('OPENCODE_OTEL'))
    parser.add_argument('--model', default=os.environ.get('OPENCODE_MODEL'))
    parser.add_argument('--installed-skills')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--otel-log', help='Optional local OTel log to bind by digest; raw telemetry remains local')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config_path = Path(args.config or os.environ.get('DEFENSEFACTORY_CONFIG') or default_config()).expanduser()
        explicit = bool(args.config or os.environ.get('DEFENSEFACTORY_CONFIG'))
        preferences = load_config(config_path) if explicit or config_path.exists() else None
        defaults = preferences or {}
        args.skills = args.skills or defaults.get('release_directory')
        args.installed_skills = args.installed_skills or defaults.get('skills_directory') or str(Path.home() / '.config/opencode/skills')
        args.model = args.model or defaults.get('model')
        args.launcher = args.launcher or defaults.get('launcher') or shutil.which('opencode-otel')
        if not args.skills:
            raise ValueError('Provide --skills or install a factory profile')
        if not args.launcher:
            raise ValueError('Provide --launcher or OPENCODE_OTEL, or install opencode-otel on PATH')
        opening = json.loads(args.opening.read_text()) if args.opening else None
        if args.run and opening is None:
            raise ValueError('Manual kickoff required: retrieve the ticket-backed stage-start receipt and supply --opening')
        target, manifest = prepare(args.prompt, args.project, args.skills, args.destination, args.launcher, args.model, args.installed_skills, preferences, opening)
        print(json.dumps({'prepared': str(target), 'requested_model': args.model, 'thinking': True}), flush=True)
        if args.run:
            result = execute(target, manifest, args.otel_log)
            print(json.dumps(result), flush=True)
            return result['runner_exit_code']
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
