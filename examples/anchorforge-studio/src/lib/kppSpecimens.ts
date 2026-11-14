import nativeNotepad from '../specimens/notepad.anchor?raw';
import {
  PRIMER_EMIT_TEXT_V0_2,
  PRIMER_AGENTIC_V0_2,
  createAnchorApplication,
  AnchorDesignContract,
  ArtifactKind,
} from './kppEngine';

export interface KppSpecimen {
  id: string;
  title: string;
  filename: string;
  kind: ArtifactKind;
  category: 'Executable Blueprint' | 'Responsibility Design' | 'Agentic & Multi-Polarity';
  description: string;
  repoPath: string;
  content: string;
}

const HELLO_WORLD_ANCHOR = `ANCHOR BLUEPRINT: HelloWorld
STATUS: EXPERIMENTAL EMIT_TEXT/0.2

${PRIMER_EMIT_TEXT_V0_2}

BEGIN MOLECULE HelloWorld
A: Neutral -01 -00 -text="Hello, World!"
END MOLECULE

BEGIN EXECUTION
RUN HelloWorld
END EXECUTION
`;

const CHASE_STOP_ANCHOR = `ANCHOR BLUEPRINT: ChaseStop
STATUS: EXPERIMENTAL EMIT_TEXT/0.2

${PRIMER_EMIT_TEXT_V0_2}

BEGIN MOLECULE ChaseStop
Body: Neutral -01 -00 -text="\\"\\"\\"Scoped Chase gate comparing candidate with a pinned performance target.\\"\\"\\"\\nimport argparse\\nimport json\\n\\ndef assess(reference_ms, candidate_ms, behavior_equal, tests_pass, tolerance):\\n    if min(reference_ms, candidate_ms) < 0 or reference_ms == 0 or tolerance < 1:\\n        raise ValueError(\\"Invalid timing/tolerance\\")\\n    ratio = candidate_ms / reference_ms\\n    satisfied = bool(behavior_equal and tests_pass and ratio <= tolerance)\\n    return {\\"status\\": \\"TARGET_REACHED_WITHIN_CHECK_SCOPE\\" if satisfied else \\"CHASE_ACTIVE\\",\\n            \\"next\\": \\"OTHER_UNMET_TARGET\\" if satisfied else \\"THIS_TARGET\\",\\n            \\"ratio\\": round(ratio, 6), \\"scope\\": \\"supplied test and latency inputs only\\"}\\n\\nif __name__ == \\"__main__\\":\\n    p=argparse.ArgumentParser()\\n    p.add_argument(\\"--reference-ms\\",type=float,required=True)\\n    p.add_argument(\\"--candidate-ms\\",type=float,required=True)\\n    p.add_argument(\\"--behavior-equal\\",action=\\"store_true\\")\\n    p.add_argument(\\"--tests-pass\\",action=\\"store_true\\")\\n    p.add_argument(\\"--tolerance\\",type=float,default=1.05)\\n    a=p.parse_args()\\n    print(json.dumps(assess(a.reference_ms,a.candidate_ms,a.behavior_equal,a.tests_pass,a.tolerance)))\\n"
END MOLECULE

BEGIN EXECUTION
RUN ChaseStop
END EXECUTION
`;

