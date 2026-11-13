"""Component RULES.md is an exact, developer-facing claim representation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/defensefactory/scripts'
sys.path.insert(0,str(SCRIPTS))
from factorycore.component_claims import catalog_receipt,compare_definitions,render_rules,validate_rules
from factorycore.core import GateError,identity


class ClaimRulesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.repo=Path(temporary.name)/'repo';self.repo.mkdir();self.component=self.repo/'service';self.component.mkdir()
        self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
        (self.component/'boundary_test.go').write_text('package service\nfunc TestAuthenticatedBoundary() {}\n')
        intro=self.commit('Introduce deterministic boundary control')
        self.catalog={'schema_version':2,'component':'fixture-service',
            'bug_classes':[{'id':'unauthenticated-peer','definition':'A privileged boundary accepts an unauthenticated peer.'}],
            'claims':[{'id':'AUTHENTICATED-BOUNDARY','statement':'Only an authenticated peer crosses the privileged boundary.',
                       'preserves':['Authenticated clients continue to cross the boundary.'],
                       'bug_classes':['unauthenticated-peer'],'fences':['boundary-test']}],
            'fences':[{'id':'boundary-test','kind':'hard','mechanism':'test','check':'boundary-check',
                       'controls':[{'path':'boundary_test.go','selector':'TestAuthenticatedBoundary',
                                    'introduced':{'repository':'fixture/repo','ref':intro,'path':'service/boundary_test.go'}}]}]}

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.PIPE).decode().strip()

    def commit(self,message):
        self.git('add','-A');self.git('commit','-qm',message);return self.git('rev-parse','HEAD')

    def write_catalog(self,catalog=None):
        (self.component/'claims.json').write_text(json.dumps(catalog or self.catalog,indent=2)+'\n')

    def health(self,receipt):
        value={'subject':receipt['subject'],'registry_sha256':receipt['registry_sha256'],
               'execution_sha256':'synthetic','claims':[],'result':'satisfied_within_scope',
               'coverage':'Synthetic admission fixture'}
        value['health_sha256']=identity(value);return value

    def test_rendered_rules_describe_shape_and_match_exact_definition(self):
        raw=render_rules(self.catalog)
        self.assertIn('## Exact claim shape',raw)
        self.assertEqual(validate_rules(raw,self.catalog),self.catalog)
        self.assertNotIn('sha256',raw.lower())

    def test_packaged_authoring_templates_have_the_same_definition_shape(self):
        references=ROOT/'skills/defensefactory/references'
        catalog=json.loads((references/'component-claims.json').read_text())
        rules=(references/'component-RULES.md').read_text()
        block=rules.split('<!-- defensefactory-claims:start -->',1)[1].split('<!-- defensefactory-claims:end -->',1)[0]
        mirrored=json.loads(block.split('```json',1)[1].rsplit('```',1)[0])
        self.assertEqual(mirrored,catalog)

    def test_receipt_binds_both_component_files(self):
        self.write_catalog();(self.component/'RULES.md').write_text(render_rules(self.catalog));revision=self.commit('Add component claim')
        receipt=catalog_receipt(self.repo,'fixture/repo',revision)
        rules=receipt['catalogs'][0]['rules']
        self.assertEqual(rules['state'],'synchronized')
        self.assertEqual(rules['path'],'service/RULES.md')
        self.assertEqual(rules['definition'],self.catalog)

    def test_changed_legacy_claim_is_blocked_until_rules_lands(self):
        self.write_catalog();base_revision=self.commit('Legacy claim');base=catalog_receipt(self.repo,'fixture/repo',base_revision)
        self.assertEqual(base['catalogs'][0]['rules']['state'],'missing_legacy')
        amended=copy.deepcopy(self.catalog);amended['claims'][0]['statement']='Only a verified authenticated peer crosses the privileged boundary.'
        self.write_catalog(amended);legacy_revision=self.commit('Amend without developer rules');legacy=catalog_receipt(self.repo,'fixture/repo',legacy_revision)
        blocked=compare_definitions(base,legacy,self.health(legacy),{'definition_review_required':False},[])
        self.assertTrue(blocked['pr_blocked']);self.assertIn('fixture-service',blocked['missing_rules'])
        (self.component/'RULES.md').write_text(render_rules(amended));rules_revision=self.commit('Add exact developer rules')
        synchronized=catalog_receipt(self.repo,'fixture/repo',rules_revision)
        admitted=compare_definitions(base,synchronized,self.health(synchronized),{'definition_review_required':False},[])
        self.assertFalse(admitted['pr_blocked'],admitted['blockers'])

    def test_rules_drift_is_rejected(self):
        self.write_catalog();raw=render_rules(self.catalog).replace('Only an authenticated peer','Any peer',1)
        (self.component/'RULES.md').write_text(raw);revision=self.commit('Drifted rules')
        with self.assertRaisesRegex(GateError,'differs from adjacent claims.json'):
            catalog_receipt(self.repo,'fixture/repo',revision)

    def test_cli_refuses_to_overwrite_unmanaged_project_rules(self):
        self.write_catalog();rules=self.component/'RULES.md';rules.write_text('# Existing project rules\n')
        result=subprocess.run([sys.executable,str(SCRIPTS/'claim-rules.py'),'--claims',str(self.component/'claims.json'),
            '--rules',str(rules),'--write'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertEqual(rules.read_text(),'# Existing project rules\n')


if __name__=='__main__':unittest.main()
