"""Deterministic execution reducer. Persist returned state/receipts in Linear, not a local DB."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time


class GateError(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return sha(canonical(value))


def require(condition, message):
    if not condition:
        raise GateError(message)


def pack(files):
    """Portable evidence bytes. Digests prove integrity, not authorship or authority."""
    return {'schema_version': 1, 'objects': {name: {'sha256': sha(data), 'size': len(data),
            'encoding': 'base64', 'data': base64.b64encode(data).decode()}
            for name, data in sorted(files.items())}}


def unpack(bundle, destination=None):
    require(bundle.get('schema_version') == 1, 'Unsupported evidence schema')
    result = {}
    for name, obj in bundle['objects'].items():
        parts = PurePosixPath(name)
        require(not parts.is_absolute() and '..' not in parts.parts and '\\' not in name and name not in ('', '.'), 'Unsafe resource path')
        data = base64.b64decode(obj['data'], validate=True)
        require(len(data) == obj['size'] and sha(data) == obj['sha256'], 'Resource integrity mismatch')
        result[name] = data
    if destination is not None:
        root = Path(destination).resolve()
        # Reject existing links before writing any object.
        for name in result:
            p = root / name
            require(root in p.resolve().parents, 'Resource escapes destination')
            require(not any(x.is_symlink() for x in [p, *p.parents] if x != root.parent), 'Symlink in destination')
        for name, data in result.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as stream:
                stream.write(data)
    return result


ROLES = {'intake': {'intake'}, 'assess': {'assess', 'dispute', 'close', 'disqualify'}, 'repair': {'repair'},
         'verify': {'verify'}, 'integrate': {'evaluate_merge', 'merge'},
         'deploy': {'build', 'deploy', 'rollback'}, 'confirm': {'confirm', 'request_closure'},
         'maintain': {'maintain', 'request_reassessment'}}
TERMINAL = {'completed', 'failed', 'cancelled', 'budget_exhausted'}


def authorize(policy, actor, operation, resource):
    """Policy must be provided by the trusted invoker, never extracted from ticket prose."""
    grant = policy.get('actors', {}).get(actor)
    require(grant is not None, 'Unknown execution identity')
    require(operation in grant.get('operations', []) and operation in ROLES.get(grant['role'], set()), 'Operation not granted to role')
    require(resource in grant.get('resources', []), 'Resource outside authority')
    return grant


def job(contract):
    require(contract.get('schema_version') == 1, 'Unsupported job schema')
    for key in ('case', 'job_id', 'stage', 'subject', 'obligations', 'policy_sha256', 'budget'):
        require(contract.get(key), 'Missing job field: ' + key)
    require(contract['stage'] in ROLES, 'Unknown stage')
    budget = contract['budget']
    require(budget['attempts'] >= 1 and budget['calls'] >= 0 and budget['deadline'] > 0, 'Invalid budget')
    return {'schema_version': 1, 'contract': copy.deepcopy(contract), 'contract_sha256': identity(contract),
            'generation': 0, 'state': 'waiting', 'attempts': 0, 'calls': 0,
            'events': [], 'outbox': [], 'effects': {}, 'children': []}


def transition(current, event, *, policy, actor, now=None):
    """Return a new state. Checkpoint CAS/publication remains the Linear connector's job."""
    now = time.time() if now is None else now
    state = copy.deepcopy(current)
    require(identity(state['contract']) == state['contract_sha256'], 'Contract was amended outside approval')
    require(identity(policy) == state['contract']['policy_sha256'], 'Execution policy changed')
    authorize(policy, actor, state['contract']['stage'] if state['contract']['stage'] not in ('integrate', 'deploy', 'confirm') else {'integrate':'evaluate_merge','deploy':'build','confirm':'confirm'}[state['contract']['stage']], state['contract']['case'])
    require(event.get('id'), 'Event identity required')
    if any(e['id'] == event['id'] for e in state['events']):
        previous = next(e for e in state['events'] if e['id'] == event['id'])
        require(previous['digest'] == identity(event), 'Event id reused with different content')
        return state
    kind = event['kind']
    require(state['state'] not in TERMINAL or kind == 'ack_delivery', 'Terminal job cannot advance')
    budget = state['contract']['budget']
    if kind not in ('cancel', 'ack_delivery') and now >= budget['deadline']:
        state['state'] = 'budget_exhausted'
        state['children'] = [{**c, 'state': 'cancelled'} for c in state['children']]
    elif kind == 'ready':
        require(state['state'] == 'waiting' and event.get('preconditions_satisfied'), 'Job prerequisites unmet')
        state['state'] = 'runnable'
    elif kind == 'lease':
        require(state['state'] == 'runnable' or (state['state'] in ('leased', 'executing') and now >= state['lease']['until']), 'Active lease cannot be replaced')
        if state['attempts'] >= budget['attempts']:
            state['state'] = 'budget_exhausted'
        else:
            require(event['seconds'] > 0, 'Lease duration must be positive')
            state['generation'] += 1
            state['attempts'] += 1
            state['lease'] = {'actor': actor, 'until': min(now + event['seconds'], budget['deadline'])}
            state['state'] = 'leased'
    elif kind in ('start', 'call', 'finish', 'child'):
        require(event.get('generation') == state['generation'] and state['lease']['actor'] == actor and now < state['lease']['until'], 'Expired or fenced worker')
        if kind == 'start':
            require(state['state'] == 'leased', 'Job is not leased')
            state['state'] = 'executing'
        else:
            require(state['state'] == 'executing', 'Job is not executing')
            if kind == 'call':
                if state['calls'] >= budget['calls']:
                    state['state'] = 'budget_exhausted'
                    state['children'] = [{**c, 'state': 'cancelled'} for c in state['children']]
                else:
                    state['calls'] += 1
            elif kind == 'child':
                # Reservations consume the parent's remaining budget, including unused allocations.
                remaining = budget['calls'] - state['calls']
                require(0 <= event['calls'] <= remaining and event['deadline'] <= budget['deadline'], 'Child expands parent budget')
                require(set(event['operations']) <= set(policy['actors'][actor]['operations']), 'Child expands authority')
                state['calls'] += event['calls']
                state['children'].append({'id': event['child_id'], 'state':'waiting', 'calls':event['calls'], 'deadline':event['deadline']})
            elif kind == 'finish':
                require(event['subject'] == state['contract']['subject'], 'Result subject changed')
                require(set(event['obligations']) == set(state['contract']['obligations']), 'Result drops or adds obligations')
                require(event.get('evidence'), 'Result evidence missing')
                require(event['result'] in ('satisfied_within_scope','violated','inconclusive','unsupported','premise_disputed','failed'), 'Invalid evaluation result')
                state['state'] = 'failed' if event['result'] == 'failed' else 'completed'
                state['result'] = copy.deepcopy(event)
                # Output + pending event are part of ONE ticket checkpoint, before delivery.
                state['outbox'].append({'id': event['id'] + ':handoff', 'kind':'reassess' if event['result']=='premise_disputed' else 'stage_receipt', 'payload_sha256':identity(event), 'delivered':False})
    elif kind == 'cancel':
        state['state'] = 'cancelled'
        state['children'] = [{**c, 'state':'cancelled'} for c in state['children']]
    elif kind == 'ack_delivery':
        found = next((x for x in state['outbox'] if x['id'] == event['delivery_id']), None)
        require(found is not None, 'Unknown pending delivery')
        found['delivered'] = True
    else:
        raise GateError('Unknown execution event')
    state['events'].append({'id': event['id'], 'digest': identity(event), 'at':now})
    return state


def reconcile_effect(state, key, desired, observed):
    """After timeout, observe remote identity before considering a retry."""
    desired_sha = identity(desired)
    prior = state.get('effects', {}).get(key)
    require(prior is None or prior['desired_sha256'] == desired_sha, 'Effect key reused')
    if observed is None:
        return {'key':key, 'desired_sha256':desired_sha, 'state':'unknown', 'next':'reconcile_remote_before_retry'}
    require(observed['identity'] == desired['identity'], 'Remote effect identity mismatch')
    return {'key':key, 'desired_sha256':desired_sha, 'state':'observed', 'remote':observed}