const INTENT_BOUNDARY_ANCHOR = `ANCHOR BLUEPRINT: IntentBoundary
STATUS: EXPERIMENTAL EMIT_TEXT/0.2

${PRIMER_EMIT_TEXT_V0_2}

BEGIN MOLECULE IntentBoundary
Body: Neutral -01 -00 -text="\\"\\"\\"Small body-side intent admission demonstration (no arbitrary command execution).\\"\\"\\"\\nimport json\\nimport sys\\n\\nALLOWED = {\\"remember\\": \\"memory.append\\", \\"recall\\": \\"memory.read\\", \\"observe\\": \\"activity.record\\"}\\n\\ndef handle(intent):\\n    if not isinstance(intent, dict):\\n        return {\\"accepted\\": False, \\"reason\\": \\"intent must be an object\\"}\\n    action = intent.get(\\"action\\")\\n    if action not in ALLOWED:\\n        return {\\"accepted\\": False, \\"reason\\": \\"action not admitted\\"}\\n    payload = intent.get(\\"payload\\", {})\\n    if not isinstance(payload, dict) or len(json.dumps(payload)) > 4096:\\n        return {\\"accepted\\": False, \\"reason\\": \\"invalid or oversized payload\\"}\\n    return {\\"accepted\\": True, \\"body_operation\\": ALLOWED[action], \\"proposal\\": payload,\\n            \\"note\\": \\"No operation is executed by this boundary.\\"}\\n\\nif __name__ == \\"__main__\\":\\n    try:\\n        request = json.load(sys.stdin)\\n        print(json.dumps(handle(request), sort_keys=True))\\n    except (ValueError, TypeError):\\n        print(json.dumps({\\"accepted\\": False, \\"reason\\": \\"invalid JSON\\"}))\\n"
END MOLECULE

BEGIN EXECUTION
RUN IntentBoundary
END EXECUTION
`;

const MEMORY_LEDGER_ANCHOR = `ANCHOR BLUEPRINT: MemoryLedger
STATUS: EXPERIMENTAL EMIT_TEXT/0.2

${PRIMER_EMIT_TEXT_V0_2}

BEGIN MOLECULE MemoryLedger
Body: Neutral -01 -00 -text="\\"\\"\\"Append-only, hash-linked JSONL records (demonstration, not a secure ledger).\\"\\"\\"\\nimport argparse\\nimport hashlib\\nimport json\\nfrom pathlib import Path\\n\\nZERO = \\"0\\" * 64\\n\\ndef canonical(obj):\\n    return json.dumps(obj, sort_keys=True, separators=(\\",\\", \\":\\"), ensure_ascii=False)\\n\\ndef read_records(path):\\n    previous = ZERO\\n    result = []\\n    if not path.exists():\\n        return result\\n    for raw in path.read_text(encoding=\\"utf-8\\").splitlines():\\n        record = json.loads(raw)\\n        if record[\\"previous\\"] != previous or record[\\"index\\"] != len(result):\\n            raise ValueError(\\"Memory link mismatch\\")\\n        payload = {key: record[key] for key in (\\"index\\", \\"previous\\", \\"text\\")}\\n        if hashlib.sha256(canonical(payload).encode(\\"utf-8\\")).hexdigest() != record[\\"digest\\"]:\\n            raise ValueError(\\"Memory digest mismatch\\")\\n        previous = record[\\"digest\\"]\\n        result.append(record)\\n    return result\\n"
END MOLECULE

BEGIN EXECUTION
RUN MemoryLedger
END EXECUTION
`;

const AGENTIC_CONTINUITY_ANCHOR = `ANCHOR BLUEPRINT: AgenticContinuityLoop
STATUS: EXPERIMENTAL AGENTIC/0.2

${PRIMER_AGENTIC_V0_2}

BEGIN MOLECULE AgenticContinuityLoop
TaskIngress: BlackHole -40 -00 -input="task"
MindReasoner: Neutral -41 -00 -gateway="MIND.INFER"
ReadOnlyToolGuard: WhiteHole -42 -00 -permission="host_tool_allowlist"
ToolDispatcher: Neutral -43 -00 -tools=[]
EventTracer: Neutral -44 -00 -checkpoint="hash_chain"
StepBudgetGate: WhiteHole -45 -00 -limits={"steps":8,"tool_calls":4}
SessionCheckpoint: Neutral -49 -00 -session="portable_snapshot"
ContextProjector: Neutral -4B -00 -context={"max_messages":16}
Cancellation: WhiteHole -4C -00 -cancellation="explicit"
PortableHandoff: Neutral -4E -00 -handoff="json_or_chromamem"
LoopTerminator: Neutral -46 -00 -condition="final_or_budget"
END MOLECULE

BEGIN EXECUTION
RUN AgenticContinuityLoop
END EXECUTION
`;

