"""Model-independent Anchor decision encoding/decoding with optional Decider AI boost.

Core contracts and offline evaluation require zero external dependencies or APIs
(Default OFF: ``DETERMINISTIC_OFFLINE``). An explicit Decider AI adapter —
defaulting to OpenRouter (``perplexity/pplx-decider-v1.2`` via
``POST https://openrouter.ai/api/alpha/decisions``) for consistency with KPP's
OpenRouter-first cognition ecosystem, or Google Gemini (``gemini-decision-1`` via
``POST https://generativelanguage.googleapis.com/v1beta/decisions``) — accelerates
closed-ended classification and gate triage when enabled, but outputs remain
``model_inferred`` with ``authority == "NONE"`` and never override canonical
singularities or grant Baker acceptance.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import urllib.error
import urllib.request

from . import anchor_design, anchors, json_contract as c
from .anchor_engine.tools import anchor_structure

INGREDIENT_ID = "anchor-decision-boost"
CAPABILITY_ID = "anchor-decision-boost/1"
BATCH_SCHEMA = "anchor.decision-batch/1"
RESULT_SCHEMA = "anchor.decision-result/1"
ENCODING_SCHEMA = "anchor.decision-encoding/1"
DECODING_SCHEMA = "anchor.decision-decoding/1"

DEFAULT_BOOST_PROVIDER = "openrouter"
SUPPORTED_BOOST_PROVIDERS = ("openrouter", "gemini")

OPENROUTER_DECISIONS_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_OPENROUTER_MODEL = "perplexity/pplx-decider-v1.2"
ALLOWED_OPENROUTER_DECISION_MODELS = frozenset({
    "perplexity/pplx-decider-v1.2",
    "perplexity/pplx-decider-flash-v1.2",
    "perplexity/pplx-decider-v1.1",
    "perplexity/pplx-decider-v1.3",
    "~perplexity/pplx-decider-latest",
})

GEMINI_DECISIONS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/decisions"
DEFAULT_GEMINI_MODEL = "gemini-decision-1"
ALLOWED_GEMINI_DECISION_MODELS = frozenset({DEFAULT_GEMINI_MODEL, f"models/{DEFAULT_GEMINI_MODEL}"})

# Backward-compatible aliases; default Decider boost uses OpenRouter pplx-decider-v1.2.
DEFAULT_MODEL = DEFAULT_OPENROUTER_MODEL
DECISIONS_ENDPOINT = GEMINI_DECISIONS_ENDPOINT
ALLOWED_DECISION_MODELS = ALLOWED_OPENROUTER_DECISION_MODELS | ALLOWED_GEMINI_DECISION_MODELS

MAX_UNITS = 128
MAX_QUESTIONS = 1000
MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_CONFIDENCE_THRESHOLD = 0.65

POLARITIES = ("BlackHole", "WhiteHole", "Neutral")
OPCODES = ("10", "20", "30", "01")
STAGES = ("REACH", "QUALIFY", "ROUTE")
DISPOSITIONS = ("ADMIT_TO_NEUTRAL", "HOLD_FOR_GUARD", "REJECT_BOUNDARY", "UNDETERMINED")
DECODE_DISPOSITIONS = ("ADMIT_TO_NEUTRAL", "HOLD_FOR_GUARD", "REJECT_BOUNDARY")

ECONOMY_RUBRIC = [
    "1: redundant or fragmented anchors",
    "2: partial consolidation",
    "3: aligned polarity owners",
    "4: minimum sufficient rule economy",
]
DECODE_RUBRIC = [
    "1: boundary violation",
    "2: missing guard",
    "3: guard satisfied with caveats",
    "4: verified deterministic route",
]

_LINE_SEPARATORS = str.maketrans({"\x85": "\\u0085", "\u2028": "\\u2028", "\u2029": "\\u2029"})

_WHITEHOLE_TOKENS = frozenset({
    "allow", "assert", "auth", "authorize", "boundary", "check", "confirm", "deny",
    "enforce", "filter", "gate", "guard", "invariant", "limit", "permit", "policy",
    "qualify", "reject", "rule", "sanitize", "schema", "verify", "validate",
})
_BLACKHOLE_TOKENS = frozenset({
    "accept", "capture", "cli", "decode", "fetch", "ingest", "input", "intake",
    "listen", "load", "parse", "poll", "read", "receive", "recv", "request", "scan",
    "stimulus", "stream", "watch",
})
_NEUTRAL_TOKENS = frozenset({
    "apply", "build", "calc", "calculate", "commit", "compute", "core", "decide",
    "emit", "format", "ledger", "persist", "plan", "project", "render", "resolve",
    "route", "save", "state", "store", "transform", "update", "write",
})
_EMIT_TOKENS = frozenset({"emit", "format", "literal", "print", "render", "serialize"})
_SIGNAL_VOCAB = _WHITEHOLE_TOKENS | _BLACKHOLE_TOKENS | _NEUTRAL_TOKENS | _EMIT_TOKENS


def _safe_identifier(raw: str, prefix: str = "U") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(raw or "").strip()).strip("_-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}" if cleaned else prefix
    return cleaned[:64]


def _safe_anchor_id(raw: str, prefix: str = "A") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "").strip().upper()).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}" if cleaned else prefix
    return cleaned[:48]


def _safe_slug(raw: str, prefix: str = "obl") -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower()).strip("-_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{prefix}-{cleaned}" if cleaned else prefix
    return cleaned[:64]


def _clamp_summary(text: str, maximum: int = 240) -> str:
    collapsed = " ".join(str(text or "").split())
    if not collapsed:
        return "Declared structural unit"
    return collapsed[:maximum]


def _collect_signals(*parts: str) -> list[str]:
    found: set[str] = set()
    for part in parts:
        # Split camelCase/snake_case identifiers into lowercase tokens.
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(part or ""))
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", spaced):
            lower = token.lower()
            for word in lower.split("_"):
                if word in _SIGNAL_VOCAB:
                    found.add(word)
    return sorted(found)


def _ast_hint_tokens(node: ast.AST) -> str:
    tokens: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                tokens.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                tokens.append(child.func.attr)
        elif isinstance(child, (ast.Raise, ast.Assert)):
            tokens.append("validate")
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Attribute):
                    tokens.append("state")
        elif isinstance(child, ast.Return) and child.value is not None:
            tokens.append("emit")
    return " ".join(tokens)


def _normalize_unit(unit_id: str, kind: str, summary: str, signals: list[str], used_anchors: set[str], index: int) -> dict:
    clean_id = _safe_identifier(unit_id, prefix=f"unit{index}")
    candidate_anchor = _safe_anchor_id(clean_id, prefix="A")
    anchor_id = candidate_anchor
    suffix = 1
    while anchor_id in used_anchors:
        suffix += 1
        base = candidate_anchor[: max(1, 48 - len(f"_{suffix}"))]
        anchor_id = f"{base}_{suffix}"
    used_anchors.add(anchor_id)
    summary_text = _clamp_summary(summary)
    return {
        "unit_id": clean_id,
        "anchor_id": anchor_id,
        "kind": kind if kind in ("function", "class", "requirement", "symbol") else "symbol",
        "summary": summary_text,
        "signals": sorted(set(signals) | set(_collect_signals(clean_id, summary_text))),
    }


def _extract_from_python(source_text: str) -> list[dict] | None:
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    units: list[dict] = []
    used_anchors: set[str] = set()
    for node in tree.body:
        if len(units) >= MAX_UNITS:
            break
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            args = ", ".join(a.arg for a in node.args.args)
            hints = _ast_hint_tokens(node)
            summary = doc.splitlines()[0] if doc else f"def {node.name}({args})"
            units.append(_normalize_unit(
                node.name, "function", summary,
                _collect_signals(node.name, summary, hints),
                used_anchors, len(units) + 1,
            ))
        elif isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or f"class {node.name}"
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            hints = _ast_hint_tokens(node)
            units.append(_normalize_unit(
                node.name, "class", doc.splitlines()[0],
                _collect_signals(node.name, doc, hints),
                used_anchors, len(units) + 1,
            ))
            for method in methods:
                if len(units) >= MAX_UNITS:
                    break
                mdoc = ast.get_docstring(method) or ""
                margs = ", ".join(a.arg for a in method.args.args if a.arg != "self")
                mhints = _ast_hint_tokens(method)
                msummary = mdoc.splitlines()[0] if mdoc else f"{node.name}.{method.name}({margs})"
                units.append(_normalize_unit(
                    f"{node.name}_{method.name}", "function", msummary,
                    _collect_signals(node.name, method.name, msummary, mhints),
                    used_anchors, len(units) + 1,
                ))
    if not units:
        units.append(_normalize_unit(
            "module_entry", "symbol",
            source_text.strip()[:240] or "Python module entrypoint",
            _collect_signals(source_text),
            used_anchors, 1,
        ))
    return units


def extract_candidate_units(source_or_spec) -> list[dict]:
    """Extract up to ``MAX_UNITS`` normalized static candidate units without executing input."""
    used_anchors: set[str] = set()
    units: list[dict] = []

    if isinstance(source_or_spec, str):
        text = source_or_spec.strip()
        c.require(bool(text), "Source or specification text cannot be empty")
        py_units = _extract_from_python(text)
        if py_units is not None:
            return py_units
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//")):
                continue
            if ":" in stripped and len(stripped.split(":", 1)[0].split()) == 1:
                head, tail = stripped.split(":", 1)
                uid = head.strip()
                summary = tail.strip() or stripped
            else:
                uid = f"req_{len(units) + 1}"
                summary = stripped
            units.append(_normalize_unit(uid, "requirement", summary, _collect_signals(uid, summary), used_anchors, len(units) + 1))
            if len(units) >= MAX_UNITS:
                break
        c.require(bool(units), "No candidate units found in input text")
        return units

    if isinstance(source_or_spec, dict):
        if "native_report" in source_or_spec and isinstance(source_or_spec["native_report"], dict):
            return extract_candidate_units(source_or_spec["native_report"])
        if isinstance(source_or_spec.get("units"), list):
            return extract_candidate_units(source_or_spec["units"])
        if isinstance(source_or_spec.get("anchors"), list) and source_or_spec.get("schema") in ("kpp.recipe/3", "kpp.recipe/4"):
            for item in source_or_spec["anchors"][:MAX_UNITS]:
                if isinstance(item, dict):
                    uid = str(item.get("id") or f"anchor_{len(units) + 1}")
                    summary = f"{item.get('statement', '')} ({item.get('test', '')})"
                    units.append(_normalize_unit(uid, "requirement", summary, _collect_signals(uid, summary), used_anchors, len(units) + 1))
            c.require(bool(units), "Recipe contains no anchor obligations")
            return units
        graph = source_or_spec.get("graph")
        if isinstance(graph, dict) and isinstance(graph.get("nodes"), list):
            for node in graph["nodes"]:
                if not isinstance(node, dict) or node.get("kind") not in ("function", "class", "module"):
                    continue
                name = str(node.get("name") or node.get("id") or f"node_{len(units) + 1}")
                path = str(node.get("path") or "")
                summary = f"{node.get('kind')} {name} in {path}".strip()
                units.append(_normalize_unit(name, "symbol" if node.get("kind") == "module" else node["kind"], summary,
                                             _collect_signals(name, path, summary), used_anchors, len(units) + 1))
                if len(units) >= MAX_UNITS:
                    break
            c.require(bool(units), "Scan graph contains no module, class, or function nodes")
            return units
        c.require(False, "Unsupported dict format for candidate extraction")

    if isinstance(source_or_spec, (list, tuple)):
        for item in source_or_spec[:MAX_UNITS]:
            if isinstance(item, str) and item.strip():
                uid = f"unit_{len(units) + 1}"
                units.append(_normalize_unit(uid, "requirement", item, _collect_signals(item), used_anchors, len(units) + 1))
            elif isinstance(item, dict):
                uid = str(item.get("id") or item.get("unit_id") or item.get("name") or f"unit_{len(units) + 1}")
                summary = str(item.get("summary") or item.get("statement") or item.get("description") or uid)
                kind = str(item.get("kind") or "symbol")
                extra_signals = item.get("signals") if isinstance(item.get("signals"), list) else []
                units.append(_normalize_unit(uid, kind, summary, _collect_signals(uid, summary, " ".join(map(str, extra_signals))),
                                             used_anchors, len(units) + 1))
        c.require(bool(units), "Candidate list contains no valid units")
        return units

    c.require(False, "source_or_spec must be source text, a scan/recipe dict, or a unit list")
    return []


def build_encode_batch(source_or_spec, *, design_id: str, goal: str) -> dict:
    """Build a model-neutral ``anchor.decision-batch/1`` packet for Anchor encoding."""
    c.identifier(design_id)
    c.text(goal, maximum=1024)
    units = extract_candidate_units(source_or_spec)
    c.require(len(units) <= MAX_UNITS, "Exceeded maximum candidate units per batch")

    context_lines = [
        f"GOAL: {goal.strip()}",
        f"DESIGN_ID: {design_id}",
        f"RULE_ECONOMY: {anchors.RULE_ECONOMY}",
        "CANONICAL_POLARITIES: BlackHole=Receive the declared input | WhiteHole=Enforce the declared boundary | Neutral=Apply the declared relationship",
        "UNITS:",
    ]
    questions: dict[str, dict] = {}
    for index, unit in enumerate(units):
        prefix = f"u_{index}"
        uid = unit["unit_id"]
        sig_label = ", ".join(unit["signals"]) if unit["signals"] else "none"
        context_lines.append(f"- [{prefix}] {uid} ({unit['kind']}): {unit['summary']} [signals: {sig_label}]")
        questions[f"{prefix}_polarity"] = {
            "type": "choice",
            "question": f"Assign Anchor polarity for unit '{uid}' ({unit['summary']}).",
            "criteria": list(POLARITIES),
        }
        questions[f"{prefix}_opcode"] = {
            "type": "choice",
            "question": f"Select Molecule opcode (-10 validate/guard, -20 capture/ingress, -30 compute/state, -01 emit/literal) for '{uid}'.",
            "criteria": list(OPCODES),
        }
        questions[f"{prefix}_stage"] = {
            "type": "choice",
            "question": f"Select Anchor execution stage for '{uid}'.",
            "criteria": list(STAGES),
        }
        questions[f"{prefix}_owns_state"] = {
            "type": "noul",
            "question": f"Should unit '{uid}' directly own durable state or core logic (Neutral role)?",
        }
        questions[f"{prefix}_guards_effect"] = {
            "type": "noul",
            "question": f"Does unit '{uid}' act as a boundary validator or side-effect guard (WhiteHole role)?",
        }
        questions[f"{prefix}_economy_merge"] = {
            "type": "noul",
            "question": f"Under N-RULE-ECONOMY, can unit '{uid}' consolidate into the primary Anchor of its polarity without losing required boundary or coverage?",
        }

    questions["batch_rule_economy"] = {
        "type": "score",
        "question": "Score how well the candidate classification honors N-RULE-ECONOMY with minimum sufficient Anchor coverage.",
        "criteria": list(ECONOMY_RUBRIC),
    }
    c.require(1 <= len(questions) <= MAX_QUESTIONS, f"Decision batch exceeds {MAX_QUESTIONS}-question limit")

    batch = {
        "schema": BATCH_SCHEMA,
        "mode": "encode",
        "design_id": design_id,
        "goal": goal.strip(),
        "input_text": "\n".join(context_lines),
        "units": units,
        "questions": questions,
    }
    batch["batch_sha256"] = c.digest(batch)
    return validate_batch(batch)


def _design_from_contract(contract: dict) -> dict:
    c.require(isinstance(contract, dict), "Contract must be an anchor.design/1 or kpp.recipe/3|4 object")
    if contract.get("schema") == anchor_design.SCHEMA:
        return anchor_design.validate(contract)
    if contract.get("schema") in ("kpp.recipe/3", "kpp.recipe/4"):
        if contract.get("anchor_design") is not None:
            return anchor_design.validate(contract["anchor_design"])
        # Project a canonical minimal 3-Anchor contract for recipes without an explicit anchor_design.
        goal = str(contract.get("goal") or "Recipe obligation routing").strip()
        rid = _safe_identifier(contract.get("id") or "recipe", prefix="D")
        obligations = contract.get("anchors") or []
        req_ids = [a.get("id", "obligation") for a in obligations if isinstance(a, dict) and a.get("required")]
        bh = anchors.application(
            "BH_RECIPE_ENTRY", definition_id="BlackHole",
            attributes={"responsibility": _clamp_summary(f"Receive requests and stimuli for recipe {rid}: {goal}")},
        )
        wh = anchors.application(
            "WH_RECIPE_GUARD", definition_id="WhiteHole",
            attributes={"responsibility": _clamp_summary(f"Enforce boundary invariants and recipe obligations ({', '.join(req_ids) or 'all'}).")},
        )
        ne = anchors.application(
            "N_RECIPE_CORE", definition_id="Neutral",
            attributes={"responsibility": _clamp_summary(f"Own state and deterministic behavior for {rid}.")},
        )
        return anchor_design.validate({
            "schema": anchor_design.SCHEMA,
            "id": rid,
            "purpose": _clamp_summary(goal),
            "applications": [bh, wh, ne],
            "flows": [
                {"from": "BH_RECIPE_ENTRY", "to": "WH_RECIPE_GUARD", "relationship": "Validate incoming stimulus"},
                {"from": "WH_RECIPE_GUARD", "to": "N_RECIPE_CORE", "relationship": "Admit verified request to Neutral core"},
            ],
            "state": [{"id": f"{_safe_slug(rid)}-state", "owner": "N_RECIPE_CORE"}],
            "effects": [
                {
                    "id": _safe_identifier(req_ids[0] if req_ids else "primary_effect", prefix="E"),
                    "requester": "N_RECIPE_CORE",
                    "guard": "WH_RECIPE_GUARD",
                    "confirmation": "WhiteHole guard verifies preconditions before Neutral effect admission.",
                }
            ],
        })
    c.require(False, "Contract must be schema anchor.design/1 or kpp.recipe/3|4")
    return {}


def build_decode_batch(contract: dict, stimulus) -> dict:
    """Build a model-neutral ``anchor.decision-batch/1`` packet for Anchor decoding/routing."""
    design = _design_from_contract(contract)
    if isinstance(stimulus, str):
        c.text(stimulus, maximum=4096)
        stim_obj = {"request": stimulus.strip()}
    elif isinstance(stimulus, dict):
        c.canonical(stimulus, limit=16384)
        stim_obj = deepcopy(stimulus)
    else:
        c.require(False, "Stimulus must be a string or JSON object")

    apps_by_type = {t: [a for a in design["applications"] if a["type"] == t] for t in POLARITIES}
    context_lines = [
        anchor_design.render(design).strip(),
        "",
        "STIMULUS:",
        json.dumps(stim_obj, ensure_ascii=False, sort_keys=True),
    ]
    questions: dict[str, dict] = {}
    if apps_by_type["BlackHole"]:
        questions["entry_anchor"] = {
            "type": "choice",
            "question": "Which BlackHole Anchor receives this stimulus?",
            "criteria": [a["id"] for a in apps_by_type["BlackHole"]] + ["UNROUTED"],
        }
    if apps_by_type["WhiteHole"]:
        questions["guard_anchor"] = {
            "type": "choice",
            "question": "Which WhiteHole Anchor must qualify this stimulus or requested effect?",
            "criteria": [a["id"] for a in apps_by_type["WhiteHole"]] + ["UNROUTED"],
        }
    if apps_by_type["Neutral"]:
        questions["target_owner"] = {
            "type": "choice",
            "question": "Which Neutral Anchor owns the target state or relationship for this stimulus?",
            "criteria": [a["id"] for a in apps_by_type["Neutral"]] + ["UNROUTED"],
        }

    for wh in apps_by_type["WhiteHole"]:
        questions[f"guard_{wh['id']}_satisfied"] = {
            "type": "noul",
            "question": f"Does the stimulus satisfy WhiteHole guard '{wh['id']}' ({wh['attributes']['responsibility']})?",
        }
    for eff in design.get("effects", []):
        questions[f"effect_{eff['id']}_permitted"] = {
            "type": "noul",
            "question": f"Is guarded effect '{eff['id']}' ({eff['confirmation']}) permitted for this stimulus?",
        }

    questions["route_disposition"] = {
        "type": "choice",
        "question": "Select the bounded Anchor routing disposition for this stimulus.",
        "criteria": list(DECODE_DISPOSITIONS),
    }
    questions["route_confidence_rubric"] = {
        "type": "score",
        "question": "Score boundary and guard verification completeness for routing this stimulus.",
        "criteria": list(DECODE_RUBRIC),
    }
    c.require(1 <= len(questions) <= MAX_QUESTIONS, f"Decision batch exceeds {MAX_QUESTIONS}-question limit")

    batch = {
        "schema": BATCH_SCHEMA,
        "mode": "decode",
        "design_id": design["id"],
        "design": design,
        "stimulus": stim_obj,
        "input_text": "\n".join(context_lines),
        "questions": questions,
    }
    batch["batch_sha256"] = c.digest(batch)
    return validate_batch(batch)


def validate_batch(batch: dict) -> dict:
    """Validate structure and digest of an ``anchor.decision-batch/1`` packet."""
    c.require(isinstance(batch, dict) and batch.get("schema") == BATCH_SCHEMA, "Invalid decision batch schema")
    mode = batch.get("mode")
    c.require(mode in ("encode", "decode"), "Batch mode must be encode or decode")
    c.identifier(batch.get("design_id"))
    c.text(batch.get("input_text"), maximum=128_000)
    questions = batch.get("questions")
    c.require(isinstance(questions, dict) and 1 <= len(questions) <= MAX_QUESTIONS, "Batch must contain 1..1000 questions")
    for qid, spec in questions.items():
        c.require(isinstance(qid, str) and bool(qid.strip()), "Invalid question id")
        c.require(isinstance(spec, dict) and spec.get("type") in ("noul", "choice", "score"), f"Invalid question type for {qid}")
        c.text(spec.get("question"), maximum=1024)
        if spec["type"] in ("choice", "score"):
            criteria = spec.get("criteria")
            c.require(isinstance(criteria, list) and 2 <= len(criteria) <= 64 and all(isinstance(x, str) and x.strip() for x in criteria),
                      f"Question {qid} requires 2..64 non-empty criteria strings")
    expected_digest = c.digest({k: v for k, v in batch.items() if k != "batch_sha256"})
    c.require(batch.get("batch_sha256") == expected_digest, "Decision batch digest mismatch")
    return deepcopy(batch)


_OPENROUTER_CHOICE_DESCRIPTIONS = {
    "BlackHole": "Receive the declared external input or parse ingress stream without committing durable state.",
    "WhiteHole": "Enforce declared boundary invariants, validation, authorization, schema, or credit/limit guard.",
    "Neutral": "Apply declared relationship, compute core logic, persist/own state, or emit output.",
    "10": "Boundary validation, invariant enforcement, or guard qualification (-10 WhiteHole).",
    "20": "External input intake, parsing, listening, or capture (-20 BlackHole).",
    "30": "Core computation, state transformation, or ledger update (-30 Neutral).",
    "01": "Pure literal emission, serialization, or formatting (-01 Neutral/Emit).",
    "REACH": "Input reception/ingress phase (BlackHole).",
    "QUALIFY": "Boundary verification/guard phase (WhiteHole).",
    "ROUTE": "Admitted relationship/state/emit phase (Neutral).",
    "ADMIT_TO_NEUTRAL": "Boundary and all WhiteHole guards are satisfied; admit stimulus to Neutral core.",
    "HOLD_FOR_GUARD": "Input boundary is valid, but a required WhiteHole guard or policy precondition is not satisfied.",
    "REJECT_BOUNDARY": "Malformed, unauthorized, or explicitly violating declared boundary invariants; reject immediately.",
    "UNROUTED": "No declared Anchor in the contract handles this stimulus.",
}


def _openrouter_choice_criteria(qid: str, criteria: list[str], batch: dict) -> dict[str, str]:
    app_responsibilities: dict[str, str] = {}
    design = batch.get("design")
    if isinstance(design, dict):
        for app in design.get("applications", ()):
            if isinstance(app, dict) and isinstance(app.get("id"), str):
                resp = (app.get("attributes") or {}).get("responsibility")
                if isinstance(resp, str) and resp.strip():
                    app_responsibilities[app["id"]] = resp.strip()

    mapping: dict[str, str] = {}
    for option in criteria:
        if option in app_responsibilities:
            mapping[option] = app_responsibilities[option]
        elif option in _OPENROUTER_CHOICE_DESCRIPTIONS:
            mapping[option] = _OPENROUTER_CHOICE_DESCRIPTIONS[option]
        else:
            mapping[option] = f"Select '{option}' for {qid}."
    return mapping


def to_gemini_decisions_request(batch: dict, *, model: str = DEFAULT_GEMINI_MODEL) -> dict:
    """Format a validated ``anchor.decision-batch/1`` into a ``POST /v1beta/decisions`` request."""
    valid = validate_batch(batch)
    if model not in ALLOWED_GEMINI_DECISION_MODELS:
        raise ValueError(f"Unsupported Gemini Decision AI model: {model!r}; expected {DEFAULT_GEMINI_MODEL!r}")
    return {
        "model": DEFAULT_GEMINI_MODEL,
        "input": valid["input_text"],
        "questions": deepcopy(valid["questions"]),
    }


def to_openrouter_decisions_request(batch: dict, *, model: str = DEFAULT_OPENROUTER_MODEL) -> dict:
    """Format a validated ``anchor.decision-batch/1`` into an OpenRouter ``POST /api/alpha/decisions`` request."""
    valid = validate_batch(batch)
    if model not in ALLOWED_OPENROUTER_DECISION_MODELS:
        raise ValueError(
            f"Unsupported OpenRouter Decider model: {model!r}; allowed: {sorted(ALLOWED_OPENROUTER_DECISION_MODELS)}"
        )
    formatted_questions: dict[str, dict] = {}
    for qid, spec in valid["questions"].items():
        qtype = spec["type"]
        if qtype == "noul":
            formatted_questions[qid] = {
                "type": "noul",
                "instructions": spec["question"],
            }
        elif qtype == "choice":
            formatted_questions[qid] = {
                "type": "choice",
                "instructions": spec["question"],
                "criteria": _openrouter_choice_criteria(qid, spec["criteria"], valid),
            }
        else:  # score
            formatted_questions[qid] = {
                "type": "score",
                "instructions": spec["question"],
                "criteria": list(spec["criteria"]),
            }
    return {
        "model": model,
        "state": valid["input_text"],
        "questions": formatted_questions,
    }


def _finite_unit_float(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a numeric float in [0.0, 1.0]")
    num = float(value)
    if not math.isfinite(num) or not (0.0 <= num <= 1.0):
        raise ValueError(f"{name} must lie in [0.0, 1.0]")
    return round(num, 6)


def _derive_confidence(qid: str, qtype: str, raw: dict, *, noul_prob: float | None = None, choice: str | None = None) -> float:
    if "confidence" in raw and raw["confidence"] is not None:
        return _finite_unit_float(raw["confidence"], f"{qid}.confidence")
    if qtype == "noul" and noul_prob is not None:
        return round(max(noul_prob, 1.0 - noul_prob), 6)
    probs = raw.get("probabilities")
    if qtype == "choice":
        if isinstance(probs, dict) and probs:
            if choice in probs:
                return _finite_unit_float(probs[choice], f"{qid}.probabilities.{choice}")
            return max(_finite_unit_float(val, f"{qid}.probabilities.{k}") for k, val in probs.items())
    elif qtype == "score":
        if isinstance(probs, dict) and probs:
            return max(_finite_unit_float(val, f"{qid}.probabilities.{k}") for k, val in probs.items())
        if isinstance(probs, list) and probs:
            return max(_finite_unit_float(val, f"{qid}.probabilities[{idx}]") for idx, val in enumerate(probs))
    return _finite_unit_float(raw.get("confidence"), f"{qid}.confidence")


def validate_result(
    batch: dict,
    raw_answers: dict,
    *,
    mode: str,
    model: str,
    provenance: str,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """Validate Decision answers against ``batch`` and flag low-confidence items as ``UNDETERMINED``."""
    valid_batch = validate_batch(batch)
    if not isinstance(raw_answers, dict):
        raise ValueError("Decision answers must be a dict keyed by question_id")
    if isinstance(confidence_threshold, bool) or not isinstance(confidence_threshold, (int, float)):
        raise ValueError("confidence_threshold must be a number in (0, 1]")
    threshold = float(confidence_threshold)
    if not math.isfinite(threshold) or not (0.0 < threshold <= 1.0):
        raise ValueError("confidence_threshold must lie in (0.0, 1.0]")

    normalized: dict[str, dict] = {}
    undetermined: list[str] = []

    for qid, spec in valid_batch["questions"].items():
        if qid not in raw_answers or not isinstance(raw_answers[qid], dict):
            raise ValueError(f"Missing or malformed decision answer for '{qid}'")
        raw = raw_answers[qid]
        qtype = spec["type"]

        if qtype == "noul":
            if "noul" in raw:
                prob = _finite_unit_float(raw["noul"], f"{qid}.noul")
            elif isinstance(raw.get("answer"), bool):
                prob = 1.0 if raw["answer"] else 0.0
            else:
                raise ValueError(f"Question '{qid}' (noul) requires numeric 'noul' in [0.0, 1.0]")
            confidence = _derive_confidence(qid, qtype, raw, noul_prob=prob)
            proposed = prob >= 0.5
            certain = confidence >= threshold
            entry = {
                "type": "noul",
                "noul": prob,
                "confidence": confidence,
                "proposed_value": proposed,
                "value": proposed if certain else "UNDETERMINED",
                "status": "CERTAIN" if certain else "UNDETERMINED",
            }
        elif qtype == "choice":
            choice = raw.get("choice")
            if not isinstance(choice, str) or choice not in spec["criteria"]:
                raise ValueError(f"Question '{qid}' choice {choice!r} is not in criteria {spec['criteria']}")
            confidence = _derive_confidence(qid, qtype, raw, choice=choice)
            certain = confidence >= threshold
            entry = {
                "type": "choice",
                "confidence": confidence,
                "proposed_value": choice,
                "value": choice if certain else "UNDETERMINED",
                "status": "CERTAIN" if certain else "UNDETERMINED",
            }
        else:  # score
            score_raw = raw.get("score")
            if isinstance(score_raw, bool) or not isinstance(score_raw, (int, float)):
                raise ValueError(f"Question '{qid}' (score) requires numeric 'score'")
            score_val = float(score_raw)
            max_score = float(len(spec["criteria"]))
            legend = raw.get("legend")
            if isinstance(legend, dict) and "0" in legend and str(len(spec["criteria"])) not in legend:
                # OpenRouter /api/alpha/decisions uses 0-indexed rubric levels in [0, len(criteria) - 1].
                if not math.isfinite(score_val) or not (0.0 <= score_val <= max_score - 1.0):
                    raise ValueError(f"Question '{qid}' 0-based score {score_val} must lie in [0, {int(max_score) - 1}]")
                score_val += 1.0
            if not math.isfinite(score_val) or not (1.0 <= score_val <= max_score):
                raise ValueError(f"Question '{qid}' score {score_val} must lie in [1, {int(max_score)}]")
            confidence = _derive_confidence(qid, qtype, raw)
            rounded_score = int(round(score_val)) if float(score_val).is_integer() else round(score_val, 3)
            certain = confidence >= threshold
            entry = {
                "type": "score",
                "score": rounded_score,
                "confidence": confidence,
                "proposed_value": rounded_score,
                "value": rounded_score if certain else "UNDETERMINED",
                "status": "CERTAIN" if certain else "UNDETERMINED",
            }

        if entry["status"] == "UNDETERMINED":
            undetermined.append(qid)
        normalized[qid] = entry

    return {
        "schema": RESULT_SCHEMA,
        "batch_sha256": valid_batch["batch_sha256"],
        "mode": mode,
        "model": model,
        "provenance": provenance,
        "confidence_threshold": threshold,
        "answers": normalized,
        "undetermined_questions": sorted(undetermined),
        "authority": "NONE",
        "baker_acceptance": "NOT_GRANTED",
    }


def _heuristic_classify_unit(unit: dict) -> tuple[str, str, str, float, float]:
    """Deterministic polarity/opcode/stage classification for offline execution."""
    tokens = set(unit.get("signals") or ()) | set(_collect_signals(unit["unit_id"], unit["summary"]))
    wh_hits = len(tokens & _WHITEHOLE_TOKENS)
    bh_hits = len(tokens & _BLACKHOLE_TOKENS)
    ne_hits = len(tokens & _NEUTRAL_TOKENS)
    emit_hits = len(tokens & _EMIT_TOKENS)

    if wh_hits > max(bh_hits, ne_hits) or (wh_hits > 0 and wh_hits >= bh_hits and ne_hits == 0):
        return ("WhiteHole", "10", "QUALIFY", 0.08, 0.92)
    if bh_hits > max(wh_hits, ne_hits) or (bh_hits > 0 and wh_hits == 0 and ne_hits == 0):
        return ("BlackHole", "20", "REACH", 0.12, 0.14)
    opcode = "01" if (emit_hits > 0 and emit_hits >= ne_hits and "state" not in tokens and "store" not in tokens and "ledger" not in tokens) else "30"
    return ("Neutral", opcode, "ROUTE", 0.88 if opcode == "30" else 0.25, 0.10)


class DeterministicDecisionEngine:
    """100% LLM-independent local Anchor decision batch solver (Python stdlib only)."""

    model = "deterministic-anchor-solver/1"

    def evaluate(self, batch: dict, *, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict:
        valid = validate_batch(batch)
        answers: dict[str, dict] = {}

        if valid["mode"] == "encode":
            seen_polarities: dict[str, int] = {}
            for index, unit in enumerate(valid["units"]):
                prefix = f"u_{index}"
                polarity, opcode, stage, owns_state, guards_effect = _heuristic_classify_unit(unit)
                seen_polarities[polarity] = seen_polarities.get(polarity, 0) + 1
                # First Anchor of each polarity anchors that role; subsequent ones without explicit
                # distinct guard/ingress tokens consolidate under N-RULE-ECONOMY.
                distinct_needed = bool(set(unit["signals"]) & {"guard", "boundary", "auth", "policy", "ledger"})
                can_merge = seen_polarities[polarity] > 1 and not distinct_needed
                answers[f"{prefix}_polarity"] = {"choice": polarity, "confidence": 0.94}
                answers[f"{prefix}_opcode"] = {"choice": opcode, "confidence": 0.93}
                answers[f"{prefix}_stage"] = {"choice": stage, "confidence": 0.93}
                answers[f"{prefix}_owns_state"] = {"noul": owns_state, "confidence": 0.92}
                answers[f"{prefix}_guards_effect"] = {"noul": guards_effect, "confidence": 0.92}
                answers[f"{prefix}_economy_merge"] = {"noul": 0.84 if can_merge else 0.16, "confidence": 0.91}
            answers["batch_rule_economy"] = {"score": 4, "confidence": 0.95}
        else:  # decode
            design = valid["design"]
            stimulus = valid["stimulus"]
            apps_by_type = {t: [a["id"] for a in design["applications"] if a["type"] == t] for t in POLARITIES}
            stim_text = json.dumps(stimulus, sort_keys=True).lower()
            boundary_bad = (
                stimulus.get("boundary_valid") is False
                or stimulus.get("valid_boundary") is False
                or stimulus.get("reject") is True
                or stimulus.get("verdict") == "REJECT_BOUNDARY"
                or stimulus.get("disposition") == "REJECT_BOUNDARY"
            )
            guard_bad = (
                stimulus.get("guard_passed") is False
                or stimulus.get("preconditions_met") is False
                or stimulus.get("authorized") is False
            )

            if "entry_anchor" in valid["questions"]:
                criteria = valid["questions"]["entry_anchor"]["criteria"]
                picked = _match_anchor_choice(criteria, stimulus.get("entry") or stim_text, default=apps_by_type["BlackHole"][0])
                answers["entry_anchor"] = {"choice": picked, "confidence": 0.95}
            if "guard_anchor" in valid["questions"]:
                criteria = valid["questions"]["guard_anchor"]["criteria"]
                picked = _match_anchor_choice(criteria, stimulus.get("guard") or stim_text, default=apps_by_type["WhiteHole"][0])
                answers["guard_anchor"] = {"choice": picked, "confidence": 0.95}
            if "target_owner" in valid["questions"]:
                criteria = valid["questions"]["target_owner"]["criteria"]
                picked = _match_anchor_choice(criteria, stimulus.get("target") or stim_text, default=apps_by_type["Neutral"][0])
                answers["target_owner"] = {"choice": picked, "confidence": 0.95}

            guard_ok = not boundary_bad and not guard_bad
            for wh_id in apps_by_type["WhiteHole"]:
                qid = f"guard_{wh_id}_satisfied"
                if qid in valid["questions"]:
                    answers[qid] = {"noul": 0.94 if guard_ok else 0.06, "confidence": 0.94}
            for eff in design.get("effects", []):
                qid = f"effect_{eff['id']}_permitted"
                if qid in valid["questions"]:
                    denied = isinstance(stimulus.get("denied_effects"), list) and eff["id"] in stimulus["denied_effects"]
                    answers[qid] = {"noul": 0.05 if (not guard_ok or denied) else 0.93, "confidence": 0.93}

            if boundary_bad:
                disposition, score_val = "REJECT_BOUNDARY", 1
            elif guard_bad:
                disposition, score_val = "HOLD_FOR_GUARD", 2
            else:
                disposition, score_val = "ADMIT_TO_NEUTRAL", 4
            answers["route_disposition"] = {"choice": disposition, "confidence": 0.95}
            answers["route_confidence_rubric"] = {"score": score_val, "confidence": 0.94}

        return validate_result(
            valid,
            answers,
            mode="DETERMINISTIC_OFFLINE",
            model=self.model,
            provenance="source_extracted",
            confidence_threshold=confidence_threshold,
        )


def _match_anchor_choice(criteria: list[str], hint, *, default: str) -> str:
    hint_str = str(hint or "").lower()
    for cid in criteria:
        if cid.lower() in hint_str:
            return cid
    return default


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Decision AI redirects are disallowed")


class _BaseDecisionBoostAdapter:
    """Shared bounded transport, budget, and fail-closed validation for Decider AI adapters."""

    provider = "base"
    api_label = "Decision AI API"
    default_model = DEFAULT_MODEL
    default_endpoint = OPENROUTER_DECISIONS_ENDPOINT
    allowed_models = ALLOWED_DECISION_MODELS

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        transport=None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        budget_calls: int = 16,
        timeout: float = 30.0,
    ):
        resolved_model = self.default_model if model is None else model
        resolved_endpoint = self.default_endpoint if endpoint is None else endpoint
        if resolved_model not in self.allowed_models:
            raise ValueError(
                f"Unsupported Decision AI model for {self.provider}: {resolved_model!r}; "
                f"allowed: {sorted(self.allowed_models)}"
            )
        if isinstance(confidence_threshold, bool) or not isinstance(confidence_threshold, (int, float)) or not (0.0 < float(confidence_threshold) <= 1.0):
            raise ValueError("confidence_threshold must lie in (0.0, 1.0]")
        if type(budget_calls) is not int or not 1 <= budget_calls <= 1000:
            raise ValueError("budget_calls must be an integer in 1..1000")
        if not isinstance(resolved_endpoint, str) or not resolved_endpoint.startswith("https://"):
            raise ValueError("Decisions endpoint must use https://")
        self.api_key = api_key
        self.model = self._normalize_model(resolved_model)
        self.endpoint = resolved_endpoint
        self.transport = transport
        self.confidence_threshold = float(confidence_threshold)
        self.budget_calls = budget_calls
        self.timeout = float(timeout)
        self.calls_used = 0
        self.last_usage: dict | None = None

    def _normalize_model(self, model: str) -> str:
        return model

    def _build_payload(self, batch: dict) -> dict:
        raise NotImplementedError

    def _auth_headers(self, key: str) -> dict[str, str]:
        raise NotImplementedError

    def evaluate(self, batch: dict) -> dict:
        valid = validate_batch(batch)
        if self.calls_used >= self.budget_calls:
            raise ValueError("Decision AI boost call budget exhausted")
        payload = self._build_payload(valid)
        self.calls_used += 1

        if self.transport is not None:
            response = self.transport(payload)
        else:
            if not isinstance(self.api_key, str) or not self.api_key.strip():
                raise ValueError(
                    f"{self.api_label} boost requires an explicit api_key or transport; "
                    "use DeterministicDecisionEngine for offline LLM-independent execution"
                )
            key = self.api_key.strip()
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            request = urllib.request.Request(
                self.endpoint,
                data=body,
                method="POST",
                headers=self._auth_headers(key),
            )
            try:
                with urllib.request.build_opener(_NoRedirect).open(request, timeout=self.timeout) as resp:
                    raw_bytes = resp.read(MAX_RESPONSE_BYTES + 1)
            except urllib.error.HTTPError as exc:
                detail = exc.read(512).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
                raise ValueError(f"{self.api_label} HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise ValueError(f"{self.api_label} network failure: {exc.reason}") from exc
            if len(raw_bytes) > MAX_RESPONSE_BYTES:
                raise ValueError(f"{self.api_label} response exceeded 1 MiB limit")
            response = json.loads(raw_bytes.decode("utf-8"))

        if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
            raise ValueError(f"{self.api_label} response must contain an 'answers' object")
        usage = response.get("usage")
        self.last_usage = dict(usage) if isinstance(usage, dict) else None
        return validate_result(
            valid,
            response["answers"],
            mode="DECISION_AI_BOOST",
            model=self.model,
            provenance="model_inferred",
            confidence_threshold=self.confidence_threshold,
        )


class OpenRouterDecisionBoostAdapter(_BaseDecisionBoostAdapter):
    """Default opt-in Decider AI adapter using OpenRouter (``perplexity/pplx-decider-v1.2``).

    Performs zero network I/O on import or construction. Uses ``POST /api/alpha/decisions``
    when an explicit ``api_key`` (or synthetic ``transport``) is provided.
    """

    provider = "openrouter"
    api_label = "OpenRouter Decisions API"
    default_model = DEFAULT_OPENROUTER_MODEL
    default_endpoint = OPENROUTER_DECISIONS_ENDPOINT
    allowed_models = ALLOWED_OPENROUTER_DECISION_MODELS

    def _build_payload(self, batch: dict) -> dict:
        return to_openrouter_decisions_request(batch, model=self.model)

    def _auth_headers(self, key: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "X-OpenRouter-Title": "KPP Anchor Decision Boost",
        }


class GeminiDecisionBoostAdapter(_BaseDecisionBoostAdapter):
    """Opt-in Google Decision AI adapter for ``gemini-decision-1`` (``POST /v1beta/decisions``).

    Performs zero network I/O on import or construction. Use ``transport`` for
    synthetic fixtures or custom host HTTP wiring; otherwise requires an explicit
    ``api_key`` and sends bounded HTTPS POST calls when ``evaluate`` is invoked.
    """

    provider = "gemini"
    api_label = "Gemini Decisions API"
    default_model = DEFAULT_GEMINI_MODEL
    default_endpoint = GEMINI_DECISIONS_ENDPOINT
    allowed_models = ALLOWED_GEMINI_DECISION_MODELS

    def _normalize_model(self, model: str) -> str:
        return DEFAULT_GEMINI_MODEL

    def _build_payload(self, batch: dict) -> dict:
        return to_gemini_decisions_request(batch, model=self.model)

    def _auth_headers(self, key: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        }


def create_decision_boost_adapter(
    *,
    provider: str = DEFAULT_BOOST_PROVIDER,
    api_key: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    transport=None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    budget_calls: int = 16,
    timeout: float = 30.0,
) -> _BaseDecisionBoostAdapter:
    """Create a bounded Decider AI adapter, defaulting to OpenRouter ``perplexity/pplx-decider-v1.2``."""
    adapters = {
        "openrouter": OpenRouterDecisionBoostAdapter,
        "gemini": GeminiDecisionBoostAdapter,
    }
    cls = adapters.get(provider)
    if cls is None:
        raise ValueError(f"Unsupported Decider provider {provider!r}; expected one of {SUPPORTED_BOOST_PROVIDERS}")
    return cls(
        api_key=api_key,
        model=model,
        endpoint=endpoint,
        transport=transport,
        confidence_threshold=confidence_threshold,
        budget_calls=budget_calls,
        timeout=timeout,
    )


def involves_anchor_coding(recipe: dict) -> dict:
    """Detect whether a KPP recipe involves Anchor coding (coding around set Anchors).

    Pure dictionary inspection: never invokes ``anchors.definition`` or ``kitchen.bind``.
    """
    c.require(isinstance(recipe, dict) and recipe.get("schema") in ("kpp.recipe/3", "kpp.recipe/4"),
              "Expected a kpp.recipe/3 or kpp.recipe/4 object")
    signals: list[str] = []
    if recipe.get("schema") == "kpp.recipe/3" or recipe.get("anchor_binding") == "shared-neutral":
        signals.append("anchor_binding:shared-neutral")
    if recipe.get("tissue") == "anchor":
        signals.append("tissue:anchor")
    if recipe.get("anchor_design") is not None:
        signals.append("anchor_design")

    impl = recipe.get("implementation")
    components = impl.get("components", ()) if isinstance(impl, dict) else ()
    if isinstance(components, (list, tuple)) and any(
        isinstance(comp, dict)
        and (
            comp.get("selected") == "anchor"
            or (isinstance(comp.get("languages"), (list, tuple)) and "anchor" in comp.get("languages", ()))
        )
        for comp in components
    ):
        signals.append("component_language:anchor")

    ingredients = recipe.get("ingredients") or ()
    if isinstance(ingredients, (list, tuple)) and any(
        isinstance(item, str) and item.startswith("anchor")
        for item in ingredients
    ):
        signals.append("anchor_ingredient")

    obligations = recipe.get("anchors") or ()
    typed_keys = ("type", "singularity", "definition", "design_anchors")
    if isinstance(obligations, (list, tuple)) and any(
        isinstance(obl, dict) and any(key in obl for key in typed_keys)
        for obl in obligations
    ):
        signals.append("typed_anchor_obligations")

    return {
        "involves_anchor_coding": bool(signals),
        "anchor_signals": signals,
    }


def recipe_boost_status(recipe: dict) -> dict:
    """Inspect whether a KPP recipe selects or should consider ``anchor-decision-boost``."""
    anchor_info = involves_anchor_coding(recipe)
    involves = anchor_info["involves_anchor_coding"]
    signals = anchor_info["anchor_signals"]
    ingredients = recipe.get("ingredients", [])
    ing_set = set(ingredients) if isinstance(ingredients, (list, tuple)) else set()
    enabled = INGREDIENT_ID in ing_set
    openrouter_mind_present = "openrouter-mind" in ing_set
    recommendation = "SELECTED" if enabled else ("RECOMMENDED_OPTIONAL" if involves else "OPTIONAL")
    if enabled:
        advisory = (
            "Selected in recipe ingredients. Default execution stays OFF (DETERMINISTIC_OFFLINE); "
            "if an API key is configured, Decider speedup defaults to OpenRouter (perplexity/pplx-decider-v1.2) "
            "or selectable Gemini (gemini-decision-1)."
        )
    elif recommendation == "RECOMMENDED_OPTIONAL":
        if openrouter_mind_present:
            advisory = (
                "Recipe involves Anchor coding and uses openrouter-mind; Decider boost is OFF by default "
                "(DETERMINISTIC_OFFLINE), recommended if you have an OpenRouter API key, defaulting to "
                "OpenRouter (perplexity/pplx-decider-v1.2) with Gemini (gemini-decision-1) also selectable."
            )
        else:
            advisory = (
                "Recipe involves Anchor coding (coding around set Anchors); Decider speedup is OFF by default "
                "(DETERMINISTIC_OFFLINE) and recommended as an optional ingredient if you have an OpenRouter API key "
                "(default provider: openrouter / perplexity/pplx-decider-v1.2, or gemini / gemini-decision-1)."
            )
    else:
        advisory = "Optional ingredient (Default OFF) available if the recipe adopts Anchor coding."
    return {
        "schema": "anchor.decision-status/1",
        "ingredient": INGREDIENT_ID,
        "capability": CAPABILITY_ID,
        "involves_anchor_coding": involves,
        "anchor_signals": signals,
        "enabled": enabled,
        "recommendation": recommendation,
        "advisory": advisory,
        "default_mode": "DETERMINISTIC_OFFLINE",
        "default_boost_provider": DEFAULT_BOOST_PROVIDER,
        "supported_boost_providers": list(SUPPORTED_BOOST_PROVIDERS),
        "boost_models": {
            "openrouter": DEFAULT_OPENROUTER_MODEL,
            "openrouter_flash": "perplexity/pplx-decider-flash-v1.2",
            "gemini": DEFAULT_GEMINI_MODEL,
        },
        "boost_model": DEFAULT_MODEL,
        "openrouter_mind_present": openrouter_mind_present,
        "authority": "NONE",
    }


def _check_recipe_allows_boost(recipe: dict | None, decision_provider) -> None:
    if recipe is None:
        return
    c.require(isinstance(recipe, dict) and recipe.get("schema") in ("kpp.recipe/3", "kpp.recipe/4"),
              "Invalid recipe contract")
    if decision_provider is not None and INGREDIENT_ID not in recipe.get("ingredients", []):
        raise ValueError(f"Recipe '{recipe.get('id', '?')}' does not select '{INGREDIENT_ID}' in ingredients")


def encode_to_anchor(
    source_or_spec,
    *,
    design_id: str,
    goal: str,
    recipe: dict | None = None,
    decision_provider=None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """Encode source or specification into validated ``anchor.design/1``, Molecule entries, and recipe/4 obligations."""
    _check_recipe_allows_boost(recipe, decision_provider)
    batch = build_encode_batch(source_or_spec, design_id=design_id, goal=goal)
    if decision_provider is not None:
        result = decision_provider.evaluate(batch)
    else:
        result = DeterministicDecisionEngine().evaluate(batch, confidence_threshold=confidence_threshold)

    answers = result["answers"]
    unknowns: list[dict] = []
    if "batch_rule_economy" in result["undetermined_questions"]:
        unknowns.append({
            "question_id": "batch_rule_economy",
            "unit_id": None,
            "reason": "Low-confidence rule economy score requires review",
            "proposed_value": answers["batch_rule_economy"]["proposed_value"],
            "confidence": answers["batch_rule_economy"]["confidence"],
        })

    classified: list[dict] = []
    for index, unit in enumerate(batch["units"]):
        prefix = f"u_{index}"
        fallback_polarity, fallback_opcode, fallback_stage, _, _ = _heuristic_classify_unit(unit)
        unit_unknown = False
        for suffix in ("polarity", "opcode", "stage", "owns_state", "guards_effect", "economy_merge"):
            qid = f"{prefix}_{suffix}"
            if answers[qid]["status"] == "UNDETERMINED":
                unit_unknown = True
                unknowns.append({
                    "question_id": qid,
                    "unit_id": unit["unit_id"],
                    "reason": "Confidence below threshold; failed closed to deterministic fallback / review",
                    "proposed_value": answers[qid]["proposed_value"],
                    "confidence": answers[qid]["confidence"],
                })

        polarity = answers[f"{prefix}_polarity"]["value"]
        if polarity == "UNDETERMINED":
            polarity = fallback_polarity
        opcode = answers[f"{prefix}_opcode"]["value"]
        if opcode == "UNDETERMINED":
            opcode = fallback_opcode
        stage = answers[f"{prefix}_stage"]["value"]
        if stage == "UNDETERMINED":
            stage = fallback_stage
        merge_val = answers[f"{prefix}_economy_merge"]["value"]
        economy_merge = bool(merge_val) if merge_val != "UNDETERMINED" else False
        owns_state = answers[f"{prefix}_owns_state"]["value"] is True
        guards_effect = answers[f"{prefix}_guards_effect"]["value"] is True

        classified.append({
            **unit,
            "polarity": polarity,
            "opcode": opcode,
            "stage": stage,
            "owns_state": owns_state,
            "guards_effect": guards_effect,
            "economy_merge": economy_merge,
            "review_needed": unit_unknown,
        })

    # Apply N-RULE-ECONOMY consolidation while preserving at least one Anchor per polarity
    # and retaining every distinct non-merged boundary/state Anchor.
    primary_by_polarity: dict[str, dict] = {}
    retained_anchors: list[dict] = []
    unit_assignments: dict[str, str] = {}
    used_anchor_ids: set[str] = set()

    for item in classified:
        pol = item["polarity"]
        if pol not in primary_by_polarity or not item["economy_merge"]:
            aid = item["anchor_id"]
            if aid in used_anchor_ids:
                aid = _safe_anchor_id(f"{aid}_{len(retained_anchors) + 1}")
            used_anchor_ids.add(aid)
            record = {
                "anchor_id": aid,
                "polarity": pol,
                "opcode": item["opcode"],
                "stage": item["stage"],
                "units": [item["unit_id"]],
                "summaries": [item["summary"]],
                "owns_state": item["owns_state"],
                "guards_effect": item["guards_effect"],
                "review_needed": item["review_needed"],
            }
            primary_by_polarity.setdefault(pol, record)
            retained_anchors.append(record)
            unit_assignments[item["unit_id"]] = aid
        else:
            primary = primary_by_polarity[pol]
            primary["units"].append(item["unit_id"])
            primary["summaries"].append(item["summary"])
            primary["owns_state"] = primary["owns_state"] or item["owns_state"]
            primary["guards_effect"] = primary["guards_effect"] or item["guards_effect"]
            primary["review_needed"] = primary["review_needed"] or item["review_needed"]
            unit_assignments[item["unit_id"]] = primary["anchor_id"]

    # Ensure canonical BlackHole -> WhiteHole -> Neutral coverage exists so the design
    # satisfies structural state ownership and WhiteHole-guarded effect invariants.
    defaults = (
        ("BlackHole", "BH_INGRESS", "20", "REACH", f"Receive and normalize external inputs for {design_id}"),
        ("WhiteHole", "WH_BOUNDARY", "10", "QUALIFY", f"Enforce boundary invariants and preconditions for {design_id}"),
        ("Neutral", "N_CORE", "30", "ROUTE", f"Own core state and relationships for {design_id}: {goal.strip()}"),
    )
    for pol, default_id, opcode, stage, default_resp in defaults:
        if pol not in primary_by_polarity:
            aid = default_id if default_id not in used_anchor_ids else _safe_anchor_id(f"{default_id}_{len(retained_anchors) + 1}")
            used_anchor_ids.add(aid)
            record = {
                "anchor_id": aid,
                "polarity": pol,
                "opcode": opcode,
                "stage": stage,
                "units": [],
                "summaries": [default_resp],
                "owns_state": pol == "Neutral",
                "guards_effect": pol == "WhiteHole",
                "review_needed": False,
            }
            primary_by_polarity[pol] = record
            retained_anchors.append(record)

    applications: list[dict] = []
    molecule_lines: list[str] = []
    for record in retained_anchors:
        unit_desc = ", ".join(record["units"][:6])
        if len(record["units"]) > 6:
            unit_desc += f" (+{len(record['units']) - 6} more)"
        first_summary = record["summaries"][0]
        responsibility = _clamp_summary(
            f"{first_summary} [units: {unit_desc}]" if unit_desc else first_summary,
            maximum=240,
        )
        applications.append(anchors.application(
            record["anchor_id"],
            definition_id=record["polarity"],
            attributes={"responsibility": responsibility},
        ))
        spec_payload = json.dumps(
            {
                "stage": record["stage"],
                "units": record["units"],
                "responsibility": responsibility,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).translate(_LINE_SEPARATORS)
        molecule_lines.append(
            f"{record['anchor_id']}: {record['polarity']} -{record['opcode']} -00 -spec={spec_payload}"
        )

    # Verify generated Molecule entries obey mantleos shared AnchorShape checks.
    molecule_text = "\n".join(molecule_lines)
    anchor_structure.check_structures(molecule_text, all_types=True)

    bh_primary = primary_by_polarity["BlackHole"]["anchor_id"]
    wh_primary = primary_by_polarity["WhiteHole"]["anchor_id"]
    n_primary = primary_by_polarity["Neutral"]["anchor_id"]

    flows = [
        {"from": bh_primary, "to": wh_primary, "relationship": "Submit received inputs for boundary qualification"},
        {"from": wh_primary, "to": n_primary, "relationship": "Admit qualified inputs to Neutral core state"},
    ]
    seen_edges = {(e["from"], e["to"]) for e in flows}
    for record in retained_anchors:
        aid = record["anchor_id"]
        if record["polarity"] == "BlackHole" and aid != bh_primary and (aid, wh_primary) not in seen_edges:
            flows.append({"from": aid, "to": wh_primary, "relationship": "Forward ingress data to boundary guard"})
            seen_edges.add((aid, wh_primary))
        elif record["polarity"] == "WhiteHole" and aid != wh_primary and (aid, n_primary) not in seen_edges:
            flows.append({"from": aid, "to": n_primary, "relationship": "Admit guard-verified operation to core"})
            seen_edges.add((aid, n_primary))
        elif record["polarity"] == "Neutral" and aid != n_primary and (wh_primary, aid) not in seen_edges:
            flows.append({"from": wh_primary, "to": aid, "relationship": "Dispatch verified operation to Neutral owner"})
            seen_edges.add((wh_primary, aid))

    state = []
    neutral_records = [r for r in retained_anchors if r["polarity"] == "Neutral"]
    for idx, record in enumerate(neutral_records, 1):
        if record["owns_state"] or record["anchor_id"] == n_primary:
            state.append({
                "id": _safe_identifier(f"state_{record['anchor_id'].lower()}", prefix=f"s{idx}"),
                "owner": record["anchor_id"],
            })
    if not state:
        state.append({"id": "core_state", "owner": n_primary})

    effects = [{
        "id": _safe_identifier(f"effect_{design_id.lower()}", prefix="eff"),
        "requester": n_primary,
        "guard": wh_primary,
        "confirmation": _clamp_summary(f"WhiteHole guard {wh_primary} verifies preconditions before effect execution."),
    }]

    design = anchor_design.validate({
        "schema": anchor_design.SCHEMA,
        "id": design_id,
        "purpose": _clamp_summary(goal, maximum=512),
        "applications": applications,
        "flows": flows,
        "state": state,
        "effects": effects,
    })

    bh_ids = [r["anchor_id"] for r in retained_anchors if r["polarity"] == "BlackHole"]
    wh_ids = [r["anchor_id"] for r in retained_anchors if r["polarity"] == "WhiteHole"]
    n_ids = [r["anchor_id"] for r in retained_anchors if r["polarity"] == "Neutral"]

    ingress_slug = f"{_safe_slug(design_id)[:55]}-ingress"
    guard_slug = f"{_safe_slug(design_id)[:55]}-guard"
    core_slug = f"{_safe_slug(design_id)[:55]}-core"

    obligations = [
        {
            "id": ingress_slug,
            "statement": "All external inputs enter exclusively through declared BlackHole ingress Anchors.",
            "test": f"Verify ingress paths route through {', '.join(bh_ids)}.",
            "required": True,
            "depth": 1,
            "depends": [],
            "preserves": [],
            "design_anchors": bh_ids,
        },
        {
            "id": guard_slug,
            "statement": "Boundary checks and guarded effects are enforced by declared WhiteHole Anchors.",
            "test": f"Verify invalid inputs are rejected and effects require confirmation from {', '.join(wh_ids)}.",
            "required": True,
            "depth": 2,
            "depends": [ingress_slug],
            "preserves": [],
            "design_anchors": wh_ids,
        },
        {
            "id": core_slug,
            "statement": "Core state and relationships remain owned by declared Neutral Anchors under N-RULE-ECONOMY.",
            "test": f"Verify deterministic execution and state ownership for {', '.join(n_ids)}.",
            "required": True,
            "depth": 3,
            "depends": [guard_slug],
            "preserves": [],
            "design_anchors": n_ids,
        },
    ]

    return {
        "schema": ENCODING_SCHEMA,
        "ingredient": INGREDIENT_ID,
        "design_id": design["id"],
        "mode": result["mode"],
        "model": result["model"],
        "provenance": result["provenance"],
        "review_required": bool(unknowns),
        "unknowns": unknowns,
        "unit_assignments": unit_assignments,
        "consolidated_unit_count": len(batch["units"]) - len(retained_anchors) if len(batch["units"]) > len(retained_anchors) else 0,
        "design": design,
        "review": anchor_design.review(design),
        "molecules": molecule_lines,
        "molecule_source": molecule_text,
        "obligations": obligations,
        "decision_result": result,
        "authority": "NONE",
        "baker_acceptance": "NOT_GRANTED",
    }


def decode_through_anchor(
    contract: dict,
    stimulus,
    *,
    recipe: dict | None = None,
    decision_provider=None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict:
    """Decode and route a stimulus through an Anchor contract; low-confidence decisions fail closed."""
    contract_recipe = recipe if recipe is not None else (contract if isinstance(contract, dict) and contract.get("schema") in ("kpp.recipe/3", "kpp.recipe/4") else None)
    _check_recipe_allows_boost(contract_recipe, decision_provider)
    batch = build_decode_batch(contract, stimulus)
    if decision_provider is not None:
        result = decision_provider.evaluate(batch)
    else:
        result = DeterministicDecisionEngine().evaluate(batch, confidence_threshold=confidence_threshold)

    answers = result["answers"]
    unknowns: list[dict] = []
    for qid in result["undetermined_questions"]:
        unknowns.append({
            "question_id": qid,
            "reason": "Confidence below threshold; routing failed closed to UNDETERMINED",
            "proposed_value": answers[qid]["proposed_value"],
            "confidence": answers[qid]["confidence"],
        })

    # Fail closed if any routing/guard/effect decision is uncertain or unrouted.
    critical_undetermined = [
        qid for qid in result["undetermined_questions"]
        if qid != "route_confidence_rubric"
    ]
    if critical_undetermined:
        disposition = "UNDETERMINED"
    else:
        disposition = answers["route_disposition"]["value"]

    def _resolved(qid: str):
        return answers[qid]["value"] if qid in answers else None

    unrouted = any(_resolved(k) == "UNROUTED" for k in ("entry_anchor", "guard_anchor", "target_owner"))
    if unrouted and disposition == "ADMIT_TO_NEUTRAL":
        disposition = "REJECT_BOUNDARY"

    guard_verdicts = {
        qid: answers[qid]["value"]
        for qid in sorted(answers)
        if qid.startswith("guard_") and qid.endswith("_satisfied")
    }
    effect_verdicts = {
        qid: answers[qid]["value"]
        for qid in sorted(answers)
        if qid.startswith("effect_") and qid.endswith("_permitted")
    }

    return {
        "schema": DECODING_SCHEMA,
        "ingredient": INGREDIENT_ID,
        "design_id": batch["design_id"],
        "mode": result["mode"],
        "model": result["model"],
        "provenance": result["provenance"],
        "disposition": disposition,
        "review_required": bool(unknowns) or disposition != "ADMIT_TO_NEUTRAL",
        "route": {
            "entry": _resolved("entry_anchor"),
            "guard": _resolved("guard_anchor"),
            "owner": _resolved("target_owner"),
        },
        "guard_verdicts": guard_verdicts,
        "effect_verdicts": effect_verdicts,
        "rubric_score": answers["route_confidence_rubric"]["value"],
        "unknowns": unknowns,
        "decision_result": result,
        "authority": "NONE",
        "baker_acceptance": "NOT_GRANTED",
    }


__all__ = [
    "ALLOWED_DECISION_MODELS",
    "ALLOWED_GEMINI_DECISION_MODELS",
    "ALLOWED_OPENROUTER_DECISION_MODELS",
    "BATCH_SCHEMA",
    "CAPABILITY_ID",
    "DECISIONS_ENDPOINT",
    "DECODE_DISPOSITIONS",
    "DECODE_RUBRIC",
    "DECODING_SCHEMA",
    "DEFAULT_BOOST_PROVIDER",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_MODEL",
    "DEFAULT_OPENROUTER_MODEL",
    "DISPOSITIONS",
    "DeterministicDecisionEngine",
    "ECONOMY_RUBRIC",
    "ENCODING_SCHEMA",
    "GEMINI_DECISIONS_ENDPOINT",
    "GeminiDecisionBoostAdapter",
    "INGREDIENT_ID",
    "MAX_QUESTIONS",
    "MAX_RESPONSE_BYTES",
    "MAX_UNITS",
    "OPCODES",
    "OPENROUTER_DECISIONS_ENDPOINT",
    "OpenRouterDecisionBoostAdapter",
    "POLARITIES",
    "RESULT_SCHEMA",
    "STAGES",
    "SUPPORTED_BOOST_PROVIDERS",
    "build_decode_batch",
    "build_encode_batch",
    "create_decision_boost_adapter",
    "decode_through_anchor",
    "encode_to_anchor",
    "extract_candidate_units",
    "involves_anchor_coding",
    "recipe_boost_status",
    "to_gemini_decisions_request",
    "to_openrouter_decisions_request",
    "validate_batch",
    "validate_result",
]
