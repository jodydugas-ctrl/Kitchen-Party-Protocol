#!/usr/bin/env python3
"""KPP sealed queue experiment, protocol v1.

Public GitHub is a ciphertext *carrier*, not a private repository. Plaintext
requests and replies remain in caller and trusted runner memory. The runner
uses an existing Actions OPENROUTER_API_KEY, never carried in repository data.

Experimental limitation: the recipient's encryption/signing keys are derived
with domain-separated HKDF from the OpenRouter secret. Rotating that secret
invalidates pending mail; a compromised secret compromises old mail. A separate
KPP_RELAY_WRAP_SECRET would improve isolation for production.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

REPO = 'jodydugas-ctrl/Kitchen-Party-Protocol'
BRANCH = 'kpp-sealed-queue-experiment'
SCHEMA_RECIPIENT = 'kpp.sealed-queue-recipient/1'
SCHEMA_REQUEST = 'kpp.sealed-queue-request/1'
SCHEMA_PENDING = 'kpp.sealed-queue-pending/1'
SCHEMA_RESULT = 'kpp.sealed-queue-result/1'
MAX_MESSAGE = 4000


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(x):
    return hashlib.sha256(canon(x)).hexdigest()


def b64e(b):
    return base64.urlsafe_b64encode(b).decode('ascii').rstrip('=')


def b64d(s):
    if not isinstance(s, str) or not s or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}',s):
        raise ValueError('INVALID_B64')
    return base64.urlsafe_b64decode(s+'='*(-len(s)%4))


def raw_public(k):
    return k.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def raw_private(k):
    return k.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())


def hkdf(value,salt,info):
    return HKDF(algorithm=hashes.SHA256(),length=32,salt=salt,info=info).derive(value)


def valid_id(rid):
    if not isinstance(rid,str) or not re.fullmatch(r'[0-9a-f]{32}',rid):
        raise ValueError('INVALID_REQUEST_ID')
    return rid


def derived_receiver(secret):
    """Derive stable per-branch recipient keys only inside authorized runner."""
    if not isinstance(secret,str) or len(secret)<20:
        raise ValueError('RUNNER_CREDENTIAL_UNAVAILABLE')
    salt=hashlib.sha256((REPO+'|'+BRANCH+'|kpp-sealed-v1').encode()).digest()
    k=secret.encode('utf-8')
    recv=X25519PrivateKey.from_private_bytes(hkdf(k,salt,b'kpp-sealed-queue-recipient-x25519-v1'))
    signer=Ed25519PrivateKey.from_private_bytes(hkdf(k,salt,b'kpp-sealed-queue-receipt-ed25519-v1'))
    pub={'schema':SCHEMA_RECIPIENT,'receiver_public':b64e(raw_public(recv.public_key())),
         'signer_public':b64e(raw_public(signer.public_key()))}
    pub['key_id']=hashlib.sha256(canon(pub)).hexdigest()[:32]
    return recv,signer,pub


def validate_recipient(p):
    if not isinstance(p,dict) or set(p)!={'schema','receiver_public','signer_public','key_id'} or p['schema']!=SCHEMA_RECIPIENT:
        raise ValueError('INVALID_RECIPIENT')
    if len(b64d(p['receiver_public']))!=32 or len(b64d(p['signer_public']))!=32:
        raise ValueError('INVALID_RECIPIENT_KEY')
    check={k:p[k] for k in ('schema','receiver_public','signer_public')}
    if p['key_id']!=hashlib.sha256(canon(check)).hexdigest()[:32]:
        raise ValueError('INVALID_KEY_ID')
    return p


def seal(recipient,message,*,now=None):
    validate_recipient(recipient)
    if not isinstance(message,str) or not message.strip() or len(message)>MAX_MESSAGE:
        raise ValueError('INVALID_MESSAGE')
    rid=uuid.uuid4().hex
    sender=X25519PrivateKey.generate()
    shared=sender.exchange(X25519PublicKey.from_public_bytes(b64d(recipient['receiver_public'])))
    salt,nonce=os.urandom(16),os.urandom(12)
    payload={'schema':'kpp.sealed-queue-payload/1','request_id':rid,
             'message':message,'model':'openrouter/free','created_at':int(now or time.time())}
    aeskey=hkdf(shared,salt,b'kpp-sealed-queue-request-v1:'+rid.encode())
    cipher=AESGCM(aeskey).encrypt(nonce,canon(payload),rid.encode())
    envelope={'schema':SCHEMA_REQUEST,'request_id':rid,'recipient_key_id':recipient['key_id'],
              'sender_public':b64e(raw_public(sender.public_key())),
              'salt':b64e(salt),'nonce':b64e(nonce),'ciphertext':b64e(cipher)}
    pending={'schema':SCHEMA_PENDING,'request_id':rid,'request_sha256':digest(envelope),
             'recipient':recipient,'sender_private':b64e(raw_private(sender)),
             'collected':False,'request_commit':None}
    return envelope,pending


def open_envelope(recv,recipient,envelope):
    validate_recipient(recipient)
    if not isinstance(envelope,dict) or set(envelope)!={'schema','request_id','recipient_key_id','sender_public','salt','nonce','ciphertext'}:
        raise ValueError('INVALID_ENVELOPE')
    if envelope['schema']!=SCHEMA_REQUEST or envelope['recipient_key_id']!=recipient['key_id']:
        raise ValueError('WRONG_RECIPIENT')
    rid=valid_id(envelope['request_id'])
    if len(canon(envelope))>15000 or len(b64d(envelope['sender_public']))!=32 or len(b64d(envelope['salt']))!=16 or len(b64d(envelope['nonce']))!=12:
        raise ValueError('INVALID_ENVELOPE_FIELDS')
    shared=recv.exchange(X25519PublicKey.from_public_bytes(b64d(envelope['sender_public'])))
    key=hkdf(shared,b64d(envelope['salt']),b'kpp-sealed-queue-request-v1:'+rid.encode())
    plain=AESGCM(key).decrypt(b64d(envelope['nonce']),b64d(envelope['ciphertext']),rid.encode())
    payload=json.loads(plain)
    if not isinstance(payload,dict) or set(payload)!={'schema','request_id','message','model','created_at'}:
        raise ValueError('INVALID_PAYLOAD')
    if payload['schema']!='kpp.sealed-queue-payload/1' or payload['request_id']!=rid or payload['model']!='openrouter/free':
        raise ValueError('INVALID_REQUEST_CONTRACT')
    if not isinstance(payload['created_at'],int) or abs(time.time()-payload['created_at'])>3600:
        raise ValueError('STALE_REQUEST')
    if not isinstance(payload['message'],str) or not payload['message'].strip() or len(payload['message'])>MAX_MESSAGE:
        raise ValueError('INVALID_MESSAGE')
    return payload


def seal_result(recv,signer,recipient,envelope,provider_data,*,run_id,request_commit):
    rid=valid_id(envelope['request_id'])
    shared=recv.exchange(X25519PublicKey.from_public_bytes(b64d(envelope['sender_public'])))
    salt,nonce=os.urandom(16),os.urandom(12)
    key=hkdf(shared,salt,b'kpp-sealed-queue-result-v1:'+rid.encode())
    cipher=AESGCM(key).encrypt(nonce,canon(provider_data),rid.encode())
    unsigned={'schema':SCHEMA_RESULT,'request_id':rid,'request_sha256':digest(envelope),
              'recipient_key_id':recipient['key_id'],'status':'ENCRYPTED_RESULT',
              'run_id':str(run_id),'request_commit':str(request_commit),
              'salt':b64e(salt),'nonce':b64e(nonce),'ciphertext':b64e(cipher)}
    unsigned['signature']=b64e(signer.sign(canon(unsigned)))
    return unsigned


def collect(pending,result):
    if pending.get('schema')!=SCHEMA_PENDING or pending.get('collected') is not False:
        raise ValueError('INVALID_PENDING')
    if not isinstance(result,dict) or set(result)!={'schema','request_id','request_sha256','recipient_key_id','status','run_id','request_commit','salt','nonce','ciphertext','signature'}:
        raise ValueError('INVALID_RESULT')
    if result['schema']!=SCHEMA_RESULT or result['status']!='ENCRYPTED_RESULT' or result['request_id']!=pending['request_id']:
        raise ValueError('RESULT_MISMATCH')
    if result['request_sha256']!=pending['request_sha256'] or result['recipient_key_id']!=pending['recipient']['key_id']:
        raise ValueError('RESULT_NOT_BOUND')
    if pending.get('request_commit') and result['request_commit']!=pending['request_commit']:
        raise ValueError('RESULT_COMMIT_MISMATCH')
    validated=validate_recipient(pending['recipient'])
    unsigned={k:v for k,v in result.items() if k!='signature'}
    verifier=Ed25519PublicKey.from_public_bytes(b64d(validated['signer_public']))
    verifier.verify(b64d(result['signature']),canon(unsigned))
    sender=X25519PrivateKey.from_private_bytes(b64d(pending['sender_private']))
    shared=sender.exchange(X25519PublicKey.from_public_bytes(b64d(validated['receiver_public'])))
    key=hkdf(shared,b64d(result['salt']),b'kpp-sealed-queue-result-v1:'+result['request_id'].encode())
    provider=json.loads(AESGCM(key).decrypt(b64d(result['nonce']),b64d(result['ciphertext']),result['request_id'].encode()))
    if provider.get('schema')!='kpp.provider-result/1' or provider.get('simulated') is not False:
        raise ValueError('INVALID_PROVIDER_DATA')
    return provider


def save(path,value):
    p=Path(path)
    with p.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write('\n')


def cli():
    p=argparse.ArgumentParser(description='KPP encrypted GitHub queue client, never prints secrets')
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('seal');s.add_argument('--recipient',required=True);s.add_argument('--message',required=True);s.add_argument('--out',required=True);s.add_argument('--pending',required=True)
    c=sub.add_parser('collect');c.add_argument('--pending',required=True);c.add_argument('--result',required=True)
    args=p.parse_args()
    if args.cmd=='seal':
        req,pending=seal(json.loads(Path(args.recipient).read_text()),args.message)
        save(args.out,req);save(args.pending,pending)
        print(json.dumps({'status':'SEALED','request_id':req['request_id'],'request_sha256':digest(req),'public_message':False}))
    elif args.cmd=='collect':
        pth=Path(args.pending);pending=json.loads(pth.read_text())
        data=collect(pending,json.loads(Path(args.result).read_text()))
        pending['collected']=True
        tmp=pth.with_suffix('.consumed')
        if tmp.exists():raise FileExistsError('pending marker exists')
        tmp.write_text(json.dumps(pending,indent=2,sort_keys=True)+'\n')
        tmp.replace(pth)
        print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':cli()