export const ANCHOR_JOURNAL_DESIGN: AnchorDesignContract = {
  schema: 'anchor.design/1',
  id: 'Anchor-Journal',
  purpose: 'Portable continuity with compact responsibilities and durable exact replies.',
  applications: [
    createAnchorApplication(
      'BH-ENCOUNTER',
      'BlackHole',
      'Receive user input, semantic proposals and checked observations; normalize without changing canonical experience.'
    ),
    createAnchorApplication(
      'N-CONTINUITY',
      'Neutral',
      'Own identity bindings, append-only experience, recall and committed request/reply continuity.'
    ),
    createAnchorApplication(
      'N-HOST',
      'Neutral',
      'Coordinate PRIMER-first model frames, authorized host operations and verified portable handoff.'
    ),
    createAnchorApplication(
      'WH-INTEGRITY',
      'WhiteHole',
      'Enforce source, PRIMER, state, authority, observation, commit and release boundaries.'
    ),
  ],
  flows: [
    {
      from: 'BH-ENCOUNTER',
      to: 'WH-INTEGRITY',
      relationship: 'Validate input and bindings',
    },
    {
      from: 'WH-INTEGRITY',
      to: 'N-CONTINUITY',
      relationship: 'Admit checked records atomically',
    },
    {
      from: 'N-CONTINUITY',
      to: 'N-HOST',
      relationship: 'Project relevant committed memory',
    },
    {
      from: 'N-HOST',
      to: 'BH-ENCOUNTER',
      relationship: 'Receive semantic proposals and verified observations',
    },
  ],
  state: [
    { id: 'identity-bindings', owner: 'N-CONTINUITY' },
    { id: 'experience', owner: 'N-CONTINUITY' },
    { id: 'encounter-preparation', owner: 'N-HOST' },
  ],
  effects: [
    {
      id: 'checked-read',
      requester: 'N-HOST',
      guard: 'WH-INTEGRITY',
      confirmation: 'Host broker grants capability; verified observation binds reply.',
    },
    {
      id: 'reply-release',
      requester: 'N-HOST',
      guard: 'WH-INTEGRITY',
      confirmation: 'Release broker grants permission; release exact durable committed reply.',
    },
    {
      id: 'portable-export',
      requester: 'N-HOST',
      guard: 'WH-INTEGRITY',
      confirmation: 'Consistent verified export succeeds before reporting Save.',
    },
  ],
};

