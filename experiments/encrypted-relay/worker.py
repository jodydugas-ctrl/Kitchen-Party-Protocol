"""One ephemeral runner; private key exists only in process memory."""
import base64,json,os,re,subprocess,time,urllib.request,urllib.error
from pathlib import Path
import relay
REPO='jodydugas-ctrl/Kitchen-Party-Protocol';BRANCH='kpp-encrypted-relay';ROOT='experiments/encrypted-relay'
def api(method,path,value=None):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,data=relay.canon(value) if value is not None else None,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(600000)
        if len(raw)>=600000:raise ValueError('OVERSIZED_GITHUB_REPLY')
        return json.loads(raw)
def get(kind,rid):
    try:
        d=api('GET',f'contents/{ROOT}/{kind}/{rid}.json?ref={BRANCH}')
        return json.loads(base64.b64decode(d['content']))
    except urllib.error.HTTPError as e:
        if e.code==404:return None
        raise

def put(kind,rid,v):
    # Create only: existing handshake prevents replay and loss of key provenance.
    api('PUT',f'contents/{ROOT}/{kind}/{rid}.json',{'branch':BRANCH,'message':'KPP encrypted relay '+kind+' '+rid,'content':base64.b64encode(relay.canon(v)+b'\n').decode()})
def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/'+BRANCH or os.environ.get('GITHUB_ACTOR')!='jodydugas-ctrl':raise ValueError('WRONG_HOST')
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());before=event['before'];commit=os.environ['GITHUB_SHA']
    if event.get('forced') or event.get('deleted') or not re.fullmatch('[a-f0-9]{40}',before) or before=='0'*40:raise ValueError('BAD_EVENT')
    names=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',before,commit,'--',ROOT+'/init/'],text=True).splitlines()
    if len(names)!=1:raise ValueError('ONE_INIT_REQUIRED')
    p=Path(names[0])
    if p.parent.as_posix()!=ROOT+'/init' or p.is_symlink() or p.stat().st_size>2000:raise ValueError('BAD_PATH')
    init=json.loads(p.read_text());relay.check_init(init);rid=init['request_id']
    if p.name!=rid+'.json':raise ValueError('BAD_NAME')
    h,secret=relay.receive(init,os.environ['GITHUB_RUN_ID'],commit)
    put('recipients',rid,h)  # A rerun fails here before provider execution.
    while time.time()<h['expires_at']:
        envelope=get('sealed',rid)
        if envelope is not None:
            put('claims',rid,{'request_id':rid,'envelope_sha256':relay.digest(envelope),'status':'CLAIMED_OUTCOME_UNKNOWN'})
            response=relay.execute(h,secret,envelope,relay.infer)
            put('responses',rid,response)
            print('Encrypted response published. No plaintext logged.');return
        time.sleep(5)
    put('expired',rid,{'request_id':rid,'status':'EXPIRED_WITHOUT_REQUEST'})
    print('Expired without inference.')
if __name__=='__main__':
    try:main()
    except Exception:
        print('Relay stopped. Inspect public state; never blindly retry uncertain outcomes.')
        raise SystemExit(2)
