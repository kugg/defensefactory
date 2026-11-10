"""Disposable local release checks. No model, MCP, ticket or credential requests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/defensefactory/scripts'
sys.path.insert(0, str(SCRIPTS))
from factorycore.core import GateError
from factorycore.execution_capture import capture
from factorycore.handoff_bundle import prepare_bundle, verify_bundle
from factorycore.installation import install, load_config
from factorycore.trial_controls import scope_prepare, stage_start


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def opening(self):
        preparation = scope_prepare({'case': 'FIXTURE-1', 'attempt': 'synthetic', 'stage': 'verify',
            'subject': {'repository': 'fixture/component', 'revision': 'a' * 40},
            'performed_by': 'fixture-agent', 'authorization_reference': 'synthetic-test-policy',
            'boundaries': 'Disposable synthetic subprocesses only',
            'package': str(ROOT / 'skills/defensefactory-verify')})
        publication = {'id': 'synthetic-connector-record', 'body': preparation['scope_body'],
                       'createdAt': preparation['prepared_at']}
        return stage_start(preparation, publication, {**publication, 'operation': 'retrieval',
                                                     'retrieved_at': preparation['prepared_at']})

    def test_install_is_idempotent_and_preserves_unrelated_client_config(self):
        native = self.root / 'client/opencode.jsonc'
        native.parent.mkdir()
        native.write_text('// unrelated client settings\n{}')
        preferences = {'model': 'fixture/model', 'linear_project': 'Example project',
            'linear_url': '', 'codeintel_url': '', 'codeintel_api_url': '', 'codeintel_token_env': '',
            'github_repository': '', 'launcher': shutil.which('true'),
            'skills_directory': str(self.root / 'client/skills'),
            'output_directory': str(self.root / 'outputs')}
        config = self.root / 'factory/config.json'
        first = install(ROOT / 'skills', config, preferences)
        before = config.read_bytes()
        second = install(ROOT / 'skills', config, preferences)
        self.assertEqual(first['skills_linked'], 9)
        self.assertEqual(second['skills_linked'], 0)
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(native.read_text(), '// unrelated client settings\n{}')
        self.assertEqual(load_config(config)['model'], 'fixture/model')

    def test_runner_refuses_to_start_without_manual_opening(self):
        runner = module('release_runner', SCRIPTS / 'opencode-trial.py')
        prompt = self.root / 'prompt.txt'
        prompt.write_text('Synthetic only')
        target, manifest = runner.prepare(prompt, self.root, ROOT / 'skills', self.root / 'invocation',
            shutil.which('false'), 'fixture/model', self.root / 'unused-install')
        with self.assertRaisesRegex(ValueError, 'Manual kickoff required'):
            runner.execute(target, manifest)
        self.assertFalse((target / 'agent.jsonl').exists())

    def test_command_wrapper_keeps_real_failure_code_and_output(self):
        opening = self.root / 'opening.json'
        opening.write_text(json.dumps(self.opening()))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'stage-exec.py'), '--opening', str(opening),
            '--id', 'synthetic', '--cwd', str(self.root), '--output', str(self.root / 'capture'), '--',
            sys.executable, '-c', 'print("synthetic producer failed");raise SystemExit(42)'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 42, result.stderr)
        record = json.loads((self.root / 'capture/execution.json').read_text())
        self.assertTrue(record['stage_start_sha256'])
        self.assertIn('synthetic producer failed', Path(record['raw_log_reference']).read_text())

    def test_failed_capture_cannot_drop_dependencies_by_becoming_a_diagnostic(self):
        subject = {'revision': 'a' * 40}
        spec = {'id': 'synthetic', 'subject': subject, 'performed_by': 'fixture-agent',
            'argv': [sys.executable, '-c', 'print("failed fixture");raise SystemExit(1)'],
            'cwd': str(self.root), 'timeout_seconds': 5,
            'execution': {'format': 'command', 'reason': 'Synthetic fixture', 'success_criteria': 'zero exit'}}
        record = capture(spec, self.root / 'capture')
        plan = {'case': 'FIXTURE-1', 'attempt': 'synthetic', 'subject': subject, 'resources': [
            {'id': 'failed', 'kind': 'protocol_failure_record', 'path': str(self.root / 'capture/execution.json')}]}
        with self.assertRaisesRegex(GateError, 'Finished execution'):
            prepare_bundle(plan, self.root / 'bundle.tar.gz')
        plan['resources'][0]['kind'] = 'execution_receipt'
        result = prepare_bundle(plan, self.root / 'bundle.tar.gz')
        self.assertTrue(verify_bundle(Path(result['file']).read_bytes(), result['requirements'])['bundle_complete'])
        self.assertEqual(record['result'], 'violated')

    def test_standalone_archives_relocate_with_licenses_and_working_installer(self):
        packager = module('release_packager', ROOT / 'scripts/package-skills.py')
        packages = packager.sync(check=True)
        isolated = self.root / 'isolated'
        for package in packages:
            item = packager.export(package, self.root)
            first = (self.root / item['file']).read_bytes()
            self.assertEqual(item, packager.export(package, self.root))
            self.assertEqual(first, (self.root / item['file']).read_bytes())
            with tarfile.open(self.root / item['file']) as archive:
                archive.extractall(isolated, filter='data')
            relocated = isolated / package.name
            manifest = json.loads((relocated / 'package-manifest.json').read_text())
            for name, digest in manifest.items():
                self.assertEqual(hashlib.sha256((relocated / name).read_bytes()).hexdigest(), digest)
            self.assertEqual((relocated / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        result = subprocess.run([sys.executable, '-I', str(isolated / 'defensefactory/scripts/install-factory.py'),
            '--yes', '--model', 'fixture/model', '--linear-project', 'Example project',
            '--launcher', shutil.which('true'), '--config', str(self.root / 'config/config.json'),
            '--skills-directory', str(self.root / 'client/skills')], env=env, cwd=self.root,
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_evidence_helpers_import_only_their_package_under_isolated_python(self):
        for name in ('evidence-compare.py','handoff-audit.py','restore-artifact.py','ticket-transfer.py'):
            result=subprocess.run([sys.executable,'-I',str(SCRIPTS/name),'--help'],cwd=self.root,
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode,0,name+': '+result.stderr)