export const NOTEPAD_FIDELITY9_DESIGN_TXT = `# Notepad Fidelity 9 — human-readable design, NOT executable native .anchor
# 9 Anchors; exactly one new from Fidelity 8: WH-BLUEPRINT-GATE (WhiteHole)

BH-EDITOR-INPUT        BlackHole    capture raw intent, no permission or state change
N-DOCUMENT             Neutral      sole authoritative text/revision/clean baseline
WH-COMMAND-GUARD       WhiteHole    authorize runtime commands and host effects
N-EDIT-HISTORY         Neutral      sole undo/redo history + expected revision
N-EDITOR-SURFACE       Neutral      Tk GUI projection and runtime BH->WH routing
N-FILE-SESSION         Neutral      authorized UTF-8 file path/digest/persistence
N-CLIPBOARD-SELECTION  Neutral      selection and injected clipboard capability
N-SEARCH-REPLACE       Neutral      stateless literal search/replacement computation
WH-BLUEPRINT-GATE      WhiteHole    OFFLINE candidate build conformity (NEW)

FLOW:
N-EDITOR-SURFACE -> BH-EDITOR-INPUT: Forward GUI text changes, file, selection and clipboard intents through capture
BH-EDITOR-INPUT -> WH-COMMAND-GUARD: Pass captured, untrusted intent for validation
WH-COMMAND-GUARD -> N-DOCUMENT: Dispatch only validated in-memory actions to the state owner
WH-COMMAND-GUARD -> N-EDIT-HISTORY: Record successful edits or request undo/redo from the bound history owner
N-EDIT-HISTORY -> N-DOCUMENT: Apply undo/redo through the document state owner, preserving its clean baseline
WH-COMMAND-GUARD -> N-FILE-SESSION: Authorize UTF-8 disk read/write and clean baseline updates
WH-COMMAND-GUARD -> N-CLIPBOARD-SELECTION: Authorize selection range and host clipboard callbacks
WH-COMMAND-GUARD -> N-SEARCH-REPLACE: Request stateless literal find/replace range computation
WH-COMMAND-GUARD -> N-EDITOR-SURFACE: Return authoritative document snapshots for projection

STATE OWNERSHIP:
document-text -> N-DOCUMENT
document-revision -> N-DOCUMENT
clean-baseline -> N-DOCUMENT
undo-redo-stacks -> N-EDIT-HISTORY
expected-history-revision -> N-EDIT-HISTORY
transient-ui-projection -> N-EDITOR-SURFACE
active-file-path -> N-FILE-SESSION
confirmed-disk-digest -> N-FILE-SESSION
selection-capability -> N-CLIPBOARD-SELECTION

GUARDED EFFECTS:
utf8-file-read: N-FILE-SESSION -> WH-COMMAND-GUARD; Host path validated and UTF-8 bytes decoded without silent fallback.
utf8-file-write: N-FILE-SESSION -> WH-COMMAND-GUARD; Atomic write confirmed and baseline digest updated only on receipt.
clipboard-access: N-CLIPBOARD-SELECTION -> WH-COMMAND-GUARD; Injected host clipboard callback confirmed before state update.
blueprint-gate-verify: N-EDITOR-SURFACE -> WH-BLUEPRINT-GATE; Offline candidate build conformity checked against all 9 Anchors.
`;

