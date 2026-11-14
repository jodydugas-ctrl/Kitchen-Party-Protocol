import { NativeRecipeProposal } from './NativeRecipeProposal';
import React, { useState } from 'react';
import {
  AnchorDesignContract,
  BLUEPRINT_NAME_REGEX,
  buildAnchorDesignFromSpec,
  qualifyEmitTextProgram,
  renderEmitTextBlueprint,
  sha256Hex,
  validateAnchorDesign,
} from '../lib/kppEngine';
import { SAMPLE_SOURCE_SNIPPETS } from '../lib/kppSpecimens';
import {
  ArrowRight,
  CheckCircle2,
  Code2,
  Cpu,
  Download,
  FileCode,
  FolderOpen,
  Layers,
  Loader2,
  Sparkles,
} from 'lucide-react';

interface CodeToAnchorConverterProps {
  onOpenInWorkbench: (content: string, filename: string) => void;
  onSendDesignToTopology: (design: AnchorDesignContract) => void;
}

interface AiAssistProposal {
  id: string;
  purpose: string;
  applications: { id: string; definition: string; responsibility: string }[];
  flows: { from: string; to: string; relationship: string }[];
  state: { id: string; owner: string }[];
  effects: { id: string; requester: string; guard: string; confirmation: string }[];
  candidateMolecules: {
    moleculeName: string;
    id: string;
    type: string;
    opcode: string;
    mass: string;
    variableKey: string;
    variableValue: string;
  }[];
  obligations: {
    id: string;
    required: boolean;
    statement: string;
    test: string;
    design_anchors: string[];
  }[];
  architectNotes: string;
}

