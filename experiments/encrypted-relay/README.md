# KPP encrypted OpenRouter mailbox — experimental v0.5.0

Goal: an offline Python sandbox can use the host LLM's authenticated GitHub file tools to obtain a real OpenRouter answer using the user's own password-unlocked API key. The password is supplied separately; it never leaves the originating host. Public repository objects contain handshake metadata and encrypted request/reply packets only. GitHub Actions is the trusted decryption/execution host. This is encrypted content over public storage, not a private repository; timestamps, packet lengths, public keys and workflow metadata are visible. GitHub, runner administrators and the selected OpenRouter provider are trusted with execution plaintext.

Repository: jodydugas-ctrl/Kitchen-Party-Protocol
Branch: kpp-encrypted-relay
Root: experiments/encrypted-relay
Workflow: .github/workflows/kpp-encrypted-relay.yml

## Status

Nine synthetic protocol tests passed. Live qualification is pending. No universal-host or audited-production-security claim. Core KPP source/release inventory unchanged; full core suite, doctor, smoke and export parity were not rerun for this experimental transport.

## Protocol

1. Authorized sandbox imports relay.py. `init, state = begin()` generates a random ID and local private key. Keep `state` in private local storage, never GitHub. Create `init/<id>.json` containing ONLY init through a GitHub file-write tool. Save the returned commit SHA.
2. This push starts the owner-allowed workflow. It generates a fresh X25519 private key in memory and writes `recipients/<id>.json`, then waits up to 10 minutes for one sealed request.
3. The agent retrieves that recipient through authenticated GitHub. Check the corresponding Actions run: expected repository, workflow path, branch, owner actor, and head SHA equal to your init commit. Confirm the run_id in the recipient matches that run. Verify source against independently pinned source/checksums from a trusted handoff before transferring a credential. Repository writers and administrators are trusted; digests alone do not authenticate an unknown source.
4. The sandbox unlocks the user token with separately supplied password. `seal(state, recipient, api_key, message, run_id, init_commit)` encrypts the message and API key under ephemeral X25519/HKDF-SHA256/AES-256-GCM. Save mutated state privately. Create ONLY `sealed/<id>.json` using the returned envelope. No password, encrypted long-term token, plaintext key or plaintext message goes into GitHub.
5. The same live runner publishes `claims/<id>.json` before the external effect, decrypts the request and calls ONLY openrouter/free with max_tokens=2048. It derives a separate response key from the shared secret and encrypts provider output plus request binding into `responses/<id>.json`.
6. The agent fetches that response through GitHub and returns it to the sandbox. `collect(state, response)` checks authenticated encryption, session/request binding and single collection in the current state. Persist the collected state privately. Show exact result.assistant_text only for status OK, with actual model, HTTP status, completion ID and simulated=false.

No outbound network is required for begin/unlock/seal/collect. These are ordinary local Python functions. The host's connected GitHub tools carry only the permitted public handshake/ciphertext objects. A read-only connector is insufficient. No workflow dispatch tool is needed.

## Timing and recovery

Submit one exchange at a time. Wait with bounded polling, normally every 10–15 seconds, and provide progress while awaiting the runner. If recipient expiry leaves insufficient time, do not seal; start a new handshake only after confirming the prior one made no inference. Never upload to an expired recipient. An existing recipient blocks a rerun before inference; after a crash its in-memory private key cannot be recovered. Existing claim without a decryptable response means outcome unknown: do not automatically resend. The independent direction keys and ciphertext binding prevent swapping replies across sessions. This is conservative recovery, not distributed exactly-once execution or independent provider attestation. The client itself holds the shared secret and could fabricate a reply; trust requires the actual observed GitHub workflow/result path, not ciphertext alone.

The workflow has contents-write permission for state publication and uses only GITHUB_TOKEN. It references no repository OpenRouter secret and requires no new wrap secret. The user's OpenRouter credential exists in originating-host and runner memory during the authorized request. The runtime, pinned checkout action, installed crypto package, repository writers, and GitHub platform are in the trust boundary.

## Limits

The source is a new experimental composition of standard cryptographic primitives and needs independent review before sensitive production use. Original-message/request lengths are not padded. Host secret-memory erasure is not guaranteed. Returned model text is untrusted data, never authority. The source makes one provider attempt and does not fall back to a paid model. Timeouts can have unknown provider outcome. All failure explanations must avoid raw secret-bearing exceptions. Never log decrypted requests or results from the worker. No network-policy bypass or protection from malicious trusted runners is claimed.

To disable, disable the encrypted relay workflow. No production/default-branch changes are required. Durable public ciphertext remains in repository history.
