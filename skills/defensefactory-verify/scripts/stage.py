#!/usr/bin/env python3
"""One explicit stage operation; JSON input/output, no scheduling or lifecycle auto-approval."""
import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
# Source checkout and exported self-contained packages both put factorycore beside this script's parent or script.
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE if (HERE/'factorycore').exists() else HERE.parent))
from factorycore.core import GateError, pack, unpack, job, transition, require, sha, identity
from factorycore.claims import assess, validate_claim, qualify_query
from factorycore.verification import verify, tree_files, architecture_scan
from factorycore.lifecycle import integrate, deployment_event, confirm, maintain, closure, benchmark
from factorycore.release import admit_release,record_rollout,confirm_release,maintain_release
from factorycore.component_claims import catalog_receipt,map_bug_classes,execute_fences,fence_health,compare_definitions,execution_contract
from factorycore.integration_gate import prepare_merge,assess_merge,merge_intent,reconcile_merge
from factorycore.integration import github_subject, merge_tree
from factorycore.maintenance import challenge, maintenance_pass
from factorycore.code_evidence import CodeEvidenceBackend,configured_host_client
from factorycore.assessment import exposure_graph
from factorycore.adapters import invoke_adapter
from factorycore.e2e import guidance_gate,evaluate_e2e
from factorycore.registry import registry_view,validate_lineage
from factorycore.classification import retrieve,adjudicate,model_proposal
from factorycore.claim_approval import propose_contract,approve_contract,verification_handoff,check_handoff
from factorycore.assessment_experiments import freeze_protocol,score
from factorycore.eligibility import evaluate,inspect_component,observe
from factorycore.verification_report import assemble
from factorycore.ledger import validate_checkpoint,reconcile,parse_document,prepare_publication
from factorycore.preflight import preflight,package_inventory,resolve_source,resolve_reference,ticket_snapshot,publication_verify
from factorycore.execution_capture import capture,assertions
from factorycore.handoff_bundle import prepare_bundle,verify_bundle
from factorycore.assessment_resolution import decision_plan,impact_review,session_usage
from factorycore.input_examples import describe
from factorycore.invocation_recovery import recovery_receipt
from factorycore.trial_controls import scope_prepare,stage_start,stage_command,mutation_plan,mutation_result,index_subject
from factorycore.runtime_plan import declare as declare_runtime, outcomes as runtime_outcomes
from factorycore.codeintel_gate import index_observation
from factorycore.source_export import export_sources
from factorycore.rules_contracts import (claim_status as rules_status,evaluate_candidate as rules_evaluate,
    parse_rules,resolve_contracts,rules_change_gate,run_contracts,semantic_diff as rules_diff,semantic_model,transitional_compare)