export const KPP_SPECIMENS: KppSpecimen[] = [
  {
    id: 'hello-world',
    title: 'HelloWorld (EMIT_TEXT/0.2)',
    filename: 'hello_world_compact.anchor',
    kind: 'EMIT_TEXT/0.2',
    category: 'Executable Blueprint',
    description:
      'Canonical minimal EMIT_TEXT/0.2 blueprint from src/mantleos/anchor_engine/profiles/hello_world_compact.anchor.',
    repoPath: 'src/mantleos/anchor_engine/profiles/hello_world_compact.anchor',
    content: HELLO_WORLD_ANCHOR,
  },
  {
    id: 'chase-stop',
    title: 'ChaseStop Gate (EMIT_TEXT/0.2)',
    filename: 'chase-stop.anchor',
    kind: 'EMIT_TEXT/0.2',
    category: 'Executable Blueprint',
    description:
      'Official MantleOS specimen packaging the scoped Chase latency and test gate Python program inside an EMIT_TEXT/0.2 Molecule.',
    repoPath: 'src/mantleos/kpp/resources/specimens/mantleos/chase-stop.anchor',
    content: CHASE_STOP_ANCHOR,
  },
  {
    id: 'intent-boundary',
    title: 'IntentBoundary (EMIT_TEXT/0.2)',
    filename: 'intent-boundary.anchor',
    kind: 'EMIT_TEXT/0.2',
    category: 'Executable Blueprint',
    description:
      'Body-side intent admission demonstration showing allowlisted operations (remember, recall, observe) packaged as an EMIT_TEXT/0.2 blueprint.',
    repoPath: 'src/mantleos/kpp/resources/specimens/mantleos/intent-boundary.anchor',
    content: INTENT_BOUNDARY_ANCHOR,
  },
  {
    id: 'memory-ledger',
    title: 'MemoryLedger (EMIT_TEXT/0.2)',
    filename: 'memory-ledger.anchor',
    kind: 'EMIT_TEXT/0.2',
    category: 'Executable Blueprint',
    description:
      'Append-only, hash-linked JSONL record verifier from the MantleOS specimens suite.',
    repoPath: 'src/mantleos/kpp/resources/specimens/mantleos/memory-ledger.anchor',
    content: MEMORY_LEDGER_ANCHOR,
  },
  {
    id: 'notepad-llm-v1',
    title: 'XPNotepad_LLM_v1 (NOTEPAD_LLM/1.3)',
    filename: 'XPNotepad_LLM_v1.anchor',
    kind: 'NOTEPAD_LLM/1.3',
    category: 'Agentic & Multi-Polarity',
    description:
      'Self-contained LLM-first state-transition blueprint with 7 Molecules (Boundary, Dispatch, Document, Editing, Searching, Files, Display) across BlackHole, WhiteHole, and Neutral polarities.',
    repoPath: 'src/mantleos/anchor_engine/tools/notepad_blueprint.py',
    content: nativeNotepad,
  },
  {
    id: 'agentic-v0-2',
    title: 'AgenticContinuityLoop (AGENTIC/0.2)',
    filename: 'agentic_continuity.anchor',
    kind: 'AGENTIC/0.2',
    category: 'Agentic & Multi-Polarity',
    description:
      'Bounded sequential Anchor agent loop blueprint using pinned AGENTIC/0.2 opcodes (-40 TASK_IN through -46 STOP) with explicit WhiteHole tool and budget guards.',
    repoPath: 'src/mantleos/agentic_profiles/primer_agentic_v0_2.txt',
    content: AGENTIC_CONTINUITY_ANCHOR,
  },
  {
    id: 'anchor-journal-design',
    title: 'Anchor-Journal (anchor.design/1 JSON)',
    filename: 'anchor-journal.design.json',
    kind: 'anchor.design/1',
    category: 'Responsibility Design',
    description:
      'Canonical 4-Anchor responsibility contract (BH-ENCOUNTER, WH-INTEGRITY, N-CONTINUITY, N-HOST) from src/mantleos/anchor_design.py.',
    repoPath: 'src/mantleos/anchor_design.py',
    content: JSON.stringify(ANCHOR_JOURNAL_DESIGN, null, 2) + '\n',
  },
  {
    id: 'notepad-fidelity9-txt',
    title: 'Notepad Fidelity 9 (.anchor.txt)',
    filename: 'Notepad.anchor.txt',
    kind: 'anchor.txt',
    category: 'Responsibility Design',
    description:
      'Human-readable 9-Anchor responsibility design contract introducing WH-BLUEPRINT-GATE alongside runtime BH->WH->Neutral routing.',
    repoPath: 'src/mantleos/kpp/resources/examples/notepad-fidelity9/Notepad.anchor.txt',
    content: NOTEPAD_FIDELITY9_DESIGN_TXT,
  },
];

export interface SampleSourceSnippet {
  id: string;
  name: string;
  language: string;
  description: string;
  code: string;
}

