#!/usr/bin/env python3
"""NEST host-assisted live worker: only one synthetic Hello test is permitted."""
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

URL = "https://openrouter.ai/api/v1/chat/completions"
def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
def digest(x):
    return hashlib.sha256(canon(x)).hexdigest()
def result_for(req, status, *, assistant_text=None, actual_model=None, completion_id=None,
               http_status=None, error_code=None):
    value = {
        "protocol":"nest-mind-result/2","request_id":req["request_id"],
        "request_sha256":digest(req),"requested_model":req["requested_model"],
        "status":status,"execution_context":"github-actions",
        "simulated":False,"assistant_text":assistant_text,
        "actual_model":actual_model,"completion_id":completion_id,
        "http_status":http_status,"error_code":error_code,
        "approved":False,"memory_committed":False
    }
    value["result_sha256"]=digest(value)
    return value
def main():
    req=json.loads(Path("experiments/nest_dual_path/request.json").read_text(encoding="utf-8"))
    if (req.get("protocol")!="nest-mind-transport/2"
        or req.get("request_id")!="b76d74cfecc744c890f3e686839b9c80"
        or req.get("route")!="host-assisted" or req.get("requested_model")!="openrouter/free"
        or req.get("stream") is not False
        or req.get("authorized_external_send") is not True
        or req.get("identity")!="synthetic-transport-test-not-real-engram"
        or req.get("requires_engram_approval") is not True
        or req.get("messages")!=[{"role":"user","content":"Hello there!"}]):
        raise ValueError("Disallowed request")
    key=os.environ.get("OPENROUTER_API_KEY","")
    if not key:
        result=result_for(req,"CREDENTIAL_MISSING")
    else:
        payload={"model":req["requested_model"],"messages":req["messages"],
                 "stream":False,"max_tokens":96}
        r=urllib.request.Request(URL,data=canon(payload),method="POST",headers={
            "Content-Type":"application/json","Authorization":"Bearer "+key})
        try:
            with urllib.request.urlopen(r,timeout=25) as resp:
                code=resp.status
                raw=resp.read(65537)
            if code!=200 or len(raw)>65536:raise ValueError("bad response")
            body=json.loads(raw)
            text=body["choices"][0]["message"]["content"]
            if not isinstance(text,str) or not text.strip() or len(text)>16384:
                raise ValueError("no nonempty assistant content")
            result=result_for(req,"OK",assistant_text=text,actual_model=body.get("model"),
                              completion_id=body.get("id"),http_status=code)
        except urllib.error.HTTPError as err:
            result=result_for(req,"PROVIDER_ERROR",http_status=err.code,
                              error_code="HTTP_"+str(err.code))
        except (ValueError,KeyError,IndexError,TypeError,OSError,TimeoutError) as err:
            result=result_for(req,"NETWORK_ERROR",error_code=type(err).__name__)
    print("NEST_RESULT_BASE64="+base64.urlsafe_b64encode(canon(result)).decode("ascii"))
    print("NEST_RESULT_STATUS="+result["status"])
    print("NEST_RESULT_HTTP_STATUS="+str(result["http_status"]))
if __name__ == "__main__":
    main()
