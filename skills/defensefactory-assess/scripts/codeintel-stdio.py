#!/usr/bin/env python3
"""Tools-only compatibility bridge for CodeIntel's POST-only MCP transport."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SUPPORTED = {'initialize', 'ping', 'tools/list', 'tools/call', 'notifications/initialized', 'notifications/cancelled'}


def forward(message, url, credential, header_name, send=None):
    identifier = message.get('id')
    def error(text, code=-32000):
        if 'id' not in message:
            return None
        return {'jsonrpc': '2.0', 'id': identifier, 'error': {'code': code, 'message': text}}
    if message.get('method') not in SUPPORTED:
        return error('This CodeIntel bridge supports the declared tools subset only', -32601) if 'id' in message else None
    upstream = dict(message)
    requested = None
    if message.get('method') == 'initialize':
        params = dict(message.get('params', {}))
        requested = params.get('protocolVersion')
        params['protocolVersion'] = '2025-06-18'
        upstream['params'] = params
    raw = json.dumps(upstream).encode()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if credential:
        headers[header_name] = ('Bearer ' if header_name.lower() == 'authorization' else '') + credential
    try:
        if send is not None:
            body = send(url, raw, headers)
        else:
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            with build_opener(NoRedirect()).open(Request(url, data=raw, headers=headers, method='POST'), timeout=60) as response:
                body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            return error('CodeIntel MCP response exceeded size budget')
        if not body:
            return None
        if credential and credential.encode() in body:
            return error('Credential-bearing upstream response suppressed')
        result = json.loads(body)
        if requested and isinstance(result, dict) and isinstance(result.get('result'), dict):
            # Advertise only the upstream tools capability, never new protocol features.
            result['result']['protocolVersion'] = requested
            result['result']['capabilities'] = {'tools': result['result'].get('capabilities', {}).get('tools', {})}
        return result
    except HTTPError as exc:
        return error('CodeIntel MCP returned HTTP ' + str(exc.code))
    except (URLError, TimeoutError, ValueError):
        return error('CodeIntel MCP transport or JSON response unavailable')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True)
    p.add_argument('--credential-env', default='')
    p.add_argument('--header-name', default='X-Api-Key')
    a = p.parse_args()
    from urllib.parse import urlsplit
    parsed = urlsplit(a.url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        p.error('Use an operator-provided credential-free HTTP(S) MCP URL')
    credential = os.environ.get(a.credential_env, '') if a.credential_env else ''
    if a.credential_env and (not credential or '\r' in credential or '\n' in credential):
        p.error('Configured credential environment variable is unavailable')
    for line in sys.stdin.buffer:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError('JSON-RPC object required')
            result = forward(message, a.url, credential, a.header_name)
        except (ValueError, UnicodeError):
            result = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON-RPC request'}}
        if result is not None:
            print(json.dumps(result, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
