import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from mantleos import anchor_design, anchors
from mantleos.anchor_decision_boost import (
    DEFAULT_BOOST_PROVIDER,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    DeterministicDecisionEngine,
    GeminiDecisionBoostAdapter,
    OpenRouterDecisionBoostAdapter,
    SUPPORTED_BOOST_PROVIDERS,
    build_decode_batch,
    build_encode_batch,
    create_decision_boost_adapter,
    decode_through_anchor,
    encode_to_anchor,
    involves_anchor_coding,
    recipe_boost_status,
    to_gemini_decisions_request,
    to_openrouter_decisions_request,
    validate_result,
)
from mantleos.anchor_engine.tools import anchor_structure
from mantleos.kpp.cli import main as kpp_main
from mantleos.kpp.core import ingredient_catalog, read_json, validate_recipe
from mantleos.kpp.language import implementation_plan
from mantleos.kpp.pantry import discover as pantry_discover, view as pantry_view
from mantleos.kpp.pantry_index import fit as pantry_fit
from mantleos.kpp.workshop import begin as workshop_begin, handoff as workshop_handoff

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "tools/export_kpp.py").is_file())

SAMPLE_PY = '''def receive_request(payload):
    """Parse and ingest external request payload."""
    return parse_json(payload)

def validate_payload(record):
    """Enforce schema boundary and reject malformed requests."""
    if not record.get("ok"):
        raise ValueError("invalid")
    return True

def commit_state(store, record):
    """Persist validated record into state ledger."""
    store.save(record)
    return store

def format_reply(record):
    """Format committed record text."""
    return str(record)
'''


