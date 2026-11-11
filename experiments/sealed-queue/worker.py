#!/usr/bin/env python3
"""KPP experimental sealed GitHub Actions queue worker.

Only ciphertext and nonsecret metadata are committed. Worker reads provider
credential from Actions secret OPENROUTER_API_KEY and never prints it.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
from protocol import (REPO,BRANCH,SCHEMA_RESULT,canon,digest,derived_receiver,
                      validate_recipient,open_envelope,seal_result)

ROOT='experiments/sealed-queue'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def api(method,path,value=None):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=canon(value) if value is not None else None,method=method,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                 'Accept':'application/vnd.github+json','Content-Type':'application/json',
                 'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

def read_current(path):
    try:
        f=api('GET',f'contents/{path}?ref={BRANCH}')
        return json.loads(base64.b64decode(f['content'])),f['sha']
    except urllib.error.HTTPError as e:
        if e.code==404:return None,None
        raise

def write_current(path,value,*,sha=None):
    body={'message':'KPP sealed queue state update','branch':BRANCH,
          'content':base64.b64encode(canon(value)+b'\n').decode()}
    if sha:body['sha']=sha
    return api('PUT',f'contents/{path}',body)

def provider_call(secret,message):
    req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
       data=canon({'model':'openrouter/free','messages':[{'role':'user','content':message}],
                   'max_tokens':2048,'stream':False}),method='POST',
       headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
    try:
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(),NoRedirect())
        with opener.open(req,timeout=45) as r:
            code=r.status;raw=r.read(65537)
        if len(raw)>65536:return {'schema':'kpp.provider-result/1','status':'RESPONSE_TOO_LARGE','simulated':False,'http_status':code,'assistant_text':None}
        d=json.loads(raw);reply=d['choices'][0]['message']['content']
        if not isinstance(reply,str) or not reply.strip():
            return {'schema':'kpp.provider-result/1','status':'NO_USABLE_ASSISTANT_TEXT',
                    'simulated':False,'http_status':code,'assistant_text':None,
                    'actual_model':d.get('model'),'completion_id':d.get('id')}
        # Guard against accidentally returning a secret in provider data.
        if secret in reply:return {'schema':'kpp.provider-result/1','status':'SENSITIVE_RESPONSE_WITHHELD','simulated':False,'http_status':code,'assistant_text':None}
        return {'schema':'kpp.provider-result/1','status':'OK','simulated':False,
                'http_status':code,'actual_model':d.get('model'),'completion_id':d.get('id'),
                'assistant_text':reply}
    except urllib.error.HTTPError as e:
        return {'schema':'kpp.provider-result/1','status':'PROVIDER_HTTP_ERROR','simulated':False,'http_status':e.code,'assistant_text':None}
    except Exception:
        return {'schema':'kpp.provider-result/1','status':'PROVIDER_OUTCOME_UNKNOWN',
                'simulated':False,'http_status':None,'assistant_text':None}

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/'+BRANCH:
        raise ValueError('WRONG_REPOSITORY_OR_BRANCH')
    secret=os.environ.get('OPENROUTER_API_KEY')
    recv,signer,recipient=derived_receiver(secret)
    path=f'{ROOT}/recipient.json'
    published,sha=read_current(path)
    if published is None:
        write_current(path,recipient)
        print('KPP recipient public key initialized; no plaintext secret committed')
        return
    if published!=recipient:
        raise ValueError('RECIPIENT_MISMATCH_POSSIBLE_SECRET_ROTATION')
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if event.get('deleted') or event.get('forced'):raise ValueError('UNSUPPORTED_EVENT')
    before=event['before']
    if not re.fullmatch(r'[0-9a-f]{40}',before) or before=='0'*40:
        raise ValueError('INVALID_EVENT_BASE')
    paths=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',
           before,os.environ['GITHUB_SHA'],'--',ROOT+'/requests/'],text=True).splitlines()
    if not paths:
        print('KPP no request in this push')
        return
    if len(paths)!=1:raise ValueError('MULTIPLE_REQUESTS_NOT_SUPPORTED')
    f=Path(paths[0]);rid=f.stem
    if f.parent.as_posix()!=ROOT+'/requests' or not re.fullmatch(r'[0-9a-f]{32}',rid) or f.stat().st_size>15000 or f.is_symlink():
        raise ValueError('INVALID_REQUEST_FILE')
    envelope=json.loads(f.read_text())
    if envelope.get('request_id')!=rid:raise ValueError('REQUEST_FILENAME_MISMATCH')
    payload=open_envelope(recv,recipient,envelope)
    outpath=f'{ROOT}/results/{rid}.json'
    prior,resultsha=read_current(outpath)
    if prior is not None:
        if prior.get('request_sha256')!=digest(envelope):raise ValueError('REUSED_REQUEST_ID')
        print('KPP request already claimed or completed; no resend')
        return
    claim={'schema':SCHEMA_RESULT,'request_id':rid,'request_sha256':digest(envelope),
           'status':'CLAIMED_OUTCOME_UNKNOWN','recipient_key_id':recipient['key_id']}
    write_current(outpath,claim)
    confirm,resultsha=read_current(outpath)
    if confirm!=claim or not resultsha:raise ValueError('CLAIM_NOT_CONFIRMED')
    result=provider_call(secret,payload['message'])
    sealed=seal_result(recv,signer,recipient,envelope,result,
                       run_id=os.environ.get('GITHUB_RUN_ID'),request_commit=os.environ.get('GITHUB_SHA'))
    write_current(outpath,sealed,sha=resultsha)
    print('KPP sealed result committed; plaintext request and reply not logged')

if __name__=='__main__':
    try:main()
    except Exception:
        print('KPP sealed queue failed. No secrets logged; review workflow state before retrying.')
        raise SystemExit(2)
