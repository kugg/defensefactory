"""Separate bounded source outcomes, blocking decisions and impact evidence."""
import copy
import datetime
import json
from .core import require, identity

STAGES = {'assessment', 'repair', 'verification', 'integration', 'deployment', 'closure'}
TICKET_SURFACES = {'description', 'status', 'comments', 'documents', 'attachments', 'relations'}
AUTHORITY_EFFECTS = {'resolves', 'constrains', 'authorizes', 'context_only'}


def _timestamp(value, label):
    require(isinstance(value, str) and value, label + ' timestamp required')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(label + ' timestamp must be ISO-8601')
    require(parsed.tzinfo is not None, label + ' timestamp requires a timezone')
    return parsed


def _authority_review(review):
    """Validate a current, complete ticket review and normalize decision records."""
    require(isinstance(review, dict), 'Current ticket authority review required before routing decisions')
    require(review.get('ticket') and review.get('snapshot_reference'),
            'Authority review needs ticket and persisted snapshot reference')
    updated = _timestamp(review.get('ticket_updated_at'), 'Ticket update')
    retrieved = _timestamp(review.get('retrieved_at'), 'Ticket retrieval')
    require(retrieved >= updated, 'Authority review predates the ticket snapshot')
    surfaces = review.get('surfaces')
    require(isinstance(surfaces, list), 'Authority review needs ticket surface records')
    kinds = [surface.get('kind') for surface in surfaces]
    require(set(kinds) == TICKET_SURFACES and len(kinds) == len(TICKET_SURFACES),
            'Review description, status, comments, documents, attachments and relations exactly once')
    for surface in surfaces:
        require(surface.get('state') in ('reviewed', 'empty'),
                'Ticket surfaces must be completely reviewed or confirmed empty')
        require(surface.get('reference'), 'Each ticket surface needs a persisted retrieval reference')

    records = review.get('authority_records', [])
    require(isinstance(records, list), 'Authority records must be an array')
    seen = set()
    for record in records:
        require(record.get('id') and record['id'] not in seen, 'Authority record identities must be unique')
        seen.add(record['id'])
        require(record.get('decision_id') and record.get('effect') in AUTHORITY_EFFECTS,
                'Authority record needs decision_id and a recognized effect')
        require(record.get('reference') and record.get('owner') and record.get('directive'),
                'Authority record needs reference, owner and retained directive')
        _timestamp(record.get('recorded_at'), 'Authority record')
        require(isinstance(record.get('supersedes', []), list), 'Authority supersedes must be an array')
    for record in records:
        replaced = record.get('supersedes', [])
        require(record['id'] not in replaced and set(replaced) <= seen,
                'Authority supersession must name other reviewed record identities')
    normalized = copy.deepcopy(review)
    normalized['authority_records'] = records
    return normalized


def decision_plan(decisions, stage='repair', authority_review=None):
    """Classify explicit prerequisites; never resolve policy choices or grant authority."""
    require(stage in STAGES, 'Unknown blocked stage')
    require(isinstance(decisions, list), 'Decisions must be an array')
    review = _authority_review(authority_review)
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
        records = [record for record in review['authority_records'] if record['decision_id'] == d['id']]
        superseded = {old for record in records for old in record.get('supersedes', [])}
        records = [record for record in records if record['id'] not in superseded]
        resolutions = [record for record in records if record['effect'] == 'resolves']
        require(len(resolutions) <= 1, 'Conflicting owner resolutions require explicit supersession')
        constraints = [record['reference'] for record in records if record['effect'] == 'constrains']
        applied = d.get('applied_authority_references', [])
        require(isinstance(applied, list), 'Applied authority references must be an array')
        require(set(constraints) <= set(applied), 'Decision omitted a current owner constraint')
        if state == 'resolved':
            # The plan is not an authority check: retain the actual decision resource.
            require(d.get('decision_reference'), 'Resolved decision needs its actual decision reference')
            require(any(record['reference'] == d['decision_reference'] for record in resolutions),
                    'Resolved decision must bind a reviewed owner resolution from the current ticket')
            require(d.get('choice'), 'Resolved decision must retain the chosen requirement or direction')
            resolved.append(d)
        else:
            require(not resolutions, 'A reviewed owner decision already resolves this question; do not reopen it')
            require(d.get('authority_review') == 'no_applicable_resolution' and d.get('authority_rationale'),
                    'Unresolved decision must explain why the complete ticket review contains no applicable resolution')
        if state == 'unresolved' and stage not in blocks:
            deferred.append(d)
        elif state == 'unresolved':
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
            'authority_review': review, 'authority_review_sha256': identity(review),
            'repair_permitted': False, 'closure_permitted': False,
            'limitation': 'Complete ticket decision reconciliation and explicit prerequisite routing; not semantic proof, authority attestation or proof that the stated blocker is necessary.'}


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
