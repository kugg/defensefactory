"""Small input examples for the operations that caused repeated trial retries."""
import copy
from .core import require


EXAMPLES = {
    'stage-scope': {'case':'REPLACE_TICKET','attempt':'REPLACE_NEW_ATTEMPT','stage':'verify',
        'subject':{'repository':'REPLACE_REPOSITORY','revision':'REPLACE_FULL_COMMIT'},
        'performed_by':'REPLACE_ACTUAL_ACTOR','package':'/REPLACE/ACTUALLY/LOADED/defensefactory-verify',
        'authorization_reference':'REPLACE_INVOCATION_REFERENCE','boundaries':'REPLACE_BOUNDED_SCOPE'},
    'stage-start': {'preparation':'REPLACE_STAGE_SCOPE_RECEIPT_OBJECT',
        'publication':{'id':'REPLACE_COMMENT_ID','body':'REPLACE_SCOPE_BODY_FROM_PREPARATION','createdAt':'REPLACE_CONNECTOR_TIME'},
        'retrieval':{'id':'REPLACE_SAME_COMMENT_ID','body':'REPLACE_FRESHLY_RETRIEVED_BODY','createdAt':'REPLACE_CONNECTOR_TIME','operation':'retrieval','retrieved_at':'REPLACE_ACTUAL_READBACK_TIME'}},
    'stage-command': {'opening':'REPLACE_STAGE_START_RECEIPT_OBJECT','specification':{
        'id':'REPLACE_CHECK','subject':{'revision':'REPLACE_FULL_COMMIT'},'performed_by':'REPLACE_ACTOR',
        'argv':['REPLACE_EXECUTABLE','REPLACE_ARGUMENT'],'cwd':'/REPLACE/CANONICAL/WORKSPACE',
        'timeout_seconds':120,'evaluator_files':{},'execution':{'format':'REPLACE_PROTOCOL','required_tests':['REPLACE_TEST']},
        'stage_start_reference':'/REPLACE/SAVED/STAGE-START.json','stage_start_sha256':'REPLACE_CANONICAL_RECEIPT_IDENTITY'},
        'evidence_directory':'/REPLACE/NEW/EVIDENCE/DIRECTORY'},
    'mutation-plan': {'plan': {'baseline_subject':{'repository':'REPLACE_REPOSITORY','revision':'REPLACE_FULL_COMMIT'},
        'argv':['REPLACE_DIRECT_TEST_EXECUTABLE'],'execution':{'format':'go-test-json','required_tests':['REPLACE_PACKAGE::TestNegative','REPLACE_PACKAGE::TestPositive']},
        'evaluators':{'relative/evaluator_test.go':'REPLACE_SHA256'},'controls':['relative/control.go'],
        'variants':[{'id':'deny-all','kind':'legitimate_behavior','subject':{'revision':'REPLACE_MUTANT_COMMIT'},'expected_failures':['REPLACE_PACKAGE::TestPositive']}]}},
    'mutation-result': {'declaration':'REPLACE_PREEXECUTION_MUTATION_PLAN_RECEIPT','variant_id':'deny-all',
        'baseline':'REPLACE_ACTUAL_CAPTURE_RECEIPT_OBJECT','mutant':'REPLACE_ACTUAL_CAPTURE_RECEIPT_OBJECT'},
    'codeintel-index-subject': {'subject':{'repository':'REPLACE_REPOSITORY','revision':'REPLACE_FULL_COMMIT'},
        'request_repository':'REPLACE_ACTUAL_STATUS_REQUEST_REPOSITORY','branch':'refs/heads/REPLACE_SELECTED_BRANCH',
        'manifests':[{'branch':'refs/heads/REPLACE_SELECTED_BRANCH','commitHash':'REPLACE_ACTUAL_FULL_COMMIT','active':True}],
        'job_active':False,'warnings':[],'scip':{'occurrences':'REPLACE_ACTUAL_COUNT'}},
    'stage-preflight': {'case':'REPLACE_TICKET','performed_by':'REPLACE_ACTUAL_ACTOR',
        'protocol_reference':'REPLACE_FROZEN_PROTOCOL','scope_authorization_reference':'REPLACE_ACTUAL_INVOCATION',
        'tool_inventory_reference':'REPLACE_CURRENT_TOOL_INVENTORY','exposed_tools':[],
        'targets':[{'id':'trial','role':'trial_target','subject':{'revision':'REPLACE_FULL_GIT_COMMIT'}}]},
    'skill-inventory': {'packages':{'defensefactory':'/REPLACE/ACTUALLY/CONSUMED/PACKAGE'}},
    'source-resolve': {'ref':'REPLACE_REPORTED_REF','repositories':[
        {'id':'origin','repo':'/REPLACE/DECLARED/ORIGIN','reference':'REPLACE_TICKET_SOURCE_MAPPING'}]},
    'component-inspect': {'repo':'/REPLACE/DECLARED/REPO','before':'REPLACE_FULL_REPORTED_COMMIT',
        'after':'REPLACE_FULL_TRIAL_COMMIT','path':'REPLACE_ORIGINAL_RELATIVE_PATH'},
    'bundle-verify': {'downloaded_file':'/REPLACE/ACTUALLY/DOWNLOADED/bundle.tar.gz',
        'requirements':'REPLACE_WITH_TICKET_BOUND_EXTERNAL_REQUIREMENTS_OBJECT'},
    'invocation-recovery': {'case':'REPLACE_TICKET','attempt':'REPLACE_EXISTING_ATTEMPT','session_id':'REPLACE_EXISTING_SESSION','log_path':'/REPLACE/CAPTURED/INVOCATION.jsonl','exit_code':1,'retries_used':0,'retry_budget':2},
    'evidence-record': {'id': 'source-observation', 'record': {
        'kind': 'applicability_observation', 'target': 'trial',
        'subject': {'revision': 'REPLACE_FULL_GIT_COMMIT'},
        'performed_by': 'REPLACE_ACTUAL_ACTOR', 'reason': 'active',
        'rationale': 'REPLACE_ANALYSIS', 'source_reference': 'REPLACE_SOURCE_RECEIPT'}},
    'assess-observe': {'packet': {'case': 'REPLACE_TICKET', 'targets': [], 'evidence': []},
                       'actor': 'REPLACE_ACTUAL_ACTOR'},
    'assess-eligibility': {'packet': {'case': 'REPLACE_TICKET', 'targets': [], 'evidence': []},
                           'policy': {'actors': {}, 'assessment_scopes': {}}, 'actor': 'REPLACE_ACTUAL_ACTOR'},
    'assess-decisions': {'stage': 'repair', 'decisions': [{
        'id': 'behavior-choice', 'state': 'unresolved', 'blocks_stages': ['repair'],
        'owner': 'REPLACE_COMPONENT_OWNER', 'reference': 'REPLACE_REQUIREMENT_REFERENCE',
        'question': 'REPLACE_THE_SPECIFIC_BEHAVIOR_CHOICE',
        'alternatives': [{'choice': 'REPLACE_OPTION_A', 'consequence': 'REPLACE_CONSEQUENCE_A'},
                         {'choice': 'REPLACE_OPTION_B', 'consequence': 'REPLACE_CONSEQUENCE_B'}]}]},
    'command-record': {'specification': {'id': 'REPLACE_CHECK_ID',
        'subject': {'revision': 'REPLACE_FULL_GIT_COMMIT'}, 'performed_by': 'REPLACE_ACTUAL_ACTOR',
        'argv': ['REPLACE_EXECUTABLE', 'REPLACE_ARGUMENT'], 'cwd': '/REPLACE/ABSOLUTE/WORKSPACE',
        'timeout_seconds': 120, 'environment': {}, 'evaluator_files': {},
        'execution': {'format': 'REPLACE_PROJECT_OUTPUT_PROTOCOL', 'required_tests': ['REPLACE_NAMED_TEST']}},
        'evidence_directory': '/REPLACE/NEW/EVIDENCE/DIRECTORY'},
    'bundle-prepare': {'plan': {'case': 'REPLACE_TICKET', 'attempt': 'REPLACE_ATTEMPT',
        'subject': {'revision': 'REPLACE_FULL_GIT_COMMIT'}, 'resources': [
            {'id': 'execution', 'kind': 'execution_receipt', 'path': '/REPLACE/CAPTURED/execution.json'}]},
        'destination': '/REPLACE/NEW/bundle.tar.gz'},
    'publication-verify': {'publication': {'resource_id': 'REPLACE_NATIVE_RESOURCE_ID',
        'acknowledged_at': 'REPLACE_ACTUAL_ACKNOWLEDGEMENT_TIME'},
        'retrieval': {'operation': 'retrieval', 'resource_id': 'REPLACE_NATIVE_RESOURCE_ID',
                      'retrieved_at': 'REPLACE_ACTUAL_LATER_RETRIEVAL_TIME'},
        'expected': {'sha256': 'REPLACE_ARCHIVE_SHA256', 'bytes': 0},
        'downloaded_file': '/REPLACE/ACTUALLY/DOWNLOADED/FILE',
        'bundle_requirements': 'REPLACE_WITH_EXTERNAL_REQUIREMENTS_OBJECT'},
    'session-usage': {'path': '/REPLACE/CAPTURED/OpenCode.jsonl', 'session_id': 'REPLACE_SESSION_ID'},
    'assess-impact': {'assertions': [{'id': 'effect', 'statement': 'REPLACE_ASSESSED_EFFECT',
        'effect': 'availability', 'assessment': 'reporter_only',
        'report_reference': 'REPLACE_ORIGINAL_REPORT_REFERENCE',
        'rationale': 'REPLACE_WHAT_IS_AND_IS_NOT_ESTABLISHED'}]},
}


def describe(operation):
    require(operation in EXAMPLES, 'No short example for this operation; consult its bundled reference')
    return {'operation': operation, 'input_example': copy.deepcopy(EXAMPLES[operation]),
            'usage': 'stage.py OPERATION --input actual-input.json --output NEW-receipt.json',
            'note': 'Shape example only. Replace placeholders with recovered facts. Policy must come from the actual invoker, not from filling this template. Use evidence-record to compute canonical record hashes; keep the original record bytes. command-record must freeze actual evaluator_files and the project execution protocol.'}
