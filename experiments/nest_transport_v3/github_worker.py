#!/usr/bin/env python3
"""Pinned synthetic Journal-shaped request. No credentials printed."""
import json, hashlib, os, base64, urllib.request, urllib.error
from pathlib import Path
def canon(o): return json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")
def sha(o): return hashlib.sha256(canon(o)).hexdigest()
def main():
    req=json.loads(Path("experiments/nest_transport_v3/request.json").read_text(encoding="utf-8"))
    allowed=("1d76860726cd4a5cb5da1b02789635ad",
             "8fc88f77f8d4ae4422c93135eefda9ea9f5db8d483ea0b92af865613c5640423")
    if (req.get("request_id")!=allowed[0] or sha(req)!=allowed[1]
        or req.get("model")!="openrouter/free" or req.get("stream") is not False):
        raise ValueError("Fixed synthetic test does not match approved request")
    result={"protocol":"nest-mind-receipt/3","request_id":req["request_id"],
      "request_sha256":sha(req),"requested_model":req["model"],"status":None,
      "assistant_text":None,"actual_model":None,"completion_id":None,
      "http_status":None,"execution_context":"github-actions",
      "simulated":False,"error_code":None,"approved":False,"memory_committed":False}
    key=os.environ.get("OPENROUTER_API_KEY")
    if not key:
        result["status"]="CREDENTIAL_MISSING"
    else:
        payload={"model":req["model"],"messages":req["messages"],
                 "stream":False,"max_tokens":req["max_tokens"]}
        call=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
            data=canon(payload),method="POST",headers={
                "Content-Type":"application/json","Authorization":"Bearer "+key})
        try:
            with urllib.request.urlopen(call,timeout=30) as resp:
                http=resp.status;raw=resp.read(65537)
            if http!=200 or len(raw)>65536:raise ValueError("Bad HTTP body")
            body=json.loads(raw)
            content=body["choices"][0]["message"]["content"]
            if not isinstance(content,str) or not content.strip():raise ValueError("No model text")
            result.update(status="OK",assistant_text=content,actual_model=body.get("model"),
                          completion_id=body.get("id"),http_status=http)
        except urllib.error.HTTPError as error:
            result.update(status="PROVIDER_ERROR",http_status=error.code,error_code="HTTP_"+str(error.code))
        except Exception as error:
            result.update(status="NETWORK_ERROR",error_code=type(error).__name__)
    result["receipt_sha256"]=sha(result)
    print("NEST_V3_RECEIPT_BASE64="+base64.urlsafe_b64encode(canon(result)).decode("ascii"))
    print("NEST_V3_STATUS="+result["status"])
    print("NEST_V3_HTTP="+str(result["http_status"]))
if __name__=="__main__":main()
