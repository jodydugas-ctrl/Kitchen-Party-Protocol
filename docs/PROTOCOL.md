# Shared system

KPP is the primary maintained protocol project; MantleOS is an associated project using the same implementation. [SYSTEMS.md](../SYSTEMS.md) defines the same Anchor and CELL models in both distributions. Recipe obligations are Neutral Anchor applications, with no separate singularities.

# Current contracts

## Recipe: kpp.recipe/3

Required: schema, id, goal, mode (composition/chase/hybrid/transformation), tissue (anchor/python/javascript/mixed/unspecified), integer fidelity 1..32, described target, ingredients, nonempty anchors, product_kind (biosoftware/bioagent/appai/conventional), delivery_mode (artifact/progressive-web), and boolean capabilities agent/mind/mantleos_splice.

BioAgent requires agent; AppAI requires splice. Labels grant no effects. Anchor dependencies form a DAG. Transformation preserve/may_change are disjoint; every preserved property maps to mandatory Anchors. Reflex declarations join the same graph.

Progressive-web requires JavaScript/mixed tissue, preview.kind=progressive-web, state_profile=json-body/1, and exactly index.html/base.js/style.css assets under previews/ with raw-byte pins. Artifact delivery has no preview. Optional reference_gui declares source_root, inventory path/canonical pin and coverage_anchor. Only current contracts are read.

## Workspace: kpp.workspace/3

new validates recipe, Pantry and pins before publishing. recipe.json and ingredient-labels.json are fixed. state owns workspace_id, revision, phase, enabled module records, acceptance and GUI inventory/evidence. load refuses changed recipe, seeds, shipped runtime, modules or inventory.

install admits immutable reviewed JavaScript with existing enabled dependencies. module-disable [--cascade] withdraws resources; module-enable restores retained source. Active/source changes clear acceptance and return to BUILDING. Native exclusive writer locking serializes mutations. recover-writer --reviewed proves no active writer and validates committed pins; partial staging is never adopted.

serve binds loopback. preview-export --out NEW.zip [--browser-state CHECKPOINT.json] carries exact pinned sources; preview-import --bundle FILE --output UNUSED restores without execution. Explicit checkpoints must match recipe/profile/source fingerprint. Incoming approval is cleared and new workspace identity makes carried GUI observations stale. See PREVIEW-RECOVERY.md.

## Evidence

status/graph/coverage/next/handoff derive from one Functional Graph. gui-matrix separates discovery, accounting, presence, functionality, testing and acceptance. Observations supply no approval. accept records explicit manual Baker attestation with fresh dependency checks; gui-accept binds reviewed captures. complete requires all mandatory Anchors/preservation obligations with current evidence.

`build-step --workspace DIR` derives `mantle.kpp-build-step/1` from those same
requirements and dependencies. Its next obligation includes the actual statement
and test; it excludes unrelated optional work. The bounded host driver
`mantleos.kpp.build.run` opens/checks the useful preview before refinement, re-reads
the graph after every cycle, rejects recipe drift and retains unsatisfied work on
budget, blocking or review stops. It never calls accept/complete. A caller's host
receipt is not independent proof of rendering and cannot be fabricated by a model.

Completion publishes a pinned receipt before COMPLETE state. Content-addressed prior receipts and full approval/invalidation records retain provenance. Missing/changed current receipts invalidate COMPLETE. Receipt scope is this recipe's obligations, not universal equivalence.

Executed tests require test --execute --reviewed --workspace WS --candidate DIR --suite DIR --out NEW.json. kpp.reflex-test-report/2 records EXPLICIT_REVIEWED_LOCAL_PYTHON; there is no sandbox. test-check rechecks pins; test-accept --baker LABEL is separate. Changed source/tests/reports invalidate evidence.

Anchor execution uses the shared MantleOS interpreter, including EMIT_TEXT/0.2 literals and NOTEPAD_LLM/1.3 explicit JSON commands; bridge-python writes syntax-checked text without executing it. Unsupported profiles fail. Portable Reflex and preview use the same strict bounded archive handling. Hashes provide integrity, never authentication.
