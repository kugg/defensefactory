#!/usr/bin/env python3
"""Transfer exact ticket resource bytes from native metadata; never retype signed URLs."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.core import sha
from factorycore.evidence_inventory import public_value
from factorycore.evidence_records import write_json


def quoted(value):
    if '\r' in value or '\n' in value:
        raise ValueError('Native metadata contains an invalid header/URL line')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'


def transfer(metadata_path, file, receipt_path, *, upload=False, expected=None, event_id=None):
    receipt_path=Path(receipt_path);file=Path(file)
    registered=os.environ.get('DEFENSEFACTORY_PUBLICATION_ROOT')
    if registered and (Path(registered).resolve() not in receipt_path.resolve().parents
                       or (not upload and Path(registered).resolve() not in file.resolve().parents)):
        raise ValueError('Save transfer receipts/downloads in DEFENSEFACTORY_PUBLICATION_ROOT')
    if receipt_path.exists():raise ValueError('Use a new transfer receipt')
    if expected and not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Expected digest must be a full SHA-256')
    raw=Path(metadata_path).read_bytes()
    if event_id:
        matches=[]
        for line in raw.splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='tool_use' and event.get('part',{}).get('id')==event_id:matches.append((line,event['part']))
        if len(matches)!=1:raise ValueError('Select exactly one actual native tool event ID')
        raw,part=matches[0]
        required='prepare_attachment_upload' if upload else 'get_attachment'
        if required not in part.get('tool','') or part.get('state',{}).get('status')!='completed':
            raise ValueError('Selected event is not the completed native transfer-metadata operation')
        metadata=json.loads(part['state']['output'])
    else:metadata=json.loads(raw)
    if isinstance(metadata,dict) and isinstance(metadata.get('content'),list):
        texts=[c['text'] for c in metadata['content'] if c.get('type')=='text']
        if len(texts)!=1:raise ValueError('Native response must contain one unambiguous JSON metadata object')
        metadata=json.loads(texts[0])
    request=metadata.get('uploadRequest',{}) if upload else {}
    url=request.get('url') if upload else metadata.get('url')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Use the exact credential-free HTTPS transfer URL returned by the native connector')
    if upload and not file.is_file():raise ValueError('Upload file is unavailable')
    if not upload and file.exists():raise ValueError('Download path already exists; preserve it')
    if upload and file.stat().st_size>128*1024*1024:raise ValueError('Transfer exceeds bounded evidence size')
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    if not upload:
        file.parent.mkdir(parents=True,exist_ok=True)
        with file.open('xb'):pass
        file.chmod(0o600)
    record={'record_type':'ticket_transfer','phase':'prepared','operation':'upload' if upload else 'download',
            'native_metadata_sha256':sha(raw),'native_resource_id':metadata.get('id'),
            'native_event_id':event_id,
            'native_issue_id':metadata.get('issueId'),'asset_url':metadata.get('assetUrl'),
            'expected_sha256':expected,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'credentials_recorded':False,'automatic_retries':0}
    before=sha(file.read_bytes()) if upload else None
    write_json(receipt_path,record)
    # Credentials only occupy a private temporary curl config, never producer argv/logs.
    with tempfile.TemporaryDirectory(prefix='ticket-transfer-') as temp:
        config=Path(temp)/'request.conf'
        lines=['url = '+quoted(url)]
        if upload:
            lines.append('request = "PUT"')
            headers=request.get('headers',{})
            if not isinstance(headers,dict):raise ValueError('Native signed headers must be a mapping')
            lines.extend('header = '+quoted(k+': '+v) for k,v in headers.items())
        config.write_text('\n'.join(lines)+'\n');config.chmod(0o600)
        argv=['curl','--config',str(config),'--fail','--silent','--show-error','--max-time','30',
              '--max-filesize',str(128*1024*1024),'--write-out','%{http_code}']
        if upload:argv+=['--upload-file',str(file)]
        else:argv+=['--output',str(file)]
        try:
            response=subprocess.run(argv,capture_output=True,text=True,timeout=35)
            status=response.stdout[-3:]
            error_text=response.stderr.replace(url,parsed.scheme+'://'+parsed.netloc+parsed.path+'?[REDACTED]')
            for value in request.get('headers',{}).values():error_text=error_text.replace(value,'[REDACTED_HEADER]')
            record.update(http_status=int(status) if status.isdigit() else None,
                          producer_exit_code=response.returncode,error=public_value(error_text))
        except (OSError,subprocess.TimeoutExpired) as error:
            record.update(producer_exit_code=None,http_status=None,error=type(error).__name__)
    digest=sha(file.read_bytes())
    record.update(phase='finished',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  file_sha256=digest,file_bytes=file.stat().st_size,local_file=str(file.resolve()))
    success=(record['producer_exit_code']==0 and record.get('http_status') is not None
             and 200<=record['http_status']<300 and (expected is None or digest==expected)
             and (before is None or digest==before))
    record['result']='recorded' if success else 'violated'
    record['bytes_verified']=bool(success and expected)
    record['scope']='HTTP transfer/integrity only, not native attachment publication, source acceptance or closure.'
    receipt_path.write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata',required=True,type=Path)
    p.add_argument('--event-id',help='Read the exact native tool result from a private OpenCode JSONL log instead of retyping metadata')
    operation=p.add_mutually_exclusive_group(required=True)
    operation.add_argument('--upload-file',type=Path)
    operation.add_argument('--download-file',type=Path)
    p.add_argument('--expected-sha256')
    p.add_argument('--receipt',required=True,type=Path)
    a=p.parse_args()
    try:
        result=transfer(a.metadata,a.upload_file or a.download_file,a.receipt,
                        upload=a.upload_file is not None,expected=a.expected_sha256,event_id=a.event_id)
        print(json.dumps({'receipt':str(a.receipt),'result':result['result'],'file_sha256':result['file_sha256']}))
        return 0 if result['result']=='recorded' else 1
    except (OSError,ValueError,KeyError,TypeError) as error:p.error(str(error))


if __name__=='__main__':raise SystemExit(main())
