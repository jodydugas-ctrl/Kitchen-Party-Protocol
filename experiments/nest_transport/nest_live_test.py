#!/usr/bin/env python3
"""Only the fixed Hello smoke test; never logs the OpenRouter credential."""
import hashlib, json, os, re, ssl, sys, urllib.error, urllib.request
from pathlib import Path
MODEL = "google/gemma-4-31b-it:free"
URL = "https://openrouter.ai/api/v1/chat/completions"
def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
def main(path):
    try:
        req = json.loads(Path(path).read_text())
        rid = req.get("request_id")
        if (not isinstance(rid,str) or not re.fullmatch("[a-f0-9]{32}",rid)
            or req.get("protocol") != "nest-mind-transport/v1"
            or req.get("user_authorized_external_send") is not True
            or req.get("requested_model") != MODEL or req.get("stream") is not False
            or req.get("authorized_context",{}).get("messages") !=
                [{"role":"user","content":"Hello there!"}]):
            raise ValueError("Invalid or unauthorized smoke-test request")
        key = os.environ.get("OPENROUTER_API_KEY","")
        if not key:
            print("NEST_LIVE_STATUS="+canon({"request_id":rid,"status":"CREDENTIAL_NOT_PROVISIONED","inference":False}).decode())
            return 0
        payload = {"model":MODEL,"messages":[{"role":"user","content":"Hello there!"}],
                   "stream":False,"max_tokens":100}
        r = urllib.request.Request(URL, data=canon(payload), method="POST",
              headers={"Content-Type":"application/json","Authorization":"Bearer "+key})
        try:
            with urllib.request.urlopen(r, timeout=30, context=ssl.create_default_context()) as resp:
                status,raw=resp.status,resp.read(65537)
        except urllib.error.HTTPError as e:
            print("NEST_LIVE_STATUS="+canon({"request_id":rid,"status":"PROVIDER_HTTP_ERROR",
                  "http_status":e.code,"inference":False}).decode())
            return 1
        if status!=200 or len(raw)>65536: raise ValueError("Bad HTTP response")
        data=json.loads(raw)
        reply=data["choices"][0]["message"]["content"]
        if not isinstance(reply,str) or not reply.strip() or len(reply)>8000:
            raise ValueError("Missing or oversized assistant reply")
        result={"protocol":"nest-mind-result/v1","request_id":rid,
                "status":"EXTERNAL_PROPOSAL_PENDING_ENGRAM_APPROVAL",
                "requested_model":MODEL,"actual_model":data.get("model"),
                "completion_id":data.get("id"),"assistant_text":reply,
                "http_status":status,"approved":False,"memory_committed":False}
        result["sha256"]=hashlib.sha256(canon(result)).hexdigest()
        print("NEST_LIVE_RESULT="+canon(result).decode())
        return 0
    except Exception as e:
        print("NEST_LIVE_STATUS="+canon({"status":"WORKER_ERROR",
              "error_type":type(e).__name__,"inference":False}).decode())
        return 1
if __name__=="__main__":
    raise SystemExit(main(sys.argv[1]))
