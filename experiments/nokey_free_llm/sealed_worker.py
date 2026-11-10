#!/usr/bin/env python3
"""Decrypt one-time sealed NoKey credential and call OpenRouter free model.
Uses the pre-existing GH Actions secret only to unwrap the ephemeral receiver.
Never prints plaintext tokens, passwords, HTTP Authorization or encrypted
key material as decrypted plaintext.
"""
import base64, json, os, urllib.request, urllib.error
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes

def dec(s):
    return base64.urlsafe_b64decode(s+"="*(-len(s)%4))
def enc(s):
    return base64.urlsafe_b64encode(s).decode("ascii")
def canonical(o):
    return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def main():
    reply={"schema":"kpp.live-nokey-openrouter-result/1",
           "request_id":"8be92f1477f3808958b5836f4c97ac72",
           "status":"INIT","http_status":None,"actual_model":None,
           "completion_id":None,"assistant_text":None,
           "credential_from_nokey_envelope":False,"inference":False}
    try:
        raw=Path("experiments/nokey_free_llm/sealed_request.json").read_bytes()
        if len(raw)>8192: raise ValueError("Envelope oversized")
        doc=json.loads(raw)
        if doc.get("schema")!="kpp.sealed-credential-envelope/1" or doc.get("request_id")!=reply["request_id"]:
            raise ValueError("Invalid envelope")
        recipient=doc["recipient"]
        if recipient.get("protocol")!="kpp.key-handoff-recipient/1" or recipient.get("private_key_exposed") is not False:
            raise ValueError("Invalid recipient")
        secret=os.environ.get("OPENROUTER_API_KEY","")
        if len(secret)<30: raise ValueError("Missing recipient-unwrapping secret")
        wrap=HKDF(algorithm=hashes.SHA256(),length=32,salt=dec(recipient["wrap_salt"]),
                  info=b"kpp-onetime-x25519-private-wrap-v1").derive(secret.encode("utf-8"))
        private= AESGCM(wrap).decrypt(dec(recipient["wrap_nonce"]),dec(recipient["wrapped_private"]),
                                      b"kpp-recipient-private-key-v1")
        recipient_key=X25519PrivateKey.from_private_bytes(private)
        sender=X25519PublicKey.from_public_bytes(dec(doc["sender_public"]))
        shared=recipient_key.exchange(sender)
        key=HKDF(algorithm=hashes.SHA256(),length=32,salt=dec(doc["transfer_salt"]),
                 info=b"kpp-onetime-credential-transfer-v1").derive(shared)
        plaintext=AESGCM(key).decrypt(dec(doc["transfer_nonce"]),dec(doc["sealed_payload"]),
                                     b"kpp-sealed-request-v1")
        request=json.loads(plaintext)
        if (set(request)!={"schema","request_id","message","model","max_tokens","api_key"}
            or request["schema"]!="kpp.sealed-exchange-request/1"
            or request["request_id"]!=doc["request_id"]
            or request["message"]!="Hi.. how are you?"
            or request["model"]!="openrouter/free"
            or request["max_tokens"]!=180
            or not isinstance(request["api_key"],str)
            or len(request["api_key"])<30):
            raise ValueError("Invalid decrypted message")
        reply["credential_from_nokey_envelope"]=True
        api_key=request["api_key"]
        payload={"model":"openrouter/free",
                 "messages":[{"role":"user","content":"Hi.. how are you?"}],
                 "stream":False,"max_tokens":180}
        call=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
            method="POST",data=canonical(payload),
            headers={"Content-Type":"application/json","Authorization":"Bearer "+api_key})
        try:
            with urllib.request.urlopen(call,timeout=35) as response:
                reply["http_status"]=response.status
                body=response.read(65537)
            if len(body)>65536: raise ValueError("Response too large")
            data=json.loads(body)
            message=data["choices"][0]["message"]["content"]
            if not isinstance(message,str) or not message.strip() or len(message)>16384:
                raise ValueError("Invalid returned completion")
            reply.update(status="OK",inference=True,actual_model=data.get("model"),
                         completion_id=data.get("id"),assistant_text=message)
        except urllib.error.HTTPError as error:
            reply.update(status="OPENROUTER_HTTP_ERROR",http_status=error.code,inference=False)
        except Exception as error:
            reply.update(status="OPENROUTER_TRANSPORT_ERROR",
                         exception_type=type(error).__name__,inference=False)
    except Exception as error:
        reply.update(status="HANDOFF_ERROR",exception_type=type(error).__name__)
    print("KPP_ACTUAL_NOKEY_RESULT_B64="+enc(canonical(reply)))
    print("KPP_ACTUAL_NOKEY_STATUS="+reply["status"])
    print("KPP_ACTUAL_NOKEY_HTTP="+str(reply["http_status"]))
    print("KPP_ACTUAL_NOKEY_CREDENTIAL_RECEIVED="+str(reply["credential_from_nokey_envelope"]))
if __name__=="__main__":main()
