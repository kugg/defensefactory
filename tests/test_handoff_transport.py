"""Mock only HTTPS transport; exercise durable bytes/receipts and a fake local runner."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/defensefactory/scripts'
sys.path.insert(0,str(SCRIPTS))
from factorycore.core import sha
from factorycore.trial_controls import scope_prepare,stage_start


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),SCRIPTS/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


class HandoffTransport(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name).resolve()

    def test_ticket_download_uses_exact_native_metadata_and_preserves_failed_bytes(self):
        helper=load('ticket-transfer')
        meta=self.root/'native.json';meta.write_text(json.dumps({'id':'fixture-asset',
            'url':'https://example.invalid/object?signature=synthetic-signature'}))
        content=b'actual bytes';target=self.root/'download';receipt=self.root/'transfer.json'
        def request(argv,**kwargs):
            self.assertNotIn('synthetic-signature',' '.join(argv))
            config=Path(argv[argv.index('--config')+1]).read_text()
            self.assertIn('signature=synthetic-signature',config)
            Path(argv[argv.index('--output')+1]).write_bytes(content)
            return subprocess.CompletedProcess(argv,0,'200','')
        with patch.object(helper.subprocess,'run',side_effect=request):
            result=helper.transfer(meta,target,receipt,expected='0'*64)
        self.assertEqual(result['result'],'violated')
        self.assertEqual(target.read_bytes(),content)
        self.assertNotIn('synthetic-signature',receipt.read_text())
        with self.assertRaises(ValueError):helper.transfer(meta,target,receipt,expected=sha(content))

    def test_ticket_upload_sends_signed_headers_without_logging_them(self):
        helper=load('ticket-transfer');payload=self.root/'bundle';payload.write_bytes(b'fixture')
        meta=self.root/'native.json';meta.write_text(json.dumps({'issueId':'fixture-issue','assetUrl':'https://example.invalid/asset',
            'uploadRequest':{'url':'https://example.invalid/upload?signature=synthetic-signature',
                'headers':{'Content-Type':'application/gzip','Authorization':'synthetic-auth-value'}}}))
        def request(argv,**kwargs):
            self.assertNotIn('synthetic-auth-value',' '.join(argv))
            config=Path(argv[argv.index('--config')+1]).read_text()
            self.assertIn('Authorization: synthetic-auth-value',config)
            return subprocess.CompletedProcess(argv,0,'200','')
        receipt=self.root/'upload-receipt.json'
        with patch.object(helper.subprocess,'run',side_effect=request):
            result=helper.transfer(meta,payload,receipt,upload=True,expected=sha(b'fixture'))
        self.assertTrue(result['bytes_verified'])
        self.assertNotIn('synthetic-auth-value',receipt.read_text())
        self.assertEqual(result['file_sha256'],sha(b'fixture'))

    def test_transfer_extracts_exact_native_event_metadata_without_manual_url_copy(self):
        helper=load('ticket-transfer');log=self.root/'events.jsonl';output=self.root/'payload'
        meta={'id':'fixture-asset','url':'https://example.invalid/exact?signature=synthetic-signature'}
        envelope={'content':[{'type':'text','text':json.dumps(meta)}]}
        event={'type':'tool_use','part':{'id':'native-result-id','tool':'linear_get_attachment',
            'state':{'status':'completed','output':json.dumps(envelope)}}}
        log.write_text(json.dumps(event)+'\n')
        def request(argv,**kwargs):
            config=Path(argv[argv.index('--config')+1]).read_text()
            self.assertIn('/exact?signature=synthetic-signature',config)
            Path(argv[argv.index('--output')+1]).write_bytes(b'fixture')
            return subprocess.CompletedProcess(argv,0,'200','')
        with patch.object(helper.subprocess,'run',side_effect=request):
            result=helper.transfer(log,output,self.root/'receipt.json',expected=sha(b'fixture'),event_id='native-result-id')
        self.assertTrue(result['bytes_verified']);self.assertEqual(result['native_event_id'],'native-result-id')

    def test_api_snapshots_request_body_and_keeps_transport_failure(self):
        helper=load('codeintel-api');config=self.root/'config.json'
        config.write_text(json.dumps({'codeintel_api_url':'https://example.invalid'}))
        body=self.root/'request.json';body.write_text('{"name":"fixture","config":{"branches":["candidate"]}}')
        output=self.root/'response.json';opener=Mock();opener.open.side_effect=helper.urllib.error.URLError('offline')
        args=['codeintel-api.py','--config',str(config),'--method','POST','--path','/api/connections',
              '--body',str(body),'--output',str(output)]
        with patch.object(helper.urllib.request,'build_opener',return_value=opener),patch.dict(os.environ,{'CODEINTEL_API_KEY':'synthetic-key'},clear=True),patch('sys.argv',args),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):helper.main()
        record=json.loads(output.read_text());self.assertEqual(record['phase'],'failed')
        saved=next(d for d in record['evidence_dependencies'] if d['name']=='request-body')
        self.assertEqual(Path(saved['path']).read_bytes(),body.read_bytes())
        self.assertNotIn('synthetic-key',output.read_text())
        opener.open.assert_called_once()

    def test_runner_leaves_postflight_failure_despite_producer_exit_zero(self):
        runner=load('opencode-trial');project=self.root/'project';project.mkdir()
        launcher=self.root/'fake-opencode'
        launcher.write_text('#!'+sys.executable+'\nimport json\nprint(json.dumps('+repr({
            'type':'tool_use','sessionID':'synthetic-fresh-session','part':{'tool':'bash','state':{
                'input':{'command':'go build ./... | tail -1'},'output':'0','status':'completed'}}})+'))\n')
        launcher.chmod(0o755);prompt=self.root/'prompt';prompt.write_text('Synthetic local test only')
        prep=scope_prepare({'case':'FIXTURE-1','attempt':'runner-fixture','stage':'verify','subject':{'revision':'a'*40},
            'performed_by':'fixture','package':str(ROOT/'skills/defensefactory-verify'),
            'authorization_reference':'synthetic fixture','boundaries':'No network or real model'})
        publication={'id':'synthetic-record','body':prep['scope_body'],'createdAt':prep['prepared_at']}
        opening=stage_start(prep,publication,{**publication,'operation':'retrieval','retrieved_at':prep['prepared_at']})
        target,manifest=runner.prepare(prompt,project,ROOT/'skills',self.root/'invocation',launcher,'fixture/model',ROOT/'skills',opening=opening)
        result=runner.execute(target,manifest)
        self.assertEqual(result['producer_exit_code'],0)
        self.assertFalse(result['whole_attempt_handoff_ready'])
        self.assertTrue((target/'postflight/inventory.json').is_file())
        self.assertEqual(manifest['environment']['DEFENSEFACTORY_EVENT_LOG'],str(target/'agent.jsonl'))


if __name__=='__main__':unittest.main()
