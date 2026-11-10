#!/usr/bin/env python3
"""No-secret NEST network probe. An HTTP auth error proves network transport, not inference."""
import datetime
import json
import ssl
import urllib.error
import urllib.request

URL = "https://openrouter.ai/api/v1/chat/completions"
PAYLOAD = {"model": "google/gemma-4-31b-it:free",
           "messages": [{"role": "user", "content": "Hello there!"}],
           "stream": False}

def run():
    request = urllib.request.Request(
        URL, data=json.dumps(PAYLOAD, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    result = {"schema": "nest-egress-probe/1", "requested_model": PAYLOAD["model"],
              "real_http_post_attempted": True, "authenticated": False,
              "live_inference": False,
              "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            result["http_status"] = response.status
            result["outcome"] = "UNEXPECTED_AUTHLESS_SUCCESS_DO_NOT_TREAT_AS_INFERENCE"
            result["http_reachable"] = True
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["http_reachable"] = True
        result["outcome"] = ("HTTP_TRANSPORT_VERIFIED_CREDENTIAL_REQUIRED" if
                             exc.code in (401, 403) else "HTTP_RESPONSE_OTHER")
    except Exception as exc:
        result["http_reachable"] = False
        result["outcome"] = "NETWORK_FAILURE"
        result["error_type"] = type(exc).__name__
    print("NEST_PROBE_RESULT=" + json.dumps(result, sort_keys=True))
    return 0 if result["http_reachable"] else 1

if __name__ == "__main__":
    raise SystemExit(run())