def run(operation, data):
    def record(name):
        if name+'_file' in data:
            require(name not in data, 'Select a record object OR its file, not both')
            return json.loads(Path(data[name+'_file']).read_text())
        require(isinstance(data.get(name),dict), 'Supply '+name+' as an object or '+name+'_file as its saved JSON path')
        return data[name]
    if operation=='stage-scope':return scope_prepare(data)
    if operation=='stage-start':return stage_start(data['preparation'],data['publication'],data['retrieval'])
    if operation=='stage-command':return stage_command(data['opening'],data['specification'],data['evidence_directory'],data.get('challenge'))
    if operation=='mutation-plan':return mutation_plan(data['plan'])
    if operation=='mutation-result':return mutation_result(record('declaration'),data['variant_id'],record('baseline'),record('mutant'))
    if operation=='runtime-plan':return declare_runtime(record('opening'),data['probes'],data['reference'])
    if operation=='runtime-result':return runtime_outcomes(record('declaration'),record('opening'),[json.loads(Path(p).read_text()) for p in data['execution_files']],lambda p:Path(p).read_bytes())
    if operation=='codeintel-index-observation':return index_observation(data['subject'],data['branch'],data['request_repository'],data['source_file'],data['manifest_pointer'],data.get('fields'),data.get('activation'),data.get('repository_pointer','/body/id'))
    if operation=='source-export':return export_sources(data['repo'],data['revisions'],data['destination'],data.get('timeout_seconds',60))
    if operation=='codeintel-index-subject':return index_subject(data['subject'],data['manifests'],data['branch'],request_repository=data['request_repository'],job_active=data.get('job_active',False),warnings=data.get('warnings'),scip=data.get('scip'))
    if operation=='invocation-recovery':return recovery_receipt(data)
    if operation=='assess-decisions':return decision_plan(data['decisions'],data.get('stage','repair'))
    if operation=='assess-impact':return impact_review(data['assertions'])
    if operation=='session-usage':return session_usage(data['path'],data['session_id'])
    if operation=='evidence-record':
        require(data.get('id') and isinstance(data.get('record'),dict),'Evidence ID and actual record object required')
        return {'id':data['id'],'record':data['record'],'sha256':identity(data['record'])}
    if operation=='stage-preflight':return preflight(data)
    if operation=='skill-inventory':return package_inventory(data['packages'])
    if operation=='source-resolve':return resolve_reference(data['ref'],data['repositories']) if 'repositories' in data else resolve_source(data['repo'],data['ref'],data.get('dependency_paths',[]))
    if operation=='ticket-snapshot':return ticket_snapshot(data['payload'],data['provenance'])
    if operation=='publication-verify':return publication_verify(data['publication'],data['retrieval'],data['expected'],Path(data['downloaded_file']).read_bytes() if data.get('downloaded_file') else None,data.get('bundle_requirements'))
    if operation=='bundle-prepare':return prepare_bundle(data['plan'],data['destination'])
    if operation=='bundle-verify':return verify_bundle(Path(data['downloaded_file']).read_bytes(),data['requirements'])
    if operation=='command-record':
        require(not os.environ.get('DEFENSEFACTORY_STAGE_OPENING'), 'Registered trial: command-record is not an admission fallback. Use stage-exec baseline setup, --comparison from published scope, or a declared challenge variant; preserve the rejection.')
        return capture(data['specification'],data['evidence_directory'])
    if operation=='probe-assert':return assertions(data['subject'],data['check_id'],data['expectations'],data['observations'])
    if operation=='assess-observe':return observe(data['packet'],data['actor'])
    if operation=='assess-eligibility':return evaluate(data.get('packet',{}),data.get('policy'),data.get('actor'))
    if operation=='component-inspect':return inspect_component(data['repo'],data['before'],data['after'],data['path'])
    if operation=='ledger-parse':return parse_document(data['content'])
    if operation=='ledger-prepare':return prepare_publication(data['checkpoint'],data['expected'],{key:Path(path).read_bytes() for key,path in data['resource_files'].items()},data.get('preparation_exit_code',0))
    if operation=='ledger-check':return validate_checkpoint(data['checkpoint'],data['expected'],{key:Path(path).read_bytes() for key,path in data['resource_files'].items()})
    if operation=='ledger-reconcile':return reconcile(data['effect_key'],data['intended'],data['observed'],data.get('lookup_complete',False))
    if operation=='execution-new':return job(data['contract'])
    if operation=='execution-event':return transition(data['state'],data['event'],policy=data['policy'],actor=data['actor'])
    if operation=='codeintel-query':
        backend=CodeEvidenceBackend(configured_host_client(),data['allowed_repositories'])
        return backend.evaluate(data['subject'],data['tool'],data['arguments'],policy_sha256=data['policy_sha256'],extractor=data['extractor'])
    if operation=='exposure-graph':return exposure_graph(data['graph'])
    if operation=='release-admit':return admit_release(data['case'],data['actor'],data['policy'],data['integration'],data['build'],data['units'],data['claim_ids'],data['fence_ids'])
    if operation=='release-rollout':return record_rollout(data['release'],data.get('current',{}),data['event'],data.get('rollback_release'))
    if operation=='release-confirm':return confirm_release(data['release'],data['rollout'],data['observations'],data['now'],data['max_age'])
    if operation=='release-maintain':return maintain_release(data['release'],data['rollout'],data['current'],data['records'],data.get('exceptions',[]),data.get('counterexamples',[]),data['now'],data.get('existing_actions'))
    if operation=='component-claims':
        require(data.get('legacy_migration') is True,'component-claims is legacy schema-2 migration compatibility; canonical components use claim-rules-check/claim-contracts')
        return catalog_receipt(data['repo'],data['repository'],data['revision'],data.get('paths'),data.get('origins'))
    if operation=='claim-rules-check':
        model=parse_rules(Path(data['rules_file']).read_bytes());result={'result':'valid','model':semantic_model(model)}
        if data.get('legacy_file'):result['legacy']=transitional_compare(json.loads(Path(data['legacy_file']).read_text()),model)
        return result
    if operation=='claim-rules-diff':return rules_diff(Path(data['base_file']).read_bytes(),Path(data['candidate_file']).read_bytes())
    if operation=='claim-contracts':return resolve_contracts(data['repo'],data['subject'],data['rules_path'])
    if operation=='claim-contract-run':return run_contracts(data['repo'],data['subject'],data['rules_path'],data['destination'],data.get('contracts'),data.get('trusted_checks'),data.get('contexts'),data.get('max_seconds',300))
    if operation=='claim-candidate-evaluate':return rules_evaluate(data['candidate'],data['disposition'],data['evaluator'],data['evidence'],data['explanation'],data.get('coverage_limitations',[]),data['next_action'],data.get('duplicate_of'))
    if operation=='claim-rules-status':return rules_status(parse_rules(Path(data['rules_file']).read_bytes()),data['run'],data.get('evaluations',[]))
    if operation=='claim-rules-change-gate':return rules_change_gate(data['repo'],data['repository'],data['base'],data['subject'],data['statuses'],data['policy'],data.get('reviews',[]))
    if operation=='bug-class-map':return map_bug_classes(data['receipt'],data['bug_classes'])
    if operation=='fence-execute':return execute_fences(data['repo'],data['receipt'],data['checks'],data['expected_checks_sha256'],data['evaluator_manifest'],data.get('max_seconds',120))
    if operation=='fence-health':return fence_health(data['receipt'],data['execution'])
    if operation=='claim-change-gate':return compare_definitions(data['base'],data['head'],data['health'],data['policy'],data.get('reviews',[]))
    if operation=='component-contract':return execution_contract(data['receipt'],data['claim_id'],data['checks'],data['evaluator_manifest'],data.get('formal'))
    if operation=='claim-registry':return registry_view(data['repo'],data['repository'],data['revision'],data['manifest_path'])
    if operation=='claim-lineage':return validate_lineage(data['child'],data['parent'],data['relation'],data['evidence'])
    if operation=='claim-retrieve':return retrieve(data['finding'],data['registry'],data.get('limit',8))
    if operation=='claim-classify':return adjudicate(data['finding'],data['registry'],data['retrieval'],data['comparisons'])
    if operation=='model-proposal':return model_proposal(data['response'],set(data['allowed_claim_ids']))
    if operation=='contract-propose':return propose_contract(data['registry'],data['claim_id'],data['evaluator'],data['producer'],data['context'],data['actions'],data['budget'])
    if operation=='contract-approve':return approve_contract(data['proposal'],data['envelope'],data['policy'],data['now'])
    if operation=='verification-handoff':return verification_handoff(data['proposal'],data['envelope'],data['policy'],data['now'])
    if operation=='handoff-preservation':return check_handoff(data['expected'],data['received'])
    if operation=='assessment-experiment-freeze':return freeze_protocol(data['cases'],data['arms'],data['thresholds'],data['adjudication'])
    if operation=='assessment-experiment-score':return score(data['cases'],data['runs'],data['protocol'],attestations=data.get('attestations'),trusted_policy=data.get('trusted_policy'),now=data.get('now'))
    if operation=='claim-lint':return {'claim_sha256':validate_claim(data['claim'])}
    if operation=='assess':return assess(data.get('claim'),data.get('finding',{}),data.get('alternatives',[]),data.get('code_evidence',{}),data.get('eligibility'))
    if operation=='qualify-query':return qualify_query(data['result'],data['subject'],data.get('required_files',[]))
    if operation in ('compile','build','deploy','deploy-local','architecture','project-adapter'):
        require(data.get('adapter'), 'Explicit project adapter required; no application or language default is selected')
        return invoke_adapter(data['adapter'],data.get('inputs',{}))
    if operation=='e2e-guidance':return guidance_gate(data.get('guidance'))
    if operation=='e2e-evaluate':return evaluate_e2e(data['candidate'],data['guidance_sha256'],data['required_gates'],data['observations'])
    if operation=='freeze-evaluator':
        require(data.get('paths'), 'Explicit project evaluator paths required')
        files=tree_files(data['repo'],data['revision'])
        require(all(path in files for path in data['paths']), 'Evaluator path missing from selected revision')
        return {path:files[path] for path in data['paths']}
    if operation=='verification-report':return assemble(data['contract'],data['execution'],data['guidance'],data.get('observations',[]),data.get('code_evidence'))
    if operation=='verify':return verify(data['repo'],data['revision'],data['claim'],data['checks'],data['evaluator_manifest'],max_seconds=data.get('max_seconds',300),formal_evidence=data.get('formal_evidence'),implementation_evidence=data.get('implementation_evidence'))
    if operation=='integrate':return integrate(data['subject'],data['verification'],data['policy'],actor=data['actor'],case=data['case'],protection=data['protection'],approved_claim_sha256=data['approved_claim_sha256'],verifier_envelope=data.get('verifier_envelope'))
    if operation=='integration-plan':return prepare_merge(data['repo'],data['repository'],data['base'],data['head'],data.get('method','merge'))
    if operation=='integration-assess':return assess_merge(data['repo'],data['case'],data['actor'],data['policy'],data['plan'],data['verification'],data['observation'],data.get('now'),data.get('verifier_envelope'),data.get('component_gate'))
    if operation=='merge-intent':return merge_intent(data['repo'],data['admission'],data['verification'],data['observation'],data['policy'],data['actor'],data['authorization_reference'],data.get('now'),data.get('verifier_envelope'),data.get('component_gate'))
    if operation=='merge-reconcile':return reconcile_merge(data['repo'],data['intent'],data['observation'],data['policy'],data.get('now'))
    if operation=='github-subject':return github_subject(data['repository'],data['number'])
    if operation=='merge-tree':return merge_tree(data['repo'],data['base'],data['head'])
    if operation=='rollout-event':return deployment_event(data['state'],data['event'])
    if operation=='confirm':return confirm(data['accepted'],data['rollout'],data['observations'],data['required_units'],now=data['now'],max_age=data['max_age'])
    if operation=='closure-request':return closure(data['policy'],actor=data['actor'],case=data['case'],confirmation=data['confirmation'],scope=data['scope'],architectural_open=data.get('architectural_open',[]))
    if operation=='maintain':return maintain(data['current'],data['evidence'],data['exceptions'],data['counterexamples'],now=data['now'])
    if operation=='challenge':return challenge(data['repo'],data['revision'],data['claim'],data['checks'],data['evaluator_manifest'],data['patches'],max_rounds=data.get('max_rounds',4),max_seconds=data.get('max_seconds',300))
    if operation=='maintain-replay':return maintenance_pass(data['current'],data['evidence'],data['exceptions'],data['counterexamples'],now=data['now'],repo=data['repo'],revision=data['revision'],claim=data['claim'],checks=data['checks'],evaluator_manifest=data['evaluator_manifest'],max_seconds=data.get('max_seconds',300))
    if operation=='benchmark':return benchmark(data['runs'],data['protocol'])
    if operation=='pack':return pack({name:Path(path).read_bytes() for name,path in data['files'].items()})
    if operation=='unpack':return {'restored':list(unpack(data['bundle'],data['destination']))}
    raise GateError('Unknown stage operation')


