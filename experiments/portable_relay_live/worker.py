#!/usr/bin/env python3
"""KPP public, no-secret protocol interop test executed on a remote GitHub runner."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import re

KEY = b"PUBLIC-TEST-KEY-NO-SECURITY-ONLY-RELAY-DEMO-2026"
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def main():
    raw=Path("experiments/portable_relay_live/request.json").read_bytes()
    if len(raw)>24576: raise ValueError("Request too large")
    req=json.loads(raw)
    if (set(req)!={"schema","request_id","service","route","payload","max_reply_bytes","authority"}
        or req["schema"]!="kpp.exchange-request/1"
        or not re.fullmatch(r"[0-9a-f]{32}",req["request_id"])
        or req["request_id"]!="b40b4d7e216e40aabb26711bc7c29dfa"
        or req["service"]!="arithmetic.sum" or req["route"]!="host-courier"
        or req["authority"]!="NONE" or req["max_reply_bytes"]!=65536
        or digest(req)!="2e76261d532283d2d4b8d7c4989e8e9bec8650414939d4d5ba9643c976457af4"):
        raise ValueError("Unexpected request")
    args=req["payload"]
    if set(args)!={"values","challenge"} or type(args["values"])!=list or len(args["values"])!=3 or any(type(x)!=int for x in args["values"]):
        raise ValueError("Invalid calculator request")
    payload={"total":sum(args["values"]),"challenge":args["challenge"]}
    receipt={"schema":"kpp.exchange-receipt/1","request_id":req["request_id"],
             "request_sha256":digest(req),"service":req["service"],"status":"OK",
             "payload":payload,"worker_id":"github-calculator","authority":"NONE"}
    receipt["receipt_sha256"]=digest(receipt)
    receipt["hmac_sha256"]=hmac.new(KEY,bytes.fromhex(receipt["receipt_sha256"]),hashlib.sha256).hexdigest()
    print("KPP_RELAY_RECEIPT_B64="+base64.urlsafe_b64encode(canonical(receipt)).decode("ascii"))
    print("KPP_RELAY_WORKER_TOTAL="+str(payload["total"]))
    print("KPP_RELAY_WORKER_REQUEST="+req["request_id"])
    print("KPP_RELAY_LIVE_REMOTE_EXECUTION=GITHUB_ACTIONS_RUNNER")
if __name__=="__main__":
    main()
