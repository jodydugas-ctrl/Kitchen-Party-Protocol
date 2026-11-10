#!/usr/bin/env python3
"""NoKey credential equality gate + bounded OpenRouter free-model smoke.
Does not print the API key, ciphertext, plaintext or decryption password.
"""
import base64
import hmac
import hashlib
import json
import os
import urllib.request
import urllib.error

CHALLENGE = "kpp-live-key-match-20261110-960bb4c27a47533e690865560ed7f3d7"
EXPECT_PROOF = "0797cf53396914b92172fcf8c166c3293b9adeaee7938bf64e0b72f99cd6d946"
PROMPT = "Hi.. how are you?"
MODEL = "openrouter/free"

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def main():
    key = os.environ.get("OPENROUTER_API_KEY","")
    result = {
        "schema":"kpp.remote-credential-probe/1",
        "challenge":CHALLENGE,
        "model_requested":MODEL,
        "request_message":PROMPT,
        "key_decrypted_locally_using_NoKey":True,
        "github_secret_matches_decrypted_token":False,
        "real_inference":False,
        "status":None
    }
    if not key:
        result["status"]="MISSING_ACTIONS_SECRET"
    else:
        actual = hmac.new(key.encode("utf-8"),CHALLENGE.encode("utf-8"),hashlib.sha256).hexdigest()
        matches = hmac.compare_digest(actual, EXPECT_PROOF)
        result["github_secret_matches_decrypted_token"] = matches
        if not matches:
            result["status"]="ACTIONS_SECRET_DIFFERS_FROM_NOKEY_TOKEN"
        else:
            payload={"model":MODEL,"messages":[{"role":"user","content":PROMPT}],
                     "stream":False,"max_tokens":150}
            req=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                method="POST",data=canonical(payload),
                headers={"Content-Type":"application/json",
                         "Authorization":"Bearer "+key})
            try:
                with urllib.request.urlopen(req,timeout=35) as response:
                    result["http_status"]=response.status
                    data=response.read(65537)
                if len(data)>65536:raise ValueError("Response exceeds bound")
                obj=json.loads(data)
                content=obj["choices"][0]["message"]["content"]
                if not isinstance(content,str) or not content.strip() or len(content)>16384:
                    raise ValueError("Response missing usable text")
                result.update(status="OK",real_inference=True,actual_model=obj.get("model"),
                              completion_id=obj.get("id"),assistant_text=content)
            except urllib.error.HTTPError as ex:
                result.update(status="OPENROUTER_HTTP_ERROR",http_status=ex.code)
            except Exception as ex:
                result.update(status="WORKER_ERROR",exception_type=type(ex).__name__)
    # Never print API key, password, ciphertext or Authorization header
    print("KPP_NOKEY_RESULT_BASE64="+base64.urlsafe_b64encode(canonical(result)).decode("ascii"))
    print("KPP_NOKEY_STATUS="+str(result["status"]))
    print("KPP_NOKEY_MATCH="+str(result["github_secret_matches_decrypted_token"]))
if __name__=="__main__":main()
