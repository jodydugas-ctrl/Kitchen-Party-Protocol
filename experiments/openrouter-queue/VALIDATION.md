# Experimental queue validation

Five focused local tests passed: completed request replay suppression, interrupted claim suppression, changed input under a reused ID rejection, missing-secret no-call behavior, and extra request fields rejection. Local fixture results are synthetic.

After explicit owner approval, the workflow was installed and one public live request was submitted via the GitHub file-creation connector. This triggered Actions without workflow dispatch. The runner published a durable claim, called OpenRouter using the repository-managed OPENROUTER_API_KEY, and updated the result. The caller fetched it through GitHub and validated request ID, canonical request SHA256 and request commit.

Live HTTP 200; model liquid/lfm-3-1.7b:free; completion gen-1794356858-1FhHvlDReTQ1LWOILB2i; simulated=false. Run: https://github.com/jodydugas-ctrl/Kitchen-Party-Protocol/actions/runs/42931408492. Request ID 613314798066485a97093d03370040e7. Both secret availability and result-write permission were exercised.

The source is a standalone experimental transport; core KPP runtime and generated release files were not changed. The full core suite, doctor, smoke, and shared export checks were not run for this transport-only branch. Crash replay protection was tested locally, not by interrupting a live inference. No private deployment, high-volume queue, universal host compatibility, exactly-once delivery or cryptographic provider attestation is claimed.
