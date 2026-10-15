# Project preparation verification

New local execution on 15 October 2026, Windows x64, CPython 3.14.2:

| Check | Result |
| --- | --- |
| Focused project export regressions | 3 passed |
| Complete KPP suite | 194 run: 190 passed, 4 skipped |
| Doctor and adaptive example | Passed |
| JavaScript syntax | 6 scripts passed |
| Shared source and exact release inventory | Passed |
| Wheel and source distribution | Built successfully with provisioned setuptools 80.9.0 and build 1.3.0 |
| Wheel installed in a fresh environment | Doctor and a new Notepad bake passed outside the checkout |
| Source distribution contents | Recipes, tests, CI, component licenses and reproducible exporter present |
| KPP/MantleOS common source | All 230 implementation files byte-identical at project preparation |

The four skips concern unavailable Windows symlink creation privileges. The
export regressions check regeneration from KPP itself, scoped package metadata,
and refusal of stale generated views or unrepresented source. Git preserves
inherited line endings so that platform checkout does not invalidate byte pins.

The four optional real browser probes, live model/cloud/provider integrations,
native reference parity and other local Python/platform combinations were not
rerun for project preparation. The CI matrix declares Windows/Linux and Python
3.11–3.14 checks; its configuration alone is not an observed hosted result.
Historical Canvas and unification records keep their original scope.
No test grants product Baker acceptance. No package registry release is made.