export const CodeToAnchorConverter: React.FC<CodeToAnchorConverterProps> = ({
  onOpenInWorkbench,
  onSendDesignToTopology,
}) => {
  const [sourceCode, setSourceCode] = useState(SAMPLE_SOURCE_SNIPPETS[0].code);
  const [language, setLanguage] = useState(SAMPLE_SOURCE_SNIPPETS[0].language);
  const [blueprintName, setBlueprintName] = useState('FileSessionOrgan');
  const [chunkMode, setChunkMode] = useState<'single' | 'logical_blocks'>('single');
  const [bakerGoal, setBakerGoal] = useState(
    'Decompose into BlackHole input capture, WhiteHole guard boundaries, and Neutral state owners following N-RULE-ECONOMY.'
  );

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [draft, setAiProposal] = useState<{ input: string; proposal: AiAssistProposal }>();
  const draftInput = JSON.stringify([sourceCode, language, blueprintName, bakerGoal]);
  const aiProposal = draft?.input === draftInput ? draft.proposal : null;

  const safeBlueprintName = blueprintName.trim().length <= 64 && BLUEPRINT_NAME_REGEX.test(blueprintName.trim())
    ? blueprintName.trim()
    : 'ConvertedModule';

  // Track 1: Deterministic EMIT_TEXT/0.2 generation & round-trip check
  const normalizedInput = sourceCode.replace(/\r\n/g, '\n');
  const deterministicUnits =
    chunkMode === 'single'
      ? [{ id: 'Body', text: normalizedInput }]
      : normalizedInput
          .split(/(?<=\n)(?=(?:def |class |export |function ))/)
          .reduce<string[]>((chunks, chunk, i) => {
            if (i < 128) chunks.push(chunk);
            else chunks[127] += chunk;
            return chunks;
          }, [])
          .map((chunk, i) => ({ id: `Unit_${i + 1}`, text: chunk }));

  const deterministicAnchorBlueprint = renderEmitTextBlueprint(
    safeBlueprintName,
    deterministicUnits.length ? deterministicUnits : [{ id: 'Body', text: normalizedInput }]
  );

  let deterministicQualification: ReturnType<typeof qualifyEmitTextProgram> | null = null;
  let deterministicError: string | null = null;
  try {
    deterministicQualification = qualifyEmitTextProgram(deterministicAnchorBlueprint);
  } catch (e: unknown) {
    deterministicError = e instanceof Error ? e.message : String(e);
  }

  const inputSha256 = sha256Hex(normalizedInput);
  const roundTripVerified =
    deterministicQualification !== null &&
    deterministicQualification.receipt.stdout_sha256 === inputSha256;

  // Deterministic heuristic extractor (instant offline fallback / companion)
  const runDeterministicExtraction = () => {
    setAiError(null);
    const lines = normalizedInput.split('\n');
    const functions: string[] = [];
    const classes: string[] = [];
    for (const line of lines) {
      const fnMatch = /(?:def|function)\s+([A-Za-z_][A-Za-z0-9_]*)/.exec(line);
      if (fnMatch) functions.push(fnMatch[1]);
      const clsMatch = /class\s+([A-Za-z_][A-Za-z0-9_]*)/.exec(line);
      if (clsMatch) classes.push(clsMatch[1]);
    }

    const bhName = `BH-${safeBlueprintName.toUpperCase()}-INPUT`;
    const whName = `WH-${safeBlueprintName.toUpperCase()}-GUARD`;
    const nStateName = `N-${safeBlueprintName.toUpperCase()}-STATE`;
    const nComputeName = `N-${safeBlueprintName.toUpperCase()}-LOGIC`;

    const proposal: AiAssistProposal = {
      id: `${safeBlueprintName}-Design`,
      purpose: `Responsibility decomposition of ${safeBlueprintName} (${classes.join(', ') || 'module'}) with explicit input capture, boundary guard, and Neutral state ownership.`,
      applications: [
        {
          id: bhName,
          definition: 'BlackHole',
          responsibility: `Capture and normalize untrusted caller input for ${functions[0] || 'entry functions'} without mutating state.`,
        },
        {
          id: whName,
          definition: 'WhiteHole',
          responsibility: `Enforce precondition, path/type boundary, and capability checks before dispatching to Neutral owners.`,
        },
        {
          id: nStateName,
          definition: 'Neutral',
          responsibility: `Sole authoritative owner of in-memory state and baseline revisions across ${classes[0] || safeBlueprintName}.`,
        },
        {
          id: nComputeName,
          definition: 'Neutral',
          responsibility: `Execute pure relationship calculations (${functions.slice(0, 4).join(', ') || 'module logic'}) on validated inputs.`,
        },
      ],
      flows: [
        { from: bhName, to: whName, relationship: 'Pass normalized untrusted request for boundary check' },
        { from: whName, to: nComputeName, relationship: 'Invoke pure logic after guard validation' },
        { from: whName, to: nStateName, relationship: 'Commit validated state transition atomically' },
      ],
      state: [
        { id: `${safeBlueprintName.toLowerCase()}-buffer`, owner: nStateName },
        { id: `${safeBlueprintName.toLowerCase()}-baseline-digest`, owner: nStateName },
      ],
      effects: [
        {
          id: `${safeBlueprintName.toLowerCase()}-host-effect`,
          requester: nStateName,
          guard: whName,
          confirmation: 'Boundary guard validates invariants and host receipt before state commit.',
        },
      ],
      candidateMolecules: [
        {
          moleculeName: 'Ingress',
          id: 'CaptureInput',
          type: 'BlackHole',
          opcode: '20',
          mass: '00',
          variableKey: 'input',
          variableValue: functions[0] || 'raw_request',
        },
        {
          moleculeName: 'Boundary',
          id: 'EnforceGuard',
          type: 'WhiteHole',
          opcode: '10',
          mass: '00',
          variableKey: 'policy',
          variableValue: 'fail_closed_validation',
        },
        {
          moleculeName: 'Execution',
          id: 'ApplyRelationship',
          type: 'Neutral',
          opcode: '30',
          mass: '00',
          variableKey: 'function',
          variableValue: functions.slice(0, 3).join('_') || 'commit_state',
        },
      ],
      obligations: [
        {
          id: 'OBL-INPUT-CAPTURE',
          required: true,
          statement: 'Untrusted inputs are normalized without side effects or state mutation.',
          test: 'Verify malformed or oversized inputs fail closed before state mutation.',
          design_anchors: [bhName, whName],
        },
        {
          id: 'OBL-ATOMIC-COMMIT',
          required: true,
          statement: 'Validated operations update Neutral state atomically and preserve baseline digests.',
          test: 'Verify state revision and SHA-256 digest match after valid execution.',
          design_anchors: [whName, nStateName, nComputeName],
        },
      ],
      architectNotes: `Deterministically mapped ${functions.length} function(s) and ${classes.length} class(es) into canonical BlackHole -> WhiteHole -> Neutral topology.`,
    };
    setAiProposal({ input: draftInput, proposal });
  };

  const handleRunAiArchitect = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const response = await fetch('/api/anchor/assist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sourceCode: normalizedInput,
          language,
          blueprintName: safeBlueprintName,
          goal: bakerGoal,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        throw new Error(data.error || `Server returned ${response.status}`);
      }
      setAiProposal({ input: draftInput, proposal: data.proposal as AiAssistProposal });
    } catch (err: unknown) {
      setAiError(err instanceof Error ? err.message : String(err));
    } finally {
      setAiLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === 'string' ? reader.result : '';
      setSourceCode(text.replace(/\r\n/g, '\n'));
      const stem = file.name.replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9_]/g, '');
      if (stem && /^[A-Za-z]/.test(stem)) {
        setBlueprintName(stem);
      }
    };
    reader.readAsText(file);
  };

  const downloadFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Validate AI proposal if present
  const builtContract = aiProposal ? buildAnchorDesignFromSpec(aiProposal) : null;
  const contractValidation = builtContract ? validateAnchorDesign(builtContract) : null;
  const organSpec = aiProposal && JSON.stringify({
    schema: 'anchorforge.organ-spec/1',
    id: aiProposal.id.toLowerCase().replace(/[^a-z0-9_-]/g, '-').slice(0, 64),
    goal: bakerGoal.trim() || aiProposal.purpose,
    target: aiProposal.purpose,
    tissue: language === 'python' ? 'python' : 'javascript',
    product_kind: 'conventional',
    fidelity: 1,
    capabilities: { agent: false, mind: false, mantleos_splice: false },
    responsibilities: aiProposal.applications.map(({ id, definition, responsibility }) => ({
      id, definition, responsibility,
    })),
    flows: aiProposal.flows,
    state: aiProposal.state,
    effects: aiProposal.effects,
    obligations: aiProposal.obligations.map(({ id, ...obligation }) => ({
      ...obligation, id: id.toLowerCase(), depth: 1, depends: [],
    })),
  }, null, 2);

  return (
    <div className="space-y-6">
      {/* Top Bar of Converter */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>PIPELINE: CODE-TO-ANCHOR CONVERSION</span>
            <span aria-hidden="true">·</span>
            <span>TRACK A: EMIT_TEXT/0.2 PACKAGING</span>
            <span aria-hidden="true">·</span>
            <span>TRACK B: ANCHOR.DESIGN/1 EXTRACTION</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">
            Source Code to Kitchen Party Protocol Anchor Translator
          </h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Package existing code into deterministic `EMIT_TEXT/0.2` Molecules or extract `BlackHole`,
            `WhiteHole`, and `Neutral` responsibility contracts (`anchor.design/1`).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <label className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg cursor-pointer transition-colors whitespace-nowrap shrink-0">
            <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
            Load Source File
            <input type="file" onChange={handleFileUpload} className="hidden" />
          </label>
          {SAMPLE_SOURCE_SNIPPETS.map((snip) => (
            <button
              key={snip.id}
              onClick={() => {
                setSourceCode(snip.code);
                setLanguage(snip.language);
                setBlueprintName(snip.id.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase()));
              }}
              className="px-3 py-2 text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg transition-colors whitespace-nowrap shrink-0"
            >
              {snip.name}
            </button>
          ))}
        </div>
      </div>

      {/* Main Split Grid: Source Input on Left, Conversion Tracks on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 5 Cols: Source Code Input & Settings */}
        <div className="lg:col-span-5 bg-slate-900/80 border border-slate-800 rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-semibold text-slate-200">
              SOURCE CODE INPUT ({language.toUpperCase()})
            </span>
            <span className="text-xs font-mono text-slate-400 tabular-nums">
              {normalizedInput.length} chars · SHA256: {inputSha256.slice(0, 10)}…
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                BLUEPRINT / DESIGN ID
              </label>
              <input
                type="text"
                value={blueprintName}
                onChange={(e) => setBlueprintName(e.target.value)}
                placeholder="e.g. FileSessionOrgan"
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
              />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                EMIT_TEXT MOLECULE CHUNKING
              </label>
              <select
                value={chunkMode}
                onChange={(e) => setChunkMode(e.target.value as 'single' | 'logical_blocks')}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
              >
                <option value="single">Single Anchor Literal (Body: Neutral -01 -00)</option>
                <option value="logical_blocks">Multi-Anchor by Function/Class (Unit_1..N)</option>
              </select>
            </div>
          </div>

          <textarea
            value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)}
            rows={18}
            spellCheck={false}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 leading-relaxed focus:outline-none focus:border-amber-400"
            placeholder="Paste Python, JavaScript, TypeScript, or system specification here…"
          />

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">
              ARCHITECT DECOMPOSITION GOAL (FOR TRACK B)
            </label>
            <input
              type="text"
              value={bakerGoal}
              onChange={(e) => setBakerGoal(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
            <button
              onClick={handleRunAiArchitect}
              disabled={aiLoading}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-400 hover:bg-amber-300 disabled:opacity-50 text-slate-950 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap"
            >
              {aiLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Decomposing via Gemini…
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  AI Extract Responsibility Contract
                </>
              )}
            </button>
            <button
              onClick={runDeterministicExtraction}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium rounded-lg transition-colors whitespace-nowrap"
            >
              <Cpu className="w-4 h-4 text-sky-400" />
              Instant Heuristic Decomposition
            </button>
          </div>
        </div>

        {/* Right 7 Cols: Track A (EMIT_TEXT/0.2) & Track B (anchor.design/1 Proposal) */}
        <div className="lg:col-span-7 space-y-6">
          {/* TRACK A: Deterministic EMIT_TEXT/0.2 Blueprint Wrapper */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-emerald-400 font-semibold">
                    TRACK A · DETERMINISTIC EMIT_TEXT/0.2 PACKAGING
                  </span>
                  <span aria-hidden="true">·</span>
                  <span className="text-slate-400 tabular-nums">
                    {deterministicUnits.length} Anchor Unit(s)
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Packages LF-normalized source as an EMIT_TEXT/0.2 literal. Open it in the workbench for native inspection and the Python bridge.
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() =>
                    downloadFile(deterministicAnchorBlueprint, `${safeBlueprintName}.anchor`)
                  }
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors whitespace-nowrap"
                >
                  <Download className="w-3.5 h-3.5" />
                  Save .anchor
                </button>
                <button
                  onClick={() =>
                    onOpenInWorkbench(deterministicAnchorBlueprint, `${safeBlueprintName}.anchor`)
                  }
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-950 bg-emerald-400 hover:bg-emerald-300 rounded transition-colors whitespace-nowrap"
                >
                  <Code2 className="w-3.5 h-3.5" />
                  Load in Workbench
                </button>
              </div>
            </div>

            {deterministicError ? (
              <div className="p-3 bg-red-950/40 border border-red-800/60 rounded text-xs text-red-300 font-mono">
                {deterministicError}
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-400 bg-slate-950 px-3 py-2 rounded border border-slate-800">
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {roundTripVerified ? 'LOCAL LITERAL ROUND-TRIP EXACT' : 'LOCAL OUTPUT DIFFERS'}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span>
                    BLUEPRINT SHA256:{' '}
                    {deterministicQualification?.receipt.source_sha256.slice(0, 12)}…
                  </span>
                  <span aria-hidden="true">·</span>
                  <span className="tabular-nums">
                    STDOUT BYTES: {deterministicQualification?.receipt.stdout_bytes}
                  </span>
                </div>

                <pre className="max-h-56 overflow-y-auto bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 leading-relaxed">
                  {deterministicAnchorBlueprint}
                </pre>
              </>
            )}
          </div>

          {/* TRACK B: AI / Heuristic Responsibility Contract Extraction */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-amber-400 font-semibold">
                    TRACK B · KPP RESPONSIBILITY CONTRACT (`anchor.design/1`)
                  </span>
                  <span aria-hidden="true">·</span>
                  <span className="text-slate-400">AUTHORITY: DESIGN_ONLY (NONE)</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Decomposes code into `BlackHole`, `WhiteHole`, and `Neutral` applications, state
                  ownership, and guarded effects.
                </p>
              </div>

              {builtContract && contractValidation && (
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <button
                    onClick={() => onSendDesignToTopology(builtContract)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors whitespace-nowrap"
                  >
                    <Layers className="w-3.5 h-3.5 text-sky-400" />
                    Inspect in Topology Graph
                  </button>
                  <button
                    onClick={() =>
                      onOpenInWorkbench(
                        contractValidation.renderedText,
                        `${builtContract.id}.anchor.txt`
                      )
                    }
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-950 bg-amber-400 hover:bg-amber-300 rounded transition-colors whitespace-nowrap"
                  >
                    <FileCode className="w-3.5 h-3.5" />
                    Open .anchor.txt in Workbench
                  </button>
                </div>
              )}
            </div>

            {aiError && (
              <div className="p-3 bg-red-950/40 border border-red-800/60 rounded text-xs text-red-300">
                {aiError}
              </div>
            )}

            {!aiProposal ? (
              <div className="p-6 text-center border border-dashed border-slate-800 rounded-lg space-y-2">
                <p className="text-xs text-slate-400">
                  Click <strong className="text-slate-200">AI Extract Responsibility Contract</strong>{' '}
                  or <strong className="text-slate-200">Instant Heuristic Decomposition</strong> to
                  map this source code into KPP `BlackHole`, `WhiteHole`, and `Neutral` Anchor
                  applications.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {organSpec && <NativeRecipeProposal key={organSpec} spec={organSpec} editable />}
                {aiProposal.architectNotes && (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs text-slate-300">
                    <span className="font-mono text-amber-400 font-semibold">ARCHITECT NOTES: </span>
                    {aiProposal.architectNotes}
                  </div>
                )}

                {/* Extracted Applications */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {builtContract?.applications.map((app) => (
                    <div
                      key={app.id}
                      className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1"
                    >
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="font-semibold text-slate-100">{app.id}</span>
                        <span
                          className={
                            app.type === 'BlackHole'
                              ? 'text-indigo-400'
                              : app.type === 'WhiteHole'
                              ? 'text-sky-400'
                              : 'text-emerald-400'
                          }
                        >
                          {app.type}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {app.attributes.responsibility}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Candidate Molecules Preview */}
                {aiProposal.candidateMolecules?.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono text-slate-400">
                        CANDIDATE UNIVERSAL ANCHOR MOLECULES
                      </span>
                      <button
                        onClick={() => {
                          const grouped = new Map<string, string[]>();
                          for (const m of aiProposal.candidateMolecules) {
                            const list = grouped.get(m.moleculeName) || [];
                            list.push(
                              `${m.id}: ${m.type} -${m.opcode} -${m.mass} -${m.variableKey}=${JSON.stringify(
                                m.variableValue
                              )}`
                            );
                            grouped.set(m.moleculeName, list);
                          }
                          const blocks = Array.from(grouped.entries())
                            .map(
                              ([molName, lines]) =>
                                `BEGIN MOLECULE ${molName.replace(/[^A-Za-z0-9_]/g, '') || 'Module'}\n${lines.join(
                                  '\n'
                                )}\nEND MOLECULE`
                            )
                            .join('\n\n');
                          onOpenInWorkbench(blocks + '\n', `${safeBlueprintName}_molecules.anchor`);
                        }}
                        className="text-xs font-mono text-amber-400 hover:underline flex items-center gap-1"
                      >
                        Load Molecules in Workbench <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                    <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
                      {aiProposal.candidateMolecules
                        .map(
                          (m) =>
                            `${m.id}: ${m.type} -${m.opcode} -${m.mass} -${m.variableKey}=${JSON.stringify(
                              m.variableValue
                            )}`
                        )
                        .join('\n')}
                    </pre>
                  </div>
                )}

                {/* Rendered .anchor.txt Preview */}
                {contractValidation && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono text-slate-400">
                        GENERATED .ANCHOR.TXT DESIGN CONTRACT
                      </span>
                      <button
                        onClick={() =>
                          downloadFile(
                            contractValidation.renderedText,
                            `${builtContract?.id || 'Design'}.anchor.txt`
                          )
                        }
                        className="text-xs font-mono text-slate-300 hover:text-white flex items-center gap-1"
                      >
                        <Download className="w-3 h-3" /> Download .anchor.txt
                      </button>
                    </div>
                    <pre className="max-h-52 overflow-y-auto bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 leading-relaxed">
                      {contractValidation.renderedText}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
