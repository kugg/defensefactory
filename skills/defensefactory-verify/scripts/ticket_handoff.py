#!/usr/bin/env python3
"""Prepare Linear checkpoint patches and verify connector readback; no API credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'factorycore').exists() else HERE.parent))
from factorycore.attempt_state import READBACK_SCHEMA, prepare_active_attempt

START = '## Factory checkpoint'
END = '## Factory resources'
ATTEMPT_START = '<!-- defensefactory-active-attempt:start -->'
ATTEMPT_END = '<!-- defensefactory-active-attempt:end -->'


def normalize(text):
    # Linear may serialize Markdown tables as paragraphs. Preserve words/order.
    return re.findall(r'[\w]+|[→]', text)


def managed(description):
    if START not in description:
        return None
    if description.count(START) != 1 or description.count(END) != 1:
        raise ValueError('Ambiguous or incomplete ticket checkpoint; reconcile it in Linear')
    start, end = description.index(START), description.index(END)
    if end <= start:
        raise ValueError('Invalid checkpoint boundaries')
    return description[start:end]


def managed_attempt(description):
    if ATTEMPT_START not in description and ATTEMPT_END not in description:
        return None
    if description.count(ATTEMPT_START) != 1 or description.count(ATTEMPT_END) != 1:
        raise ValueError('Ambiguous or incomplete active-attempt checkpoint; reconcile it in Linear')
    start, end = description.index(ATTEMPT_START), description.index(ATTEMPT_END) + len(ATTEMPT_END)
    if end <= start:
        raise ValueError('Invalid active-attempt checkpoint boundaries')
    return description[start:end]


def checkpoint_id(block):
    found = re.search(r'(?m)^Checkpoint: `?([A-Za-z0-9._:-]+)`?\s*$', block or '')
    if not found:
        raise ValueError('Checkpoint identity missing')
    return found[1]


def render_attempt(checkpoint):
    reusable = {item['id'] for item in checkpoint['inputs'] if item['classification'] == 'reusable'}
    rows = [ATTEMPT_START, '## Factory active attempt', '',
            f"Checkpoint: `{checkpoint['checkpoint_id']}`",
            f"Checkpoint digest: `{checkpoint['checkpoint_sha256']}`",
            f"Attempt: `{checkpoint['attempt']}`", f"Stage: `{checkpoint['stage']}`",
            f"Subject: `{checkpoint['subject']['repository']}@{checkpoint['subject']['revision']}`",
            f"Finding status: {checkpoint['finding_status']}", f"Result: `{checkpoint['result']}`",
            f"Execution permitted: `{'true' if checkpoint['execution_permitted'] else 'false'}`", '',
            checkpoint['reason'], '', '### Minimal verified input closure', '',
            '| ID | Kind | Reference | Binding |', '| --- | --- | --- | --- |']
    for item in checkpoint['inputs']:
        if item['id'] not in reusable:
            continue
        binding = item['binding'].get('sha256') or item['binding'].get('native_id')
        rows.append('| ' + ' | '.join(str(value).replace('|', '/') for value in
                    (item['id'], item['kind'], item['reference'], binding)) + ' |')
    rows += ['', '### Evidence outside the active closure', '',
             '| ID | Classification | Rationale |', '| --- | --- | --- |']
    for item in checkpoint['inputs']:
        if item['id'] in reusable:
            continue
        rows.append('| ' + ' | '.join(str(value).replace('|', '/') for value in
                    (item['id'], item['classification'], item['rationale'])) + ' |')
    if all(item['id'] in reusable for item in checkpoint['inputs']):
        rows.append('| None | historical/stale/refresh-required | No excluded inputs recorded. |')
    rows += ['', '### Current applicability', '',
             f"Result: `{checkpoint['applicability']['result']}`  ",
             f"Evidence: {checkpoint['applicability']['reference']}  ",
             f"Evidence SHA-256: `{checkpoint['applicability']['sha256']}`", '']
    rows += ['### Blocking refresh work', '']
    rows += ['- ' + value for value in checkpoint['blockers']] or ['- None.']
    rows += ['', '### Boundaries and next action', '', checkpoint['boundaries'], '',
             f"Next action: {checkpoint['next_action']}", f"Owner: {checkpoint['owner']}", '',
             'Historical comments and attachments remain append-only evidence. This block is only the current execution pointer.',
             ATTEMPT_END]
    rendered = '\n'.join(rows)
    if rendered.count(ATTEMPT_START) != 1 or rendered.count(ATTEMPT_END) != 1:
        raise ValueError('Active-attempt text contains reserved boundary markers')
    return rendered


def prepare_attempt(issue, request):
    if issue.get('id') != request.get('case'):
        raise ValueError('Ticket/attempt case mismatch')
    description = issue.get('description') or ''
    old = managed_attempt(description)
    predecessor = checkpoint_id(old) if old else None
    if request.get('previous_checkpoint') != predecessor:
        raise ValueError('Stale active attempt; fetch the ticket and reconcile its current pointer')
    checkpoint = prepare_active_attempt(request)
    if checkpoint['checkpoint_id'] == predecessor:
        raise ValueError('A bounded retry needs a new active checkpoint identifier')
    block = render_attempt(checkpoint)
    patch = ({'op': 'replace', 'old_string': old, 'new_string': block} if old else
             {'op': 'prepend', 'text': block + '\n\n'})
    return {
        'schema': 'defensefactory/active-attempt-publication/v1',
        'case': issue['id'],
        'read_updated_at': issue.get('updatedAt'),
        'read_description_sha256': hashlib.sha256(description.encode()).hexdigest(),
        'predecessor': predecessor,
        'checkpoint_id': checkpoint['checkpoint_id'],
        'checkpoint': checkpoint,
        'expected_checkpoint': block,
        'linear_request': {'id': issue['id'], 'patch': [patch]},
        'note': 'The exact-anchor patch replaces only the active pointer. It is not a server lease and never deletes historical comments or attachments.',
    }


def acknowledge_attempt(issue, prepared):
    if issue.get('id') != prepared.get('case'):
        raise ValueError('Active-attempt readback is for another issue')
    actual = managed_attempt(issue.get('description') or '')
    if actual is None or checkpoint_id(actual) != prepared['checkpoint_id']:
        raise ValueError('Active-attempt publication not observed; do not execute the stage')
    if normalize(actual) != normalize(prepared['expected_checkpoint']):
        raise ValueError('Active-attempt readback differs from the published pointer')
    checkpoint = prepared['checkpoint']
    return {
        'schema': READBACK_SCHEMA,
        'case': issue['id'],
        'checkpoint_id': checkpoint['checkpoint_id'],
        'checkpoint_sha256': checkpoint['checkpoint_sha256'],
        'ticket_updated_at': issue.get('updatedAt'),
        'ticket_description_sha256': hashlib.sha256(issue['description'].encode()).hexdigest(),
        'publication': 'observed_in_connector_readback',
        'note': 'Confirms the current ticket pointer only; referenced input bytes and stage acceptance remain separate evidence.',
    }


def render(state):
    source_stop=state.get('early_disposition')=='stop_source'
    early=state.get('early_disposition') in ('close','disqualify','stop_source')
    required = ('case', 'checkpoint_id', 'current_stage', 'overall_result', 'summary',
                'stages', 'obligations', 'next_actions', 'open_decisions', 'limitations', 'authorization')
    required += ('disposition_receipt_reference','disposition_receipt_sha256','target_scope_reference') if early else ('candidate_revision','base_revision','contract_version','contract_sha256')
    if any(key not in state for key in required):
        raise ValueError('Incomplete ticket handoff state')
    strings=('case','checkpoint_id','current_stage','overall_result','summary','authorization')
    strings += ('disposition_receipt_reference','disposition_receipt_sha256','target_scope_reference') if early else ('candidate_revision','base_revision','contract_sha256')
    for key in strings:
        if not isinstance(state[key],str) or not state[key].strip():
            raise ValueError(f'{key} must be a nonempty string, with unknowns explicit')
    if early:
        if state['current_stage']!='assess' or not re.fullmatch('[a-f0-9]{64}',state['disposition_receipt_sha256']):
            raise ValueError('Early disposition requires assessment and a pinned receipt')
        if source_stop and (state.get('lifecycle_disposition')!='deferred' or state.get('closure_permitted') is not False):
            raise ValueError('Source stop must explicitly defer lifecycle disposition and deny closure')
    elif not isinstance(state['contract_version'],int) or isinstance(state['contract_version'],bool) or state['contract_version']<1:
        raise ValueError('Contract version must identify the actual published contract')
    for key in ('stages', 'obligations', 'next_actions', 'open_decisions', 'limitations'):
        if not isinstance(state[key], list):
            raise ValueError(f'{key} must be an array')
    if not re.fullmatch(r'[A-Z][A-Z0-9]*-[1-9][0-9]*', state['case']):
        raise ValueError('Invalid Linear issue identifier')
    if not re.fullmatch(r'[A-Za-z0-9._:-]+', state['checkpoint_id']):
        raise ValueError('Invalid checkpoint identifier')
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    rows = [START, '', f"Checkpoint: `{state['checkpoint_id']}`", f'Checkpoint digest: {fingerprint}', '',
            f"Current stage: {state['current_stage']}", f"Overall result: {state['overall_result']}", '', state['summary'], '']
    if early:
        rows += [f"Early assessment disposition: {state['early_disposition']}",
                 f"Disposition receipt: {state['disposition_receipt_reference']}",
                 f"Disposition SHA-256: {state['disposition_receipt_sha256']}",
                 f"Target scope: {state['target_scope_reference']}",
                 'Repair contract: not applicable to this early disposition.',
                 'Source task complete; lifecycle disposition deferred. No native status transition is authorized.' if source_stop else 'Native lifecycle readback is required before calling the ticket closed.', '']
    else:
        rows += [f"Candidate: {state['candidate_revision']}", f"Integrated base: {state['base_revision']}",
                 f"Contract version: {state['contract_version']}", f"Contract SHA-256: {state['contract_sha256']}", '']
    rows += ['### Stage receipts', '', '| Stage | Recorded result | Subject and evidence |', '| --- | --- | --- |']
    for item in state['stages']:
        rows.append('| ' + ' | '.join(str(item[key]).replace('|', '/') for key in ('stage', 'result', 'evidence')) + ' |')
    for title, key in [('Obligation results', 'obligations'), ('Next actions', 'next_actions'),
                       ('Open decisions', 'open_decisions'), ('Evidence limits', 'limitations')]:
        rows += ['', '### ' + title, '']
        rows += ['- ' + item for item in state[key]] or ['- None recorded.']
    rows += ['', '### Authorized scope', '', state['authorization'], '',
             'The next stage must re-read this ticket and its linked contract/receipts before acting. Local case files and chat history are supporting records; they do not advance the handoff.', '', '']
    rendered = '\n'.join(rows)
    if rendered.count(START) != 1 or END in rendered:
        raise ValueError('Checkpoint text contains reserved boundary markers')
    return rendered


def prepare(issue, state):
    if issue.get('id') != state.get('case'):
        raise ValueError('Ticket/state case mismatch')
    description = issue.get('description') or ''
    old = managed(description)
    predecessor = checkpoint_id(old) if old else None
    if state.get('previous_checkpoint') != predecessor:
        raise ValueError('Stale predecessor; fetch the ticket again and reconcile')
    new = render(state)
    if old:
        if state['checkpoint_id'] == predecessor:
            raise ValueError('A new handoff needs a new checkpoint identifier')
        patch = {'op': 'replace', 'old_string': old, 'new_string': new}
    else:
        resources = state.get('resource_markdown', '')
        patch = {'op': 'prepend', 'text': new + END + '\n\n' + resources + '\n\n## Reported finding and prior history\n\n'}
    return {'schema_version': 1, 'case': issue['id'], 'read_updated_at': issue.get('updatedAt'),
            'read_description_sha256': hashlib.sha256(description.encode()).hexdigest(),
            'predecessor': predecessor, 'checkpoint_id': state['checkpoint_id'],
            'expected_checkpoint': new, 'linear_request': {'id': issue['id'], 'patch': [patch]},
            'note': 'Exact-anchor patch reduces overwrite risk; it is not a server lease or a general atomic compare-and-swap.'}


def acknowledge(issue, prepared):
    if issue.get('id') != prepared.get('case'):
        raise ValueError('Readback is for another issue')
    actual = managed(issue.get('description') or '')
    if actual is None or checkpoint_id(actual) != prepared['checkpoint_id']:
        raise ValueError('Ticket publication not observed; do not advance')
    if normalize(actual) != normalize(prepared['expected_checkpoint']):
        raise ValueError('Readback differs from the published handoff; reconcile before advancing')
    return {'schema_version': 1, 'case': issue['id'], 'checkpoint_id': prepared['checkpoint_id'],
            'ticket_updated_at': issue.get('updatedAt'),
            'ticket_description_sha256': hashlib.sha256(issue['description'].encode()).hexdigest(),
            'publication': 'observed_in_connector_readback',
            'note': 'Confirms this exported connector readback matches the intended checkpoint. Does not prove trusted execution, policy approval or current server state after this read.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare'); a.add_argument('--issue', required=True); a.add_argument('--state', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('ack'); a.add_argument('--issue', required=True); a.add_argument('--prepared', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('attempt-prepare'); a.add_argument('--issue', required=True); a.add_argument('--state', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('attempt-ack'); a.add_argument('--issue', required=True); a.add_argument('--prepared', required=True); a.add_argument('--output', required=True)
    args = p.parse_args()
    output = Path(args.output)
    if output.exists():
        p.error('Use a new output per invocation; do not overwrite a handoff receipt')
    issue = json.loads(Path(args.issue).read_text())
    try:
        if args.command == 'prepare':
            result = prepare(issue, json.loads(Path(args.state).read_text()))
        elif args.command == 'ack':
            result = acknowledge(issue, json.loads(Path(args.prepared).read_text()))
        elif args.command == 'attempt-prepare':
            result = prepare_attempt(issue, json.loads(Path(args.state).read_text()))
        else:
            result = acknowledge_attempt(issue, json.loads(Path(args.prepared).read_text()))
        output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'case': result['case'], 'checkpoint_id': result['checkpoint_id'], 'output': args.output}))
    except ValueError as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
