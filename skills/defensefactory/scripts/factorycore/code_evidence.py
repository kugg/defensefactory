"""Revision-bound MCP adapter. No graph reconstruction or backend success fabrication."""
import copy
import json
import urllib.request
from .core import require, identity, sha
from .claims import EvidenceCache


class MCPClient:
    def __init__(self, url, headers, timeout=30):
        self.url=url;self.headers=dict(headers);self.timeout=timeout
    def call(self, tool, arguments):
        data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':arguments}}).encode()
        h={**self.headers,'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-06-18'}
        req=urllib.request.Request(self.url,data=data,headers=h)
        with urllib.request.urlopen(req,timeout=self.timeout) as response:raw=response.read()
        result=json.loads(raw)
        require('error' not in result and not result.get('result',{}).get('isError'),'MCP query failed')
        return result


class CodeEvidenceBackend:
    def __init__(self, client, allowed_repositories, cache=None):
        self.client=client;self.allowed=set(allowed_repositories);self.cache=cache or EvidenceCache()
    def evaluate(self, subject, tool, arguments, *, policy_sha256, extractor):
        require(subject['repository'] in self.allowed, 'Repository access denied')
        require(arguments.get('repo')==subject['repository'], 'Query scope differs from source subject')
        require(subject.get('revision') and len(subject['revision'])==40, 'Exact source revision required')
        raw=self.client.call(tool,arguments);result=raw.get('result',{});meta=result.get('_meta',{})
        matches=meta.get('matches',[]);graph=meta.get('evidence',{})
        scopes=graph.get('ActiveScopes',[])
        rows=matches or scopes
        require(bool(rows),'No precise source correspondence; lexical-only/unsupported result')
        for row in rows:
            revision=row.get('CommitHash',row.get('commitHash'));require(revision==subject['revision'],'Index/subject commit mismatch')
        diagnostics=list(graph.get('Warnings') or [])
        text='\n'.join(x.get('text','') for x in result.get('content',[]) if x.get('type')=='text')
        if 'truncat' in text.lower():diagnostics.append('response_truncated')
        receipt={'schema_version':1,'subject':copy.deepcopy(subject),'producer':'CodeIntel MCP','tool':tool,'arguments':arguments,
                 'query_sha256':identity({'tool':tool,'arguments':arguments}), 'policy_sha256':policy_sha256,'extractor':extractor,
                 'raw_sha256':identity(raw),'raw':raw,'semantic_available':True,'diagnostics':diagnostics,
                 'coverage':'selected_results_only','complete':False,'covered_files':sorted({m['FilePath'] for m in matches}),
                 'source_scopes':scopes,'cache_key':identity({'subject':subject,'query':arguments,'tool':tool,'policy':policy_sha256,'extractor':extractor}),
                 'limits':'Exact returned source binding, not total reference/dispatch/runtime coverage. Graph confidence scores are producer rankings.'}
        return {'reference':self.cache.put(receipt),'receipt':receipt}
    def resolve(self, reference):return self.cache.get(reference,self.allowed)
    def propose_stitch(self, proposal, validating_evidence=None):
        require(proposal['subject']['repository'] in self.allowed,'Repository access denied')
        return {'proposal':proposal,'state':'unresolved' if not validating_evidence else 'requires_adjudication','validation_evidence':validating_evidence or [],'accepted':False}


def configured_host_client():
    """Read credentials from the operator's existing MCP capability, never a ticket resource."""
    from pathlib import Path
    import subprocess
    import tomllib
    config=tomllib.loads((Path.home()/'.codex/config.toml').read_text())['mcp_servers']['codeintel']
    headers=json.loads(subprocess.check_output(config['http_headers_helper'],shell=True,text=True))
    return MCPClient(config['url'],headers)
