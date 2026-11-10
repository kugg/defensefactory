#!/usr/bin/env python3
"""One bounded CodeIntel workspace API request; credentials stay in inherited memory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.core import identity, sha
from factorycore.evidence_records import dependency, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default=os.environ.get('DEFENSEFACTORY_CONFIG'))
    p.add_argument('--method', choices=('GET', 'POST', 'PUT'), default='GET')
    p.add_argument('--path', required=True)
    p.add_argument('--body', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    key = ''
    reserved = False
    try:
        if a.output.exists():
            raise ValueError('Use a new request receipt path; failures are not overwritten')
        registered = os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT')
        if registered and Path(registered).resolve() not in a.output.resolve().parents:
            raise ValueError('Write API observations inside DEFENSEFACTORY_EVIDENCE_ROOT')
        config = json.loads(Path(a.config).read_text())
        base = config['codeintel_api_url'].rstrip('/')
        parsed = urllib.parse.urlsplit(base)
        relative = urllib.parse.urlsplit(a.path)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or relative.scheme or relative.netloc
                or not relative.path.startswith('/api/') or '..' in relative.path.split('/') or relative.fragment):
            raise ValueError('Use the operator-configured credential-free API base and relative /api/ path')
        variable = config.get('codeintel_token_env') or 'CODEINTEL_API_KEY'
        key = os.environ.get(variable, '')
        if not key or '\n' in key or '\r' in key:
            raise ValueError('Operator-provisioned API credential environment variable is unavailable')
        payload = a.body.read_bytes() if a.body else None
        if payload is not None:
            json.loads(payload)
        from factorycore.evidence_inventory import public_value
        a.output.parent.mkdir(parents=True,exist_ok=True)
        deps=[]
        if payload is not None:
            parsed_body=json.loads(payload);safe_body=public_value(parsed_body)
            body_file=a.output.with_name(a.output.stem+'.request.json')
            with body_file.open('xb') as saved:
                saved.write(payload if safe_body==parsed_body else json.dumps(safe_body).encode())
            body_file.chmod(0o600)
            deps.append(dependency('request-body',body_file,'request_input'))
        opening_path=os.environ.get('DEFENSEFACTORY_STAGE_OPENING')
        opening=json.loads(Path(opening_path).read_text()) if opening_path else None
        if opening:
            opening_copy=a.output.with_name(a.output.stem+'.opening.json')
            write_json(opening_copy,opening)
            deps.append(dependency('stage-opening',opening_copy,'execution_context'))
        receipt={'record_type':'api_observation','phase':'prepared','method':a.method,'base_url':base,'path':a.path,
            'request_body_sha256':hashlib.sha256(payload).hexdigest() if payload else None,
            'request_body_redacted': bool(payload is not None and safe_body!=parsed_body),
            'evidence_dependencies':deps,'credential_environment_name':variable,'credential_recorded':False,
            'stage_start_sha256':identity(opening) if opening else None,
            'started_at':datetime.now(timezone.utc).isoformat(),'automatic_retries':0}
        write_json(a.output,receipt);reserved=True
        request = urllib.request.Request(base + a.path, method=a.method, data=payload,
            headers={config.get('codeintel_header_name', 'X-Api-Key'): ('Bearer ' if config.get('codeintel_header_name', '').lower() == 'authorization' else '') + key, 'Content-Type': 'application/json'})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        started = receipt['started_at']
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
        receipt.update({'phase':'finished','method': a.method, 'base_url': base, 'path': a.path, 'status': status,
            'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
            'request_body_sha256': hashlib.sha256(payload).hexdigest() if payload else None,
            'response_sha256_before_redaction': hashlib.sha256(raw).hexdigest(), 'body': redact(body),
            'credential_recorded': False, 'automatic_retries': 0,
            'limitation': 'Sanitized HTTP observation, not index completion or source/semantic acceptance.'})
        with a.output.open('w') as f:
            json.dump(receipt, f, indent=2)
        a.output.chmod(0o600)
        print(json.dumps({'status': status, 'receipt': str(a.output)}))
        return 0 if 200 <= status < 300 else 1
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as error:
        message=str(error) if not isinstance(error,urllib.error.URLError) else 'API transport unavailable'
        if key:message=message.replace(key,'[REDACTED_CREDENTIAL]')
        if reserved:
            receipt.update(phase='failed',result='inconclusive',error=message,finished_at=datetime.now(timezone.utc).isoformat())
            a.output.write_text(json.dumps(receipt,indent=2)+'\n')
        p.error(message)


if __name__ == '__main__':
    raise SystemExit(main())