def main():
    p=argparse.ArgumentParser(description=__doc__,epilog='Use --describe OPERATION for a short input example. See bundled references/experiment-preflight.md for authority boundaries.');p.add_argument('operation',nargs='?');p.add_argument('--describe',metavar='OPERATION');p.add_argument('--input');p.add_argument('--output');a=p.parse_args()
    if a.describe:
        if a.operation or a.input or a.output:p.error('--describe does not execute a stage or accept input/output')
        try:print(json.dumps(describe(a.describe),indent=2))
        except GateError as e:p.error(str(e))
        return 0
    if not (a.operation and a.input and a.output):p.error('operation, --input and --output required for execution')
    out=Path(a.output)
    if out.exists():p.error('Use a new output per invocation; do not overwrite a receipt')
    roots=[Path(os.environ[k]).resolve() for k in ('DEFENSEFACTORY_EVIDENCE_ROOT','DEFENSEFACTORY_HANDOFF_ROOT','DEFENSEFACTORY_PUBLICATION_ROOT') if os.environ.get(k)]
    if roots and not any(r in out.resolve().parents for r in roots):p.error('Save stage metadata in a registered evidence/handoff/publication root')
    try:
        data=json.loads(Path(a.input).read_text());require(isinstance(data,dict),'Stage input must be a JSON object')
        if a.operation=='bundle-prepare':require(Path(data['destination']).resolve()!=out.resolve(),'Bundle destination and JSON receipt must be different files')
        result=run(a.operation,data)
    except (GateError,OSError,KeyError,ValueError,TypeError,subprocess.CalledProcessError) as e:result={'result':'inconclusive','error':str(e),'operation':a.operation,'input_help':'stage.py --describe '+a.operation}
    out.parent.mkdir(parents=True,exist_ok=True)
    try:
        with out.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    except FileExistsError:p.error('Output appeared during execution; preserve it and use a new receipt path')
    print(json.dumps({'operation':a.operation,'output':str(out),'result':result.get('result','recorded')}))
    return 1 if result.get('result') in ('violated','inconclusive','unsupported','failed') else 0


if __name__=='__main__':sys.exit(main())
