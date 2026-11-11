"""KPP experimental public-message queue. No credential is stored in Git."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

ROOT = 'experiments/openrouter-queue'
BRANCH = 'kpp-openrouter-queue'
REPO = 'jodydugas-ctrl/Kitchen-Party-Protocol'

def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def validate(req, filename):
    if not isinstance(req, dict) or set(req) != {'schema', 'request_id', 'message'}:
        raise ValueError('INVALID_REQUEST')
    if req['schema'] != 'kpp.openrouter-queue-request/1':
        raise ValueError('INVALID_SCHEMA')
    rid = req['request_id']
    if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{32}', rid) or filename != rid+'.json':
        raise ValueError('INVALID_ID')
    if not isinstance(req['message'],str) or not req['message'].strip() or len(req['message']) > 4000:
        raise ValueError('INVALID_MESSAGE')
    return rid

def api(method, path, value=None):
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=canon(value) if value is not None else None,method=method,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                 'Accept':'application/vnd.github+json','Content-Type':'application/json',
                 'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=30) as r:
        return json.load(r)

def read_result(rid):
    try:
        d=api('GET',f'contents/{ROOT}/results/{rid}.json?ref={BRANCH}')
        return json.loads(base64.b64decode(d['content'])), d['sha']
    except urllib.error.HTTPError as e:
        if e.code==404:return None,None
        raise

def write_result(rid, value, sha=None):
    data={'message':'KPP queue result '+rid,'branch':BRANCH,
          'content':base64.b64encode(canon(value)+b'\n').decode()}
    if sha:data['sha']=sha
    api('PUT',f'contents/{ROOT}/results/{rid}.json',data)

def infer(key, message):
    body={'model':'openrouter/free','messages':[{'role':'user','content':message}],
          'stream':False,'max_tokens':2048}
    request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
        data=canon(body),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=60) as r:
            status=r.status;raw=r.read(262145)
        if len(raw)>262144:return {'status':'RESPONSE_TOO_LARGE','http_status':status}
        d=json.loads(raw);choice=d.get('choices',[{}])[0];text=choice.get('message',{}).get('content')
        if isinstance(text,str) and key in text:
            return {'status':'SENSITIVE_RESPONSE_WITHHELD','http_status':status}
        ok=isinstance(text,str) and bool(text.strip())
        return {'status':'OK' if ok else 'NO_USABLE_ASSISTANT_TEXT','http_status':status,
                'actual_model':d.get('model'),'completion_id':d.get('id'),
                'assistant_text':text if ok else None,'finish_reason':choice.get('finish_reason')}
    except urllib.error.HTTPError as e:
        return {'status':'PROVIDER_HTTP_ERROR','http_status':e.code,'assistant_text':None}
    except Exception:
        return {'status':'PROVIDER_OUTCOME_UNKNOWN','assistant_text':None}

def process(req,filename,read,write,call,key):
    rid=validate(req,filename);digest=hashlib.sha256(canon(req)).hexdigest()
    prior,sha=read(rid)
    if prior is not None:
        if prior.get('request_sha256')!=digest:raise ValueError('REQUEST_ID_REUSED')
        return  # Claimed or completed: never automatically repeat inference.
    base={'schema':'kpp.openrouter-queue-result/1','request_id':rid,'request_sha256':digest,
          'requested_model':'openrouter/free','authority':'NONE','simulated':False,
          'run_id':os.environ.get('GITHUB_RUN_ID'),'request_commit':os.environ.get('GITHUB_SHA')}
    if not key:
        write(rid,dict(base,status='SETUP_REQUIRED',assistant_text=None),None);return
    # Publish durable claim before the network request. Interrupted claims need review.
    write(rid,dict(base,status='CLAIMED_OUTCOME_UNKNOWN',assistant_text=None),None)
    claim,sha=read(rid)
    if not sha or claim.get('request_sha256')!=digest:raise ValueError('CLAIM_NOT_CONFIRMED')
    result=call(key,req['message'])
    write(rid,dict(base,**result),sha)

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/'+BRANCH:
        raise ValueError('WRONG_DEPLOYMENT')
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if event.get('deleted') or event.get('forced'):raise ValueError('UNSUPPORTED_PUSH')
    before=event['before']
    if not re.fullmatch('[0-9a-f]{40}',before) or before=='0'*40:raise ValueError('INVALID_BASE')
    names=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',before,os.environ['GITHUB_SHA'],'--',ROOT+'/requests/'],text=True).splitlines()
    if len(names)!=1:raise ValueError('EXACTLY_ONE_NEW_REQUEST_REQUIRED')
    name=names[0];p=Path(name)
    if p.parent.as_posix()!=ROOT+'/requests' or p.is_symlink() or p.stat().st_size>20000:
        raise ValueError('INVALID_FILE')
    process(json.loads(p.read_text()),p.name,read_result,write_result,infer,os.environ.get('OPENROUTER_API_KEY',''))
    print('KPP queue processed; read the result file. No secrets logged.')

if __name__=='__main__':
    try:main()
    except Exception:
        print('KPP queue failed; inspect request and claim state before retrying. Details withheld.')
        raise SystemExit(2)
