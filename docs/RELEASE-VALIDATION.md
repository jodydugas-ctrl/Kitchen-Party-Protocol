# Verification

Run focused tests, then from the extracted root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
python -m kpp doctor
python examples/adaptive-reflex/smoke.py
python tools/verify_release.py
```

Restricted hosts need writable TEMP/TMP and permitted loopback for HTTP tests. Symlink creation checks explicitly skip if privilege is unavailable; report skips. Do not turn blocked checks into passes.

validate_release.py --json-out OUTSIDE_SOURCE.json records actual outcomes/counts/environment. Optional --browser runs all four real probes: notes, calculator, managed recovery/transport and GUI observations/matrix. It needs already available Playwright/Chromium; --chromium selects a local executable. Optional Node checks syntax. These tools are developer instrumentation; nothing is installed automatically.

The shared runtime supports Python 3.11–3.14; versions not actually exercised remain untested. Local Python versions are recorded separately; definitions for hosted CI do not establish an observed run. Pixel-twin synthetic comparison does not establish native Qt or Notepad Next parity. Probe/test approval labels are synthetic and confer no actual product acceptance.

Regenerate SHA256SUMS.json over exact release source (excluding itself/development outputs), package, clean-extract, verify inventory and rerun checks. Current evidence is unsigned observation, never Baker acceptance.