class AnchorDecisionBoostTests(unittest.TestCase):
    def test_offline_deterministic_encode_produces_valid_design_molecules_and_obligations(self):
        encoded = encode_to_anchor(
            SAMPLE_PY,
            design_id="RequestPipeline",
            goal="Validate external requests before committing to durable state ledger",
        )
        self.assertEqual(encoded["schema"], "anchor.decision-encoding/1")
        self.assertEqual(encoded["mode"], "DETERMINISTIC_OFFLINE")
        self.assertEqual(encoded["provenance"], "source_extracted")
        self.assertEqual(encoded["authority"], "NONE")
        self.assertEqual(encoded["baker_acceptance"], "NOT_GRANTED")
        self.assertFalse(encoded["review_required"])

        design = anchor_design.validate(encoded["design"])
        for app in design["applications"]:
            anchors.validate(app)
        shapes = anchor_structure.check_structures(encoded["molecule_source"], all_types=True)
        self.assertEqual({s.id for s in shapes}, {a["id"] for a in design["applications"]})

        # Verify generated design + obligations drop cleanly into a valid kpp.recipe/4.
        recipe = {
            "schema": "kpp.recipe/4",
            "id": "encoded-pipeline-check",
            "goal": design["purpose"],
            "mode": "composition",
            "tissue": "mixed",
            "fidelity": 1,
            "target": {"description": "Encoded pipeline"},
            "ingredients": ["anchor-decision-boost"],
            "oven": {
                "assumption": "Offline deterministic encoding",
                "provider": "local",
                "iterations": "1",
                "implementation": "incremental",
                "verification": "Baker acceptance",
            },
            "acceptance": "Evidence required",
            "anchors": encoded["obligations"],
            "product_kind": "conventional",
            "delivery_mode": "artifact",
            "capabilities": {},
            "implementation": {
                "components": [
                    {"id": "app", "policy": "required", "languages": ["python"]},
                    {"id": "contract", "policy": "required", "languages": ["anchor"], "profile": "EMIT_TEXT/0.2"},
                ]
            },
            "construction": {"techniques": []},
            "anchor_binding": "none",
            "anchor_design": design,
        }
        validate_recipe(recipe)

    def test_offline_deterministic_encode_supports_scan_report_and_spec_text(self):
        scan_like = {
            "schema": "kpp.static-scan/1",
            "native_report": {
                "schema": "scan.report/1",
                "graph": {
                    "nodes": [
                        {"id": "n1", "kind": "function", "name": "parse_packet", "path": "net.py"},
                        {"id": "n2", "kind": "function", "name": "verify_signature", "path": "auth.py"},
                        {"id": "n3", "kind": "function", "name": "write_ledger", "path": "db.py"},
                    ],
                    "edges": [],
                },
            },
        }
        res_scan = encode_to_anchor(scan_like, design_id="ScanDesign", goal="Route parsed verified ledger writes")
        self.assertGreaterEqual(len(res_scan["design"]["applications"]), 3)

        spec_text = "\n".join([
            "ingest: Receive external JSON request input",
            "auth_check: Guard and verify capability token before write",
            "state_store: Update append-only state record",
        ])
        res_spec = encode_to_anchor(spec_text, design_id="SpecDesign", goal="Specify boundary-guarded state store")
        types = {a["type"] for a in res_spec["design"]["applications"]}
        self.assertEqual(types, {"BlackHole", "WhiteHole", "Neutral"})

    def test_offline_deterministic_decode_routes_and_gates_stimuli(self):
        recipe = read_json(ROOT / "recipes/anchor-decision-boost-v4.json")

        admitted = decode_through_anchor(recipe, {"operation": "encode", "preconditions_met": True})
        self.assertEqual(admitted["schema"], "anchor.decision-decoding/1")
        self.assertEqual(admitted["mode"], "DETERMINISTIC_OFFLINE")
        self.assertEqual(admitted["disposition"], "ADMIT_TO_NEUTRAL")
        self.assertEqual(admitted["route"]["entry"], "INTAKE_GATE")
        self.assertEqual(admitted["route"]["guard"], "CONFIDENCE_GUARD")
        self.assertEqual(admitted["route"]["owner"], "DECISION_CORE")
        self.assertEqual(admitted["authority"], "NONE")

        held = decode_through_anchor(recipe, {"operation": "encode", "guard_passed": False})
        self.assertEqual(held["disposition"], "HOLD_FOR_GUARD")
        self.assertTrue(held["review_required"])

        rejected = decode_through_anchor(recipe, {"operation": "encode", "boundary_valid": False})
        self.assertEqual(rejected["disposition"], "REJECT_BOUNDARY")

        # Also works against recipes without an explicit anchor_design (projects canonically).
        legacy_recipe = read_json(ROOT / "recipes/notepad-demo.json")
        legacy_decoded = decode_through_anchor(legacy_recipe, {"operation": "save", "guard_passed": True})
        self.assertEqual(legacy_decoded["disposition"], "ADMIT_TO_NEUTRAL")
        self.assertEqual(legacy_decoded["route"]["entry"], "BH_RECIPE_ENTRY")

    def test_gemini_decision_boost_encode_consolidation_and_provenance(self):
        recipe = read_json(ROOT / "recipes/anchor-decision-boost-v4.json")
        captured_requests = []

        def fake_gemini_decisions(request_payload):
            captured_requests.append(request_payload)
            answers = {}
            for qid, spec in request_payload["questions"].items():
                if spec["type"] == "score":
                    answers[qid] = {"score": 4, "confidence": 0.94}
                elif qid.endswith("_polarity"):
                    if qid.startswith("u_0"):
                        answers[qid] = {"choice": "BlackHole", "confidence": 0.96}
                    elif qid.startswith("u_1"):
                        answers[qid] = {"choice": "WhiteHole", "confidence": 0.97}
                    else:
                        answers[qid] = {"choice": "Neutral", "confidence": 0.95}
                elif qid.endswith("_opcode"):
                    val = "20" if qid.startswith("u_0") else "10" if qid.startswith("u_1") else "01" if qid.startswith("u_3") else "30"
                    answers[qid] = {"choice": val, "confidence": 0.92}
                elif qid.endswith("_stage"):
                    val = "REACH" if qid.startswith("u_0") else "QUALIFY" if qid.startswith("u_1") else "ROUTE"
                    answers[qid] = {"choice": val, "confidence": 0.93}
                elif qid.endswith("_owns_state"):
                    answers[qid] = {"noul": 0.91 if qid.startswith("u_2") else 0.08, "confidence": 0.90}
                elif qid.endswith("_guards_effect"):
                    answers[qid] = {"noul": 0.95 if qid.startswith("u_1") else 0.09, "confidence": 0.91}
                elif qid.endswith("_economy_merge"):
                    # Merge u_3 (format_reply) into u_2 (commit_state) under N-RULE-ECONOMY.
                    answers[qid] = {"noul": 0.92 if qid.startswith("u_3") else 0.12, "confidence": 0.91}
            return {"answers": answers}

        adapter = GeminiDecisionBoostAdapter(transport=fake_gemini_decisions, confidence_threshold=0.70, budget_calls=4)
        result = encode_to_anchor(
            SAMPLE_PY,
            design_id="BoostedPipeline",
            goal="Fast calibrated Anchor encoding",
            recipe=recipe,
            decision_provider=adapter,
        )
        self.assertEqual(len(captured_requests), 1)
        self.assertEqual(captured_requests[0]["model"], DEFAULT_GEMINI_MODEL)
        self.assertEqual(adapter.calls_used, 1)
        self.assertEqual(result["mode"], "DECISION_AI_BOOST")
        self.assertEqual(result["model"], "gemini-decision-1")
        self.assertEqual(result["provenance"], "model_inferred")
        self.assertEqual(result["authority"], "NONE")
        self.assertEqual(result["baker_acceptance"], "NOT_GRANTED")
        self.assertEqual(result["consolidated_unit_count"], 1)
        # u_3 (format_reply) merged into u_2 (COMMIT_STATE).
        self.assertEqual(result["unit_assignments"]["format_reply"], result["unit_assignments"]["commit_state"])
        self.assertEqual(len(result["design"]["applications"]), 3)

    def test_low_confidence_decision_ai_fails_closed_to_undetermined(self):
        recipe = read_json(ROOT / "recipes/anchor-decision-boost-v4.json")

        def uncertain_gemini(request_payload):
            answers = {}
            for qid, spec in request_payload["questions"].items():
                if spec["type"] == "choice":
                    choice = "ADMIT_TO_NEUTRAL" if qid == "route_disposition" else spec["criteria"][0]
                    conf = 0.42 if qid == "route_disposition" else 0.95
                    answers[qid] = {"choice": choice, "confidence": conf}
                elif spec["type"] == "noul":
                    conf = 0.48 if qid.startswith("guard_") else 0.93
                    answers[qid] = {"noul": 0.90, "confidence": conf}
                else:
                    answers[qid] = {"score": 4, "confidence": 0.90}
            return {"answers": answers}

        adapter = GeminiDecisionBoostAdapter(transport=uncertain_gemini, confidence_threshold=0.70)
        decoded = decode_through_anchor(
            recipe,
            {"operation": "ambiguous_effect"},
            decision_provider=adapter,
        )
        self.assertEqual(decoded["disposition"], "UNDETERMINED")
        self.assertTrue(decoded["review_required"])
        unknown_qids = {u["question_id"] for u in decoded["unknowns"]}
        self.assertIn("route_disposition", unknown_qids)
        self.assertIn("guard_CONFIDENCE_GUARD_satisfied", unknown_qids)
        self.assertEqual(decoded["authority"], "NONE")

    def test_recipe_boundary_budget_and_validation_refusals(self):
        recipe_without_boost = read_json(ROOT / "recipes/conventional-python-v4.json")
        self.assertFalse(recipe_boost_status(recipe_without_boost)["enabled"])

        adapter = GeminiDecisionBoostAdapter(transport=lambda req: {"answers": {}}, budget_calls=1)
        with self.assertRaisesRegex(ValueError, "does not select"):
            encode_to_anchor(
                SAMPLE_PY,
                design_id="BlockedDesign",
                goal="Blocked boost attempt",
                recipe=recipe_without_boost,
                decision_provider=adapter,
            )

        with self.assertRaisesRegex(ValueError, "Unsupported Decision AI model"):
            GeminiDecisionBoostAdapter(model="gemini-3.8-flash")

        no_key_adapter = GeminiDecisionBoostAdapter()
        batch = build_encode_batch(SAMPLE_PY, design_id="NoNet", goal="Verify no implicit network")
        with self.assertRaisesRegex(ValueError, "explicit api_key or transport"):
            no_key_adapter.evaluate(batch)

        # Single-use budget enforcement.
        decode_batch = build_decode_batch(read_json(ROOT / "recipes/anchor-decision-boost-v4.json"), {"op": "read"})
        baseline = DeterministicDecisionEngine().evaluate(decode_batch)
        raw = {qid: {("choice" if entry["type"] == "choice" else entry["type"]): (entry["proposed_value"] if entry["type"] == "choice" else entry.get("noul", entry.get("score"))), "confidence": 0.9}
               for qid, entry in baseline["answers"].items()}
        one_shot = GeminiDecisionBoostAdapter(transport=lambda req: {"answers": raw}, budget_calls=1)
        one_shot.evaluate(decode_batch)
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            one_shot.evaluate(decode_batch)

        # Bad choice value outside criteria must be rejected.
        bad_raw = json.loads(json.dumps(raw))
        bad_raw["route_disposition"]["choice"] = "GRANT_BAKER_APPROVAL"
        bad_adapter = GeminiDecisionBoostAdapter(transport=lambda req: {"answers": bad_raw})
        with self.assertRaisesRegex(ValueError, "not in criteria"):
            bad_adapter.evaluate(decode_batch)

        # Batch payload shape check for Gemini v1beta/decisions.
        req = to_gemini_decisions_request(decode_batch)
        self.assertEqual(set(req), {"model", "input", "questions"})
        self.assertEqual(req["model"], "gemini-decision-1")

    def test_pantry_discovery_fit_and_cli_roundtrip(self):
        label = pantry_view(ROOT, "anchor-decision-boost", level="label")
        self.assertEqual(label["status"], "ready")
        contract = pantry_view(ROOT, "anchor-decision-boost", level="contract")
        self.assertEqual(contract["provides"], ["anchor-decision-boost/1"])

        recipe_path = ROOT / "recipes/anchor-decision-boost-v4.json"
        recipe = read_json(recipe_path)
        fit_report = pantry_fit(ingredient_catalog(ROOT, check_sources=False), recipe=recipe)
        self.assertTrue(all(item["declared_inputs_satisfied"] for item in fit_report["ingredients"]))

        def run_cli(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = kpp_main(list(argv))
            self.assertEqual(code, 0)
            return json.loads(out.getvalue())

        status = run_cli("anchor-decision", "status", "--recipe", str(recipe_path))
        self.assertTrue(status["enabled"])

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            src = d / "sample.py"
            src.write_text(SAMPLE_PY, encoding="utf-8")
            stim = d / "stimulus.json"
            stim.write_text(json.dumps({"operation": "encode", "preconditions_met": True}), encoding="utf-8")

            req = run_cli(
                "anchor-decision", "batch",
                "--input", str(src),
                "--id", "CliDesign",
                "--goal", "CLI batch check",
                "--gemini-request",
            )
            self.assertEqual(req["model"], "gemini-decision-1")
            self.assertGreater(len(req["questions"]), 1)

            encoded = run_cli(
                "anchor-decision", "encode",
                "--input", str(src),
                "--id", "CliDesign",
                "--goal", "CLI encode check",
                "--recipe", str(recipe_path),
            )
            self.assertEqual(encoded["mode"], "DETERMINISTIC_OFFLINE")

            # Feed a recorded v1beta/decisions-style response through CLI --responses.
            dec_batch = build_decode_batch(recipe, {"operation": "encode"})
            answers = {}
            for qid, spec in dec_batch["questions"].items():
                if spec["type"] == "choice":
                    answers[qid] = {"choice": "ADMIT_TO_NEUTRAL" if qid == "route_disposition" else spec["criteria"][0], "confidence": 0.91}
                elif spec["type"] == "noul":
                    answers[qid] = {"noul": 0.92, "confidence": 0.91}
                else:
                    answers[qid] = {"score": 4, "confidence": 0.91}
            resp_path = d / "responses.json"
            resp_path.write_text(json.dumps({"answers": answers}), encoding="utf-8")

            decoded = run_cli(
                "anchor-decision", "decode",
                "--contract", str(recipe_path),
                "--stimulus", str(stim),
                "--recipe", str(recipe_path),
                "--provider", "gemini",
                "--responses", str(resp_path),
            )
            self.assertEqual(decoded["mode"], "DECISION_AI_BOOST")
            self.assertEqual(decoded["model"], "gemini-decision-1")
            self.assertEqual(decoded["disposition"], "ADMIT_TO_NEUTRAL")

            or_req = run_cli(
                "anchor-decision", "batch",
                "--input", str(src),
                "--id", "CliDesign",
                "--goal", "OpenRouter batch check",
                "--openrouter-request",
            )
            self.assertEqual(or_req["model"], DEFAULT_OPENROUTER_MODEL)
            self.assertIn("state", or_req)
            self.assertIn("questions", or_req)

    def test_openrouter_decider_provider_default_wire_contract_and_factory(self):
        self.assertEqual(DEFAULT_BOOST_PROVIDER, "openrouter")
        self.assertEqual(DEFAULT_MODEL, "perplexity/pplx-decider-v1.2")
        self.assertEqual(SUPPORTED_BOOST_PROVIDERS, ("openrouter", "gemini"))

        default_adapter = create_decision_boost_adapter(transport=lambda req: {"answers": {}})
        self.assertIsInstance(default_adapter, OpenRouterDecisionBoostAdapter)
        self.assertEqual(default_adapter.model, "perplexity/pplx-decider-v1.2")

        gemini_adapter = create_decision_boost_adapter(provider="gemini", transport=lambda req: {"answers": {}})
        self.assertIsInstance(gemini_adapter, GeminiDecisionBoostAdapter)
        self.assertEqual(gemini_adapter.model, "gemini-decision-1")

        with self.assertRaisesRegex(ValueError, "Unsupported Decider provider"):
            create_decision_boost_adapter(provider="unknown-provider")

        with self.assertRaisesRegex(ValueError, "Unsupported Decision AI model"):
            OpenRouterDecisionBoostAdapter(model="openai/gpt-4o")

        # OpenRouter /api/alpha/decisions payload requires record criteria on choice,
        # instructions instead of question, and top-level state.
        recipe = read_json(ROOT / "recipes/anchor-decision-boost-v4.json")
        enc_batch = build_encode_batch(SAMPLE_PY, design_id="OpenRouterTest", goal="OpenRouter Decider wire check")
        or_payload = to_openrouter_decisions_request(enc_batch, model="perplexity/pplx-decider-flash-v1.2")
        self.assertEqual(or_payload["model"], "perplexity/pplx-decider-flash-v1.2")
        self.assertEqual(set(or_payload), {"model", "state", "questions"})
        self.assertIsInstance(or_payload["questions"]["u_0_polarity"]["criteria"], dict)
        self.assertEqual(set(or_payload["questions"]["u_0_polarity"]["criteria"]), {"BlackHole", "WhiteHole", "Neutral"})
        self.assertIn("instructions", or_payload["questions"]["u_0_polarity"])
        self.assertIsInstance(or_payload["questions"]["batch_rule_economy"]["criteria"], list)

        # Simulate authentic OpenRouter Decider V1.2 response:
        # - noul has no explicit confidence field -> derived from max(p, 1 - p)
        # - choice has probabilities dict + confidence
        # - score uses 0-indexed legend (0..3) normalized onto 1..4 rubric
        captured = []

        def fake_openrouter_encode(payload):
            captured.append(payload)
            answers = {}
            for qid, spec in payload["questions"].items():
                if spec["type"] == "score":
                    answers[qid] = {
                        "type": "score",
                        "score": 2.85,
                        "legend": {str(i): label for i, label in enumerate(spec["criteria"])},
                        "probabilities": {"0": 0.01, "1": 0.04, "2": 0.04, "3": 0.91},
                        "confidence": 0.90,
                    }
                elif qid.endswith("_polarity"):
                    pol = "BlackHole" if qid.startswith("u_0") else "WhiteHole" if qid.startswith("u_1") else "Neutral"
                    answers[qid] = {
                        "type": "choice",
                        "choice": pol,
                        "probabilities": {opt: (0.94 if opt == pol else 0.03) for opt in spec["criteria"]},
                        "confidence": 0.91,
                    }
                elif qid.endswith("_opcode"):
                    val = "20" if qid.startswith("u_0") else "10" if qid.startswith("u_1") else "01" if qid.startswith("u_3") else "30"
                    answers[qid] = {"type": "choice", "choice": val, "probabilities": {val: 0.93}, "confidence": 0.91}
                elif qid.endswith("_stage"):
                    val = "REACH" if qid.startswith("u_0") else "QUALIFY" if qid.startswith("u_1") else "ROUTE"
                    answers[qid] = {"type": "choice", "choice": val, "probabilities": {val: 0.92}, "confidence": 0.89}
                elif qid.endswith("_owns_state"):
                    answers[qid] = {"type": "noul", "noul": 0.95 if qid.startswith("u_2") else 0.06}
                elif qid.endswith("_guards_effect"):
                    answers[qid] = {"type": "noul", "noul": 0.94 if qid.startswith("u_1") else 0.05}
                elif qid.endswith("_economy_merge"):
                    answers[qid] = {"type": "noul", "noul": 0.91 if qid.startswith("u_3") else 0.10}
            return {
                "model": "perplexity/pplx-decider-v1.2-20261016",
                "answers": answers,
                "usage": {"input_tokens": 310, "output_tokens": 27, "cost": 0.0000062},
            }

        adapter = OpenRouterDecisionBoostAdapter(transport=fake_openrouter_encode, confidence_threshold=0.70)
        encoded = encode_to_anchor(
            SAMPLE_PY,
            design_id="OpenRouterEncoded",
            goal="OpenRouter Decider V1.2 encode",
            recipe=recipe,
            decision_provider=adapter,
        )
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["model"], "perplexity/pplx-decider-v1.2")
        self.assertEqual(encoded["mode"], "DECISION_AI_BOOST")
        self.assertEqual(encoded["model"], "perplexity/pplx-decider-v1.2")
        self.assertEqual(encoded["decision_result"]["answers"]["batch_rule_economy"]["score"], 3.85)
        self.assertEqual(encoded["consolidated_unit_count"], 1)
        self.assertEqual(adapter.last_usage["input_tokens"], 310)

        # Low-confidence noul (e.g. p=0.54 without confidence key -> 0.54 < 0.70) fails closed.
        dec_batch = build_decode_batch(recipe, {"operation": "unverified"})
        low_conf_answers = {}
        for qid, spec in dec_batch["questions"].items():
            if spec["type"] == "noul":
                low_conf_answers[qid] = {"type": "noul", "noul": 0.54}
            elif spec["type"] == "choice":
                low_conf_answers[qid] = {"type": "choice", "choice": spec["criteria"][0], "probabilities": {spec["criteria"][0]: 0.95}}
            else:
                low_conf_answers[qid] = {"type": "score", "score": 2.9, "legend": {str(i): c for i, c in enumerate(spec["criteria"])}, "probabilities": {"3": 0.95}}
        validated = validate_result(
            dec_batch,
            low_conf_answers,
            mode="DECISION_AI_BOOST",
            model="perplexity/pplx-decider-v1.2",
            provenance="model_inferred",
            confidence_threshold=0.70,
        )
        self.assertTrue(any(q.startswith("guard_") for q in validated["undetermined_questions"]))
        self.assertEqual(validated["answers"]["route_confidence_rubric"]["score"], 3.9)

        # Recipe with openrouter-mind surfaces OpenRouter default boost awareness cleanly.
        or_recipe = json.loads(json.dumps(read_json(ROOT / "recipes/journal-engram-design.json")))
        or_recipe["ingredients"] = list(or_recipe["ingredients"]) + ["openrouter-mind"]
        st = recipe_boost_status(or_recipe)
        self.assertEqual(st["default_mode"], "DETERMINISTIC_OFFLINE")
        self.assertEqual(st["default_boost_provider"], "openrouter")
        self.assertEqual(st["supported_boost_providers"], ["openrouter", "gemini"])
        self.assertTrue(st["openrouter_mind_present"])
        self.assertIn("OpenRouter API key", st["advisory"])

    def test_anchor_recipe_detection_and_advisory_recommendation_surfaces(self):
        # 1. Unbound conventional recipe/4 gets OPTIONAL with no Anchor signals.
        conventional = read_json(ROOT / "recipes/conventional-python-v4.json")
        self.assertEqual(
            involves_anchor_coding(conventional),
            {"involves_anchor_coding": False, "anchor_signals": []},
        )
        conv_status = recipe_boost_status(conventional)
        self.assertEqual(conv_status["recommendation"], "OPTIONAL")
        self.assertFalse(conv_status["involves_anchor_coding"])
        self.assertFalse(conv_status["enabled"])

        conv_plan = implementation_plan(conventional)
        self.assertEqual(conv_plan["anchor_decision_boost"]["recommendation"], "OPTIONAL")
        self.assertEqual(conv_plan["recommended_optional_ingredients"], [])

        catalog = ingredient_catalog(ROOT, check_sources=False)
        conv_fit = pantry_fit(catalog, recipe=conventional)
        self.assertEqual(conv_fit["recommended_optional"], [])

        # 2. All Anchor coding signal variants trigger RECOMMENDED_OPTIONAL when not yet selected.
        signal_cases = []
        # (a) kpp.recipe/3 legacy binding
        signal_cases.append(("recipe3", read_json(ROOT / "recipes/notepad-demo.json"), "anchor_binding:shared-neutral"))

        # (b) explicit shared-neutral anchor_binding on recipe/4
        r_binding = json.loads(json.dumps(conventional))
        r_binding["anchor_binding"] = "shared-neutral"
        signal_cases.append(("shared_neutral", r_binding, "anchor_binding:shared-neutral"))

        # (c) tissue == "anchor" + component language "anchor"
        r_tissue = json.loads(json.dumps(conventional))
        r_tissue["tissue"] = "anchor"
        r_tissue["implementation"]["components"][0]["languages"] = ["anchor"]
        signal_cases.append(("tissue_anchor", r_tissue, "tissue:anchor"))
        signal_cases.append(("comp_lang_anchor", r_tissue, "component_language:anchor"))

        # (d) Anchor ingredient present (e.g. anchor-tissue)
        r_ing = json.loads(json.dumps(conventional))
        r_ing["ingredients"] = ["anchor-tissue"]
        signal_cases.append(("anchor_ingredient", r_ing, "anchor_ingredient"))

        # (e) anchor_design + design_anchors on real Anchor recipe
        engram_design = read_json(ROOT / "recipes/journal-engram-design.json")
        signal_cases.append(("anchor_design", engram_design, "anchor_design"))
        signal_cases.append(("typed_obligations", engram_design, "typed_anchor_obligations"))

        for label, case_recipe, expected_signal in signal_cases:
            with self.subTest(label=label):
                validate_recipe(case_recipe)
                info = involves_anchor_coding(case_recipe)
                self.assertTrue(info["involves_anchor_coding"])
                self.assertIn(expected_signal, info["anchor_signals"])
                status = recipe_boost_status(case_recipe)
                self.assertEqual(status["recommendation"], "RECOMMENDED_OPTIONAL")
                self.assertFalse(status["enabled"])

        # 3. Advisory surface checks on journal-engram-design (Anchor recipe without anchor-decision-boost).
        eng_plan = implementation_plan(engram_design)
        self.assertEqual(eng_plan["anchor_decision_boost"]["recommendation"], "RECOMMENDED_OPTIONAL")
        self.assertEqual(eng_plan["recommended_optional_ingredients"], ["anchor-decision-boost"])

        eng_fit = pantry_fit(catalog, recipe=engram_design)
        self.assertEqual(len(eng_fit["recommended_optional"]), 1)
        self.assertEqual(eng_fit["recommended_optional"][0]["id"], "anchor-decision-boost")
        self.assertEqual(eng_fit["recommended_optional"][0]["policy"], "recommended_optional")

        # 4. Pantry discovery via department:languages includes anchor-decision-boost.
        lang_found = pantry_discover(ROOT, "department:languages", tissue="anchor")
        self.assertIn("anchor-decision-boost", [m["id"] for m in lang_found["matches"]])

        # 5. Selected Anchor recipe reports SELECTED and clears recommended_optional duplicate nudge.
        selected_recipe = read_json(ROOT / "recipes/anchor-decision-boost-v4.json")
        sel_status = recipe_boost_status(selected_recipe)
        self.assertEqual(sel_status["recommendation"], "SELECTED")
        self.assertTrue(sel_status["enabled"])
        self.assertTrue(sel_status["involves_anchor_coding"])

        sel_plan = implementation_plan(selected_recipe)
        self.assertEqual(sel_plan["anchor_decision_boost"]["recommendation"], "SELECTED")
        self.assertEqual(sel_plan["recommended_optional_ingredients"], [])

        sel_fit = pantry_fit(catalog, recipe=selected_recipe)
        self.assertEqual(sel_fit["recommended_optional"], [])

        # 6. Handoff contract carries Anchor decision boost status.
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            workshop_begin(ws, engram_design, ROOT)
            handoff_text = workshop_handoff(ws)
            self.assertIn("Anchor decision boost:", handoff_text)
            self.assertIn("RECOMMENDED_OPTIONAL", handoff_text)


if __name__ == "__main__":
    unittest.main()
