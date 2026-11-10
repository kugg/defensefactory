"""Separate bounded source outcomes, blocking decisions and impact evidence."""
import copy
import json
from .core import require, identity

STAGES = {'assessment', 'repair', 'verification', 'integration', 'deployment', 'closure'}


def decision_plan(decisions, stage='repair'):
    """Classify explicit prerequisites; never resolve policy choices or grant authority."""
    require(stage in STAGES, 'Unknown blocked stage')
    require(isinstance(decisions, list), 'Decisions must be an array')
    ids = [d['id'] for d in decisions]
    require(len(ids) == len(set(ids)), 'Duplicate decision identity')
    blocking, deferred, resolved, questions, incomplete = [], [], [], [], []
    for original in decisions:
        d = copy.deepcopy(original)
        state = d.get('state')
        require(state in ('unresolved', 'resolved'), 'Decision state must be unresolved/resolved')
        blocks = d.get('blocks_stages', ['repair'])
        require(isinstance(blocks, list) and blocks and set(blocks) <= STAGES, 'Explicit nonempty blocked stages required')
        d['blocks_stages'] = blocks
        if state == 'resolved':
            # The plan is not an authority check: retain the actual decision resource.
            require(d.get('decision_reference'), 'Resolved decision needs its actual decision reference')
            resolved.append(d)
        elif stage not in blocks:
            deferred.append(d)
        else:
            blocking.append(d)
            options = d.get('alternatives', [])
            if not (d.get('owner') and d.get('question') and d.get('reference') and
                    len(options) >= 2 and all(o.get('choice') and o.get('consequence') for o in options)):
                incomplete.append(d['id'])
            questions.append({'id': d['id'], 'owner': d.get('owner'), 'question': d.get('question'),
                              'alternatives': options, 'reference': d.get('reference')})
    return {'result': 'inconclusive' if incomplete else 'recorded', 'stage': stage,
            'blocked': bool(blocking), 'blocking_decisions': blocking,
            'deferred_decisions': deferred, 'resolved_decisions': resolved,
            'questions': questions, 'incomplete_decision_briefs': incomplete,
            'repair_permitted': False, 'closure_permitted': False,
            'limitation': 'Explicit prerequisite routing, not a decision, authority attestation or proof that the stated blocker is necessary.'}


def impact_review(assertions):
    """Check claim/evidence correspondence; text and causal adequacy still need review."""
    require(isinstance(assertions, list) and assertions, 'Impact assertions required')
    ids = [a['id'] for a in assertions]
    require(len(ids) == len(set(ids)), 'Duplicate impact assertion')
    by_id = {a['id']: a for a in assertions}
    problems = []
    confirmed = {'source_supported', 'observed'}
    states = confirmed | {'reporter_only', 'conditional', 'unsupported', 'unresolved'}
    for a in assertions:
        require(a.get('statement') and a.get('effect') and a.get('assessment') in states,
                'Impact assertion needs statement, effect and assessment')
        require(a.get('report_reference'), 'Preserve the originating reporter assertion/reference')
        deps = a.get('depends_on', [])
        require(isinstance(deps, list) and all(d in by_id and d != a['id'] for d in deps), 'Unknown/self impact prerequisite')
        if a['assessment'] in confirmed:
            support = a.get('evidence', [])
            if not any(e.get('reference') and e.get('assertion_id') == a['id'] and
                       e.get('effect') == a['effect'] and
                       e.get('basis') in ({'execution'} if a['assessment'] == 'observed' else {'source', 'execution'}) for e in support):
                problems.append({'id': a['id'], 'problem': 'No direct same-effect support; reporter text and a different demonstrated effect cannot establish this conclusion'})
            if any(by_id[d]['assessment'] not in confirmed for d in deps):
                problems.append({'id': a['id'], 'problem': 'Confirmed conclusion depends on an unconfirmed premise'})
        elif not a.get('rationale'):
            problems.append({'id': a['id'], 'problem': 'Explain the uncertainty, rejection or conditional assumption'})
    # Cycles cannot be used as mutually supporting causal evidence.
    visited, active = set(), set()
    def visit(key):
        require(key not in active, 'Cyclic impact prerequisites')
        if key in visited:
            return
        active.add(key)
        for dep in by_id[key].get('depends_on', []):
            visit(dep)
        active.remove(key)
        visited.add(key)
    for key in ids:
        visit(key)
    return {'result': 'inconclusive' if problems else 'recorded', 'problems': problems,
            'assertions': copy.deepcopy(assertions), 'assertions_sha256': identity(assertions),
            'closure_permitted': False,
            'limitation': 'Checks labeled correspondence only. A reviewer must judge whether cited source/execution actually establishes the stated effect; hashes and labels do not prove causation.'}


def session_usage(path, session_id):
    """Read captured OpenCode JSONL, counting unique provider-reported finish parts."""
    require(session_id, 'Explicit session identity required')
    seen, sessions, reported, errors = set(), set(), [], []
    totals = {'input': 0, 'output': 0, 'reasoning': 0, 'cache_read': 0, 'cache_write': 0}
    with open(path) as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
            except ValueError:
                errors.append({'line': number, 'problem': 'Non-JSON line retained; usage may be incomplete'})
                continue
            if not isinstance(event, dict):
                errors.append({'line': number, 'problem': 'Non-object event'})
                continue
            if event.get('sessionID'):
                sessions.add(event['sessionID'])
            if event.get('sessionID') != session_id or event.get('type') != 'step_finish':
                continue
            part = event.get('part', {})
            if not part.get('id'):
                errors.append({'line': number, 'problem': 'Finish event without stable identity'})
                continue
            if part['id'] in seen:
                continue
            seen.add(part['id'])
            tokens = part.get('tokens')
            if not isinstance(tokens, dict):
                errors.append({'line': number, 'problem': 'Missing provider token counters'})
                continue
            values = {k: tokens.get(k) for k in ('input', 'output', 'reasoning')}
            values.update({k: tokens.get('cache', {}).get(k.split('_')[1]) for k in ('cache_read', 'cache_write')})
            if not all(type(v) is int and v >= 0 for v in values.values()):
                errors.append({'line': number, 'problem': 'Missing/invalid provider token counters'})
                continue
            for key, value in values.items():
                totals[key] += value
            if type(part.get('cost')) in (int, float):
                reported.append(part['cost'])
    return {'result': 'recorded' if seen and not errors else 'inconclusive', 'session_id': session_id,
            'observed_sessions': sorted(sessions), 'finish_events': len(seen),
            'provider_reported_tokens': totals if seen else None,
            'provider_reported_cost_values': reported, 'billing_cost': 'not_verified',
            'diagnostics': errors,
            'limitation': 'Captured provider counters, not verified billing. Reasoning/output/cache counters may overlap; do not add them into an invented charged-token total. A reported zero cost is not proof of free execution.'}
