"""KPP encrypted mailbox v1. Agent-side functions need no networking.
Public handshake provenance must be checked through authenticated GitHub tools.
The worker sees the API key and message. GitHub stores public metadata/ciphertext.
"""
import base64
import hashlib
import json
import os
import re
import time
import uuid
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA='kpp.encrypted-mailbox/1'
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(v):return hashlib.sha256(canon(v)).hexdigest()
def enc(b):return base64.urlsafe_b64encode(b).decode().rstrip('=')
def dec(s):
    if not isinstance(s,str) or not re.fullmatch('[A-Za-z0-9_-]+',s) or len(s)>400000:raise ValueError('BAD_BASE64')
    return base64.urlsafe_b64decode(s+'='*((-len(s))%4))
def public(k):return enc(k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
def private(k):return enc(k.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
def exact(d,fields):
    if not isinstance(d,dict) or set(d)!=set(fields.split()):raise ValueError('BAD_FIELDS')
def identifier(s):
    if not isinstance(s,str) or not re.fullmatch('[a-f0-9]{32}',s):raise ValueError('BAD_ID')
def check_init(init):
    exact(init,'schema request_id client_public')
    if init['schema']!=SCHEMA:raise ValueError('BAD_SCHEMA')
    identifier(init['request_id'])
    if len(dec(init['client_public']))!=32:raise ValueError('BAD_KEY')
def begin():
    key=X25519PrivateKey.generate()
    init={'schema':SCHEMA,'request_id':uuid.uuid4().hex,'client_public':public(key)}
    return init,{'init':init,'client_private':private(key),'sealed':False,'collected':False}
def receive(init,run_id,commit,now=None):
    check_init(init);now=int(time.time()) if now is None else now
    key=X25519PrivateKey.generate()
    h=dict(init,server_public=public(key),run_id=str(run_id),init_commit=commit,expires_at=now+600)
    return h,private(key)
def check_handshake(init,h,run_id,commit,now=None):
    check_init(init);exact(h,'schema request_id client_public server_public run_id init_commit expires_at')
    if any(h[k]!=v for k,v in init.items()) or h['run_id']!=str(run_id) or h['init_commit']!=commit:raise ValueError('HANDSHAKE_MISMATCH')
    if len(dec(h['server_public']))!=32:raise ValueError('BAD_KEY')
    now=int(time.time()) if now is None else now
    if type(h['expires_at']) is not int or not now<h['expires_at']<=now+660:raise ValueError('EXPIRED')
def session_key(secret,peer,h,direction):
    shared=X25519PrivateKey.from_private_bytes(dec(secret)).exchange(X25519PublicKey.from_public_bytes(dec(peer)))
    return HKDF(algorithm=hashes.SHA256(),length=32,salt=bytes.fromhex(digest(h)),info=('kpp-mailbox-v1/'+direction).encode()).derive(shared)
def pack(value,key,aad):
    nonce=os.urandom(12)
    return {'nonce':enc(nonce),'ciphertext':enc(AESGCM(key).encrypt(nonce,canon(value),canon(aad)))}
def unpack(box,key,aad):
    exact(box,'nonce ciphertext')
    return json.loads(AESGCM(key).decrypt(dec(box['nonce']),dec(box['ciphertext']),canon(aad)))
def unlock(token,password):
    parts=token.strip().split('.')
    if len(parts)!=5 or parts[:2]!=['v1','scrypt-aes256gcm']:raise ValueError('BAD_TOKEN')
    salt,nonce,cipher=map(dec,parts[2:])
    if len(salt)!=16 or len(nonce)!=12:raise ValueError('BAD_TOKEN')
    key=hashlib.scrypt(password.encode(),salt=salt,n=32768,r=8,p=1,dklen=32,maxmem=128*1024*1024)
    return AESGCM(key).decrypt(nonce,cipher,b'api-key-v1').decode()
def seal(state,h,api_key,message,run_id,commit,now=None):
    if state['sealed']:raise ValueError('ALREADY_SEALED')
    check_handshake(state['init'],h,run_id,commit,now)
    if not isinstance(api_key,str) or not 10<=len(api_key)<=10000:raise ValueError('BAD_API_KEY')
    if not isinstance(message,str) or not message.strip() or len(message)>4000:raise ValueError('BAD_MESSAGE')
    payload={'message':message,'api_key':api_key}
    aad={'handshake_sha256':digest(h),'direction':'request'}
    box=pack(payload,session_key(state['client_private'],h['server_public'],h,'request'),aad)
    envelope={'schema':SCHEMA,'request_id':h['request_id'],'handshake_sha256':digest(h),'box':box}
    state.update(sealed=True,handshake=h,envelope_sha256=digest(envelope))
    return envelope

def execute(h,secret,envelope,call,now=None):
    exact(envelope,'schema request_id handshake_sha256 box')
    now=int(time.time()) if now is None else now
    if now>=h['expires_at']:raise ValueError('EXPIRED')
    if envelope['schema']!=SCHEMA or envelope['request_id']!=h['request_id'] or envelope['handshake_sha256']!=digest(h):raise ValueError('REQUEST_MISMATCH')
    aad={'handshake_sha256':digest(h),'direction':'request'}
    payload=unpack(envelope['box'],session_key(secret,h['client_public'],h,'request'),aad)
    exact(payload,'message api_key')
    key,msg=payload['api_key'],payload['message']
    if not isinstance(key,str) or not 10<=len(key)<=10000 or not isinstance(msg,str) or not msg.strip() or len(msg)>4000:raise ValueError('BAD_REQUEST')
    result=call(key,msg)
    # Prevent accidental secret echoes even in encrypted released output.
    if key in json.dumps(result):result={'status':'SENSITIVE_RESPONSE_WITHHELD','assistant_text':None,'simulated':False}
    receipt={'result':result,'handshake_sha256':digest(h),'envelope_sha256':digest(envelope),'request_id':h['request_id'],'authority':'NONE'}
    aad={'handshake_sha256':digest(h),'envelope_sha256':digest(envelope),'direction':'response'}
    return {'schema':SCHEMA,'request_id':h['request_id'],'box':pack(receipt,session_key(secret,h['client_public'],h,'response'),aad)}
def collect(state,response):
    if not state['sealed'] or state['collected']:raise ValueError('INVALID_PENDING')
    exact(response,'schema request_id box');h=state['handshake']
    if response['schema']!=SCHEMA or response['request_id']!=h['request_id']:raise ValueError('REPLY_MISMATCH')
    aad={'handshake_sha256':digest(h),'envelope_sha256':state['envelope_sha256'],'direction':'response'}
    receipt=unpack(response['box'],session_key(state['client_private'],h['server_public'],h,'response'),aad)
    exact(receipt,'result handshake_sha256 envelope_sha256 request_id authority')
    if receipt['handshake_sha256']!=digest(h) or receipt['envelope_sha256']!=state['envelope_sha256'] or receipt['request_id']!=h['request_id'] or receipt['authority']!='NONE':raise ValueError('RECEIPT_MISMATCH')
    state['collected']=True
    return receipt
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None

def infer(key,msg):
    payload={'model':'openrouter/free','messages':[{'role':'user','content':msg}],'max_tokens':2048,'stream':False}
    request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=canon(payload),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=60) as r:status=r.status;raw=r.read(262145)
        if len(raw)>262144:raise ValueError('OVERSIZED')
        d=json.loads(raw);choice=d['choices'][0];text=choice['message']['content']
        ok=isinstance(text,str) and bool(text.strip())
        return {'status':'OK' if ok else 'NO_USABLE_ASSISTANT_TEXT','http_status':status,'actual_model':d.get('model'),'completion_id':d.get('id'),'assistant_text':text if ok else None,'simulated':False}
    except urllib.error.HTTPError as e:return {'status':'PROVIDER_HTTP_ERROR','http_status':e.code,'assistant_text':None,'simulated':False}
    except Exception:return {'status':'PROVIDER_OUTCOME_UNKNOWN','assistant_text':None,'simulated':False}
