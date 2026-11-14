# Anchor Decision Boost (`anchor-decision-boost`)

`anchor-decision-boost` is a Pantry ingredient (`kpp.ingredient/1`) for accelerating Anchor Code **encoding** (source, scan reports, or specifications -> `anchor.design/1`, universal Molecule entries, and `kpp.recipe/4` obligations) and **decoding/triage** (incoming stimuli -> `BlackHole` -> `WhiteHole` -> `Neutral` routing verdicts) without compromising KPP's model-neutral, deterministic foundation.

## Anchor Coding Philosophy & Advisory Recommendation

**Anchor Coding** is the practice of coding *around set Anchors*: like a river flowing around stones, the final artifact is a byproduct of execution flowing around invariant `BlackHole` (ingress), `WhiteHole` (boundary guard), and `Neutral` (state & core relationship) boundaries. Whenever Anchor artifacts or bindings appear in a recipe, that recipe is using the Anchor Coding style.

Because closed-ended decision batching fits every Anchor Coding system, KPP surfaces `anchor-decision-boost` as `RECOMMENDED_OPTIONAL` (**Default OFF**, never mandatory, preserving zero reliance on any LLM) whenever any Anchor signal is present (`kpp.recipe/3`, `anchor_binding: "shared-neutral"`, `tissue: "anchor"`, `anchor_design`, component language `"anchor"`, an Anchor Pantry ingredient, or typed Anchor obligations). Specifically, if the operator has an **OpenRouter API key** (common across KPP recipes using `openrouter-mind`), enabling Decider speedup defaults to OpenRouter while also letting you select Google Gemini. This advisory status appears automatically across:

- `kpp language-plan` (`anchor_decision_boost` and `recommended_optional_ingredients`)
- `kpp pantry-fit` (`recommended_optional`)
- `kpp build-step` and `kpp handoff` (`implementation.anchor_decision_boost` and the Handoff Contract block)
- `kpp anchor-decision status --recipe FILE` (`involves_anchor_coding`, `anchor_signals`, `default_mode`, `default_boost_provider`, `supported_boost_providers`, `openrouter_mind_present`, `recommendation`)

## Why Closed-Ended Decision Batching Fits Anchor Code

Every Anchor application in MantleOS and KPP operates over a small, fixed canonical schema:

- **Three polarities**: `BlackHole` (input ingress), `WhiteHole` (boundary guard), `Neutral` (state & core relationship owner).
- **Fixed Molecule opcodes and stages**: `-10`, `-20`, `-30`, `-01` across `REACH`, `QUALIFY`, `ROUTE`.
- **Single-concept rule consolidation**: `N-RULE-ECONOMY` ("Use as few rules as possible while still covering all needed variables").
- **Closed gate verdicts**: satisfy/deny checks and bounded route dispositions (`ADMIT_TO_NEUTRAL`, `HOLD_FOR_GUARD`, `REJECT_BOUNDARY`).

Instead of paying free-form text generation latency and token overhead for structural classification, `anchor.decision-batch/1` compiles up to 1,000 independent `noul` (yes/no probability), `choice` (single-select), and `score` (rubric) questions for one-pass evaluation.

## Modes and Selectable Decider Providers Behind One Contract

1. **Deterministic Offline Default — Decider Boost OFF (`DeterministicDecisionEngine`)**:
   - Uses only the Python 3.11-3.14 standard library.
   - Performs AST and static signal inspection offline with zero API keys or network traffic.
   - Emits `mode: "DETERMINISTIC_OFFLINE"`, `provenance: "source_extracted"`, `authority: "NONE"`.

2. **Default Boost Provider — OpenRouter Perplexity Decider V1.2 (`OpenRouterDecisionBoostAdapter`)**:
   - Consistent with KPP's OpenRouter-first MIND configuration (`openrouter-mind`), `"openrouter"` is the default Decider provider when boost is enabled (`model: "perplexity/pplx-decider-v1.2"`, plus `"perplexity/pplx-decider-flash-v1.2"`, `"perplexity/pplx-decider-v1.1"`, `"perplexity/pplx-decider-v1.3"`, or `"~perplexity/pplx-decider-latest"`).
   - Opt-in when `"anchor-decision-boost"` is listed in a recipe's `"ingredients"` and the host explicitly constructs `OpenRouterDecisionBoostAdapter(api_key=..., ...)` or `create_decision_boost_adapter(provider="openrouter", ...)`.
   - Formats batches for `POST https://openrouter.ai/api/alpha/decisions` (`state`, `instructions`, record `criteria` on `choice`, ordered `criteria` on `score`) and normalizes OpenRouter 0-based `legend` scores cleanly onto rubric scales.

3. **Selectable Gemini Option — Google Decision 1 (`GeminiDecisionBoostAdapter` / `gemini-decision-1`)**:
   - Selectable via `GeminiDecisionBoostAdapter(api_key=..., ...)` or `create_decision_boost_adapter(provider="gemini", ...)`.
   - Formats the batch for `POST https://generativelanguage.googleapis.com/v1beta/decisions` (`model: "gemini-decision-1"`), producing calibrated values and `confidence` scores in a single pass.

4. **Shared Safety Invariants (All Providers)**:
   - **Fail-closed confidence gating**: any answer below `confidence_threshold` (default `0.65`) is marked `"UNDETERMINED"`, surfaced in `unknowns`, and prevents unverified routing admission (`disposition: "UNDETERMINED"`).
   - **No authority escalation**: outputs always carry `provenance: "model_inferred"`, `authority: "NONE"`, `baker_acceptance: "NOT_GRANTED"`, and canonical singularities in `mantleos.anchors` remain immutable.

## CLI Usage

Inspect whether a recipe enables the ingredient and view Decider provider defaults:

```bash
python -m mantleos kpp anchor-decision status --recipe recipes/anchor-decision-boost-v4.json
```

Emit a closed-ended decision batch (OpenRouter `api/alpha/decisions` with `--openrouter-request`, or Gemini `v1beta/decisions` with `--gemini-request`):

```bash
python -m mantleos kpp anchor-decision batch --input path/to/source.py --id MyDesign --goal "Route validated requests" --openrouter-request --out batch.json
```

Encode offline (Default OFF), or supply `--responses responses.json` with `--provider openrouter` (default) or `--provider gemini`:

```bash
python -m mantleos kpp anchor-decision encode --input path/to/source.py --id MyDesign --goal "Route validated requests" --recipe recipes/anchor-decision-boost-v4.json --out encoded.json
```

Decode and triage a stimulus against an Anchor design or KPP recipe:

```bash
python -m mantleos kpp anchor-decision decode --contract recipes/anchor-decision-boost-v4.json --stimulus stimulus.json --provider openrouter
```
