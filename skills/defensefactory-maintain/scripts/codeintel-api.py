#!/usr/bin/env python3
"""One bounded CodeIntel workspace API request; credentials stay in inherited memory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default=os.environ.get('DEFENSEFACTORY_CONFIG'))
    p.add_argument('--method', choices=('GET', 'POST', 'PUT'), default='GET')
    p.add_argument('--path', required=True)
    p.add_argument('--body', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        config = json.loads(Path(a.config).read_text())
        base = config['codeintel_api_url'].rstrip('/')
        parsed = urllib.parse.urlsplit(base)
        relative = urllib.parse.urlsplit(a.path)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or relative.scheme or relative.netloc
                or not relative.path.startswith('/api/') or '..' in relative.path.split('/') or relative.fragment):
            raise ValueError('Use the operator-configured credential-free API base and relative /api/ path')
        if a.output.exists():
            raise ValueError('Use a new request receipt path; failures are not overwritten')
        variable = config.get('codeintel_token_env') or 'CODEINTEL_API_KEY'
        key = os.environ.get(variable, '')
        if not key or '\n' in key or '\r' in key:
            raise ValueError('Operator-provisioned API credential environment variable is unavailable')
        payload = a.body.read_bytes() if a.body else None
        if payload is not None:
            json.loads(payload)
        request = urllib.request.Request(base + a.path, method=a.method, data=payload,
            headers={config.get('codeintel_header_name', 'X-Api-Key'): ('Bearer ' if config.get('codeintel_header_name', '').lower() == 'authorization' else '') + key, 'Content-Type': 'application/json'})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        started = datetime.now(timezone.utc).isoformat()
        try:
            response = urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Response exceeded bounded size')
        clean = raw.replace(key.encode(), b'[REDACTED_CREDENTIAL]')
        try:
            body = json.loads(clean)
        except ValueError:
            body = {'non_json_response': clean.decode(errors='replace')}
        def redact(value):
            if isinstance(value, dict):
                return {k: '[REDACTED]' if k.lower() in ('apikey', 'password', 'token', 'secret', 'authorization')
                        else redact(v) for k, v in value.items()}
            if isinstance(value, list):
                return [redact(v) for v in value]
            if isinstance(value, str):
                return value.replace(key, '[REDACTED_CREDENTIAL]')
            return value
        receipt = {'method': a.method, 'base_url': base, 'path': a.path, 'status': status,
            'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
            'request_body_sha256': hashlib.sha256(payload).hexdigest() if payload else None,
            'response_sha256_before_redaction': hashlib.sha256(raw).hexdigest(), 'body': redact(body),
            'credential_recorded': False, 'automatic_retries': 0,
            'limitation': 'Sanitized HTTP observation, not index completion or source/semantic acceptance.'}
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x') as f:
            json.dump(receipt, f, indent=2)
        a.output.chmod(0o600)
        print(json.dumps({'status': status, 'receipt': str(a.output)}))
        return 0 if 200 <= status < 300 else 1
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as error:
        p.error(str(error) if not isinstance(error, urllib.error.URLError) else 'API transport unavailable')


if __name__ == '__main__':
    raise SystemExit(main())