export const SAMPLE_SOURCE_SNIPPETS: SampleSourceSnippet[] = [
  {
    id: 'organ-save-service',
    name: 'Notepad Save Organ (Python)',
    language: 'python',
    description: 'Guarded UTF-8 file persistence module with conflict detection and clean-baseline tracking.',
    code: `"""Guarded file session manager with SHA-256 baseline conflict checks."""
import hashlib
from pathlib import Path

class FileSessionGuard:
    def __init__(self, allowed_root: Path):
        self.allowed_root = allowed_root.resolve()
        self.active_path: Path | None = None
        self.baseline_sha256: str | None = None
        self.document_buffer: str = ""

    def capture_save_request(self, raw_filename: str, raw_text: str) -> dict:
        """Untrusted input capture: normalize CRLF to LF without writing disk."""
        normalized_text = raw_text.replace("\\r\\n", "\\n")
        return {"filename": raw_filename.strip(), "text": normalized_text}

    def enforce_save_boundary(self, request: dict) -> Path:
        """Boundary guard: verify path stays inside allowed_root and check disk conflicts."""
        candidate = (self.allowed_root / request["filename"]).resolve()
        if not str(candidate).startswith(str(self.allowed_root)):
            raise PermissionError("Path traversal blocked by boundary guard")
        if candidate.exists() and self.baseline_sha256 is not None:
            current_disk = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if current_disk != self.baseline_sha256:
                raise RuntimeError("External file modification conflict detected")
        return candidate

    def commit_atomic_save(self, request: dict) -> dict:
        """Authoritative state update and guarded disk write."""
        target = self.enforce_save_boundary(request)
        encoded = request["text"].encode("utf-8")
        target.write_bytes(encoded)
        self.active_path = target
        self.document_buffer = request["text"]
        self.baseline_sha256 = hashlib.sha256(encoded).hexdigest()
        return {"path": str(target.name), "sha256": self.baseline_sha256, "bytes": len(encoded)}
`,
  },
  {
    id: 'kpp-chase-evaluator',
    name: 'Chase Obligation Runner (Python)',
    language: 'python',
    description: 'Selects unmet recipe obligations, validates test evidence, and holds Baker acceptance separate.',
    code: `"""KPP Chase loop obligation selector and evidence ledger."""
import hashlib
import json

class ChaseLedger:
    def __init__(self, recipe_id: string, obligations: list[dict]):
        self.recipe_id = recipe_id
        self.obligations = obligations
        self.observations: dict[str, dict] = {}
        self.baker_attestations: dict[str, dict] = {}

    def ingest_scan_observation(self, raw_payload: str) -> dict:
        """Receive bounded Scan observation without granting acceptance."""
        data = json.loads(raw_payload)
        return {"anchor_id": str(data["anchor_id"]), "passed": bool(data.get("passed")), "log": str(data.get("log", ""))}

    def verify_attestation_guard(self, anchor_id: str, baker: str, evidence: str) -> bool:
        """WhiteHole boundary: require non-empty evidence and existing obligation before recording acceptance."""
        known_ids = {item["id"] for item in self.obligations}
        if anchor_id not in known_ids:
            raise ValueError(f"Unknown recipe obligation: {anchor_id}")
        if not baker.strip() or not evidence.strip():
            raise PermissionError("Explicit Baker label and behavioral evidence required")
        return True

    def next_unmet_obligation(self) -> dict | None:
        """Pure selection of the next mandatory obligation lacking Baker attestation."""
        for item in self.obligations:
            if item.get("required", True) and item["id"] not in self.baker_attestations:
                return item
        return None
`,
  },
  {
    id: 'progressive-calculator',
    name: 'Progressive Calculator Engine (JavaScript)',
    language: 'javascript',
    description: 'Browser preview module for deterministic arithmetic expression evaluation and history tape.',
    code: `// Progressive Calculator KPP Browser Module
export class CalculatorOrgan {
  constructor() {
    this.displayValue = "0";
    this.memoryRegister = 0;
    this.historyTape = [];
  }

  captureKeyInput(rawKey) {
    const allowed = /^[0-9+\\-*/.=C]$/;
    if (!allowed.test(rawKey)) {
      return { valid: false, reason: "Unsupported key token" };
    }
    return { valid: true, token: rawKey };
  }

  guardDivisionAndBounds(left, operator, right) {
    if (operator === "/" && Number(right) === 0) {
      throw new Error("DIVIDE_BY_ZERO_GUARD");
    }
    const result = this.compute(left, operator, right);
    if (!Number.isFinite(result)) {
      throw new Error("NONFINITE_RESULT_GUARD");
    }
    return result;
  }

  compute(left, operator, right) {
    const a = Number(left);
    const b = Number(right);
    switch (operator) {
      case "+": return a + b;
      case "-": return a - b;
      case "*": return a * b;
      case "/": return a / b;
      default: return b;
    }
  }

  commitCalculation(left, operator, right) {
    const value = this.guardDivisionAndBounds(left, operator, right);
    const entry = { expr: \`\${left} \${operator} \${right}\`, result: String(value) };
    this.displayValue = String(value);
    this.historyTape.push(entry);
    return entry;
  }
}
`,
  },
];
