"""No live service: test wire/auth behavior and nonsecret request receipts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'skills/defensefactory/scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CodeIntelTransport(unittest.TestCase):
    def test_stdio_preserves_tool_arguments_and_uses_workspace_header(self):
        bridge = load('codeintel-stdio')
        message = {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                   'params': {'name': 'grep', 'arguments': {'repo': 'fixture', 'pattern': 'Valid'}}}
        def send(url, body, headers):
            self.assertEqual(json.loads(body), message)
            self.assertEqual(headers['X-Api-Key'], 'synthetic-key')
            return b'{"jsonrpc":"2.0","id":7,"result":{"content":[]}}'
        result = bridge.forward(message, 'https://example.invalid/mcp', 'synthetic-key', 'X-Api-Key', send)
        self.assertEqual(result['id'], 7)
        self.assertNotIn('synthetic-key', json.dumps(result))

    def test_stdio_initialization_limits_capabilities_and_suppresses_secret_echo(self):
        bridge = load('codeintel-stdio')
        message = {'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2026-client'}}
        def send(url, body, headers):
            self.assertEqual(json.loads(body)['params']['protocolVersion'], '2025-06-18')
            return b'{"id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{},"resources":{}}}}'
        result = bridge.forward(message, 'https://example.invalid/mcp', 'synthetic-key', 'X-Api-Key', send)
        self.assertEqual(result['result']['protocolVersion'], '2026-client')
        self.assertEqual(result['result']['capabilities'], {'tools': {}})
        result = bridge.forward(message, 'https://example.invalid/mcp', 'synthetic-key', 'X-Api-Key',
                                lambda *args: b'{"message":"synthetic-key"}')
        self.assertIn('error', result)
        self.assertNotIn('synthetic-key', json.dumps(result))

    def test_unsupported_mcp_method_does_not_make_a_request(self):
        bridge = load('codeintel-stdio')
        send = Mock()
        result = bridge.forward({'id': 1, 'method': 'resources/list'}, 'https://example.invalid/mcp', '', 'X-Api-Key', send)
        self.assertEqual(result['error']['code'], -32601)
        send.assert_not_called()

    def test_api_receipt_redacts_credentials_and_preserves_http_failure_without_retry(self):
        api = load('codeintel-api')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'config.json'
            config.write_text(json.dumps({'codeintel_api_url': 'http://127.0.0.1:3000'}))
            output = root / 'response.json'
            key = 'synthetic-secret'
            raw = json.dumps({'error': 'active job', 'apiKey': key, 'message': key}).encode()
            class Response:
                code = 409
                def read(self, size): return raw
                def __enter__(self): return self
                def __exit__(self, *args): pass
            opener = Mock()
            opener.open.return_value = Response()
            argv = ['codeintel-api.py', '--config', str(config), '--path', '/api/repos/1/status', '--output', str(output)]
            with patch.object(api.urllib.request, 'build_opener', return_value=opener), patch.dict(os.environ, {'CODEINTEL_API_KEY': key}), patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(api.main(), 1)
            opener.open.assert_called_once()
            record = json.loads(output.read_text())
            self.assertEqual(record['status'], 409)
            self.assertEqual(record['automatic_retries'], 0)
            self.assertNotIn(key, output.read_text())
