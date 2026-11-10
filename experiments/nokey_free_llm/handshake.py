#!/usr/bin/env python3
"""One-time recipient key generation; wrapping key is a GitHub Actions secret.
Never reveal actual Actions secret or private X25519 key.
"""
import os, json, base64, hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

def enc(x):
    return base64.urlsafe_b64encode(x).decode("ascii")
def main():
    secret=os.environ.get("OPENROUTER_API_KEY","").encode("utf8")
    if len(secret)<30:
        raise ValueError("A suitably long Actions secret is required")
    receiver=X25519PrivateKey.generate()
    priv=receiver.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
    pub=receiver.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    salt=os.urandom(16)
    nonce=os.urandom(12)
    wrap=HKDF(algorithm=hashes.SHA256(),length=32,salt=salt,info=b"kpp-onetime-x25519-private-wrap-v1").derive(secret)
    cipher=AESGCM(wrap).encrypt(nonce,priv,b"kpp-recipient-private-key-v1")
    outcome={"protocol":"kpp.key-handoff-recipient/1",
             "public_key":enc(pub),"wrap_salt":enc(salt),
             "wrap_nonce":enc(nonce),"wrapped_private":enc(cipher),
             "key_stored_in":"GH_ACTIONS_SECRET",
             "private_key_exposed":False}
    print("KPP_HANDOFF_RECIPIENT_B64="+enc(json.dumps(outcome,sort_keys=True,separators=(",",":")).encode()))
    print("KPP_HANDOFF_STATUS=READY")
if __name__=="__main__":main()
