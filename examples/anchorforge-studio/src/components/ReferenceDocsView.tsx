import React, { useState } from 'react';
import {
  DEFINITIONS,
  PRIMER_EMIT_TEXT_V0_2,
  PRIMER_NOTEPAD_LLM_V1,
  PRIMER_AGENTIC_V0_2,
  RULE_ECONOMY,
  sha256Hex,
} from '../lib/kppEngine';
import { Copy, Check, Terminal, BookOpen, ShieldCheck, Layers } from 'lucide-react';

export const ReferenceDocsView: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const primers = [
    {
      id: 'emit-text',
      name: 'EMIT_TEXT/0.2 Execution Primer',
      status: 'STATUS: EXPERIMENTAL EMIT_TEXT/0.2',
      sha256: sha256Hex(PRIMER_EMIT_TEXT_V0_2 + '\n'),
      scope:
        'Deterministic non-effectful literal text emission. 1 to 128 unique Neutral anchors (`ID: Neutral -01 -00 -text="<JSON_STRING>"`). Concatenates decoded strings in order with zero side effects.',
      content: PRIMER_EMIT_TEXT_V0_2,
    },
    {
      id: 'notepad-llm',
      name: 'NOTEPAD_LLM/1.3 Execution Primer',
      status: 'STATUS: RELEASE CANDIDATE NOTEPAD_LLM/1.3',
      sha256: sha256Hex(PRIMER_NOTEPAD_LLM_V1 + '\n'),
      scope:
        'Self-contained LLM-first state-transition language for one plain-text editor. OP 10 checks external authority (WhiteHole), OP 20 admits document input (BlackHole), OP 30 applies the declared function (Neutral).',
      content: PRIMER_NOTEPAD_LLM_V1,
    },
    {
      id: 'agentic-v0-2',
      name: 'AGENTIC/0.2 Execution Primer',
      status: 'STATUS: EXPERIMENTAL AGENTIC/0.2',
      sha256: sha256Hex(PRIMER_AGENTIC_V0_2 + '\n'),
      scope:
        'Bounded sequential Anchor agent loop with explicit pause, resume, read-only tool guards (-42 TOOL_GUARD), and portable chat/PNG handoff (-4E PORTABLE_HANDOFF).',
      content: PRIMER_AGENTIC_V0_2,
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span>SPECIFICATION: KITCHEN PARTY PROTOCOL (KPP 1.1.0a5)</span>
          <span aria-hidden="true">·</span>
          <span>SHARED RUNTIME: MANTLEOS & KPP</span>
          <span aria-hidden="true">·</span>
          <span>AUTHORITY: NONE</span>
        </div>
        <h2 className="text-xl font-bold text-slate-100 mt-1">
          Anchor Code Language Reference & Protocol Contracts
        </h2>
        <p className="text-sm text-slate-400 mt-0.5 max-w-3xl">
          Reference documentation for immutable Anchor singularities, universal Anchor entry shapes,
          pinned execution primers, and KPP CLI commands from{' '}
          <span className="font-mono text-slate-300">jodydugas-ctrl/Kitchen-Party-Protocol</span>.
        </p>
      </div>

      {/* Section 1: Immutable Singularities */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-amber-400" />
          <h3 className="text-base font-semibold text-slate-100">
            01. Immutable Anchor Definitions (`src/mantleos/anchors.py`)
          </h3>
        </div>
        <p className="text-xs text-slate-400 max-w-3xl">
          Definitions are trusted source constants. A model or Baker may propose contextual
          applications (`anchor.application/1`) with custom attributes, but can never redefine or
          override the canonical `type` or `singularity`.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.values(DEFINITIONS).map((def) => (
            <div
              key={def.id}
              className="p-4 bg-slate-900/80 border border-slate-800 rounded-lg space-y-2"
            >
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="font-bold text-slate-100">{def.id}</span>
                <span
                  className={
                    def.type === 'BlackHole'
                      ? 'text-indigo-400'
                      : def.type === 'WhiteHole'
                      ? 'text-sky-400'
                      : 'text-emerald-400'
                  }
                >
                  {def.type}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-medium">
                “{def.singularity}”
              </p>
              <div className="pt-2 border-t border-slate-800/80 text-[11px] font-mono text-slate-500">
                Stages: REACH · QUALIFY · ROUTE
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section 2: Universal Anchor Entry Grammar */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-sky-400" />
          <h3 className="text-base font-semibold text-slate-100">
            02. Universal Serialized Anchor Entry Shape (`anchor_structure.py`)
          </h3>
        </div>

        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-lg space-y-3">
          <div className="font-mono text-xs text-amber-300 bg-slate-950 p-3 rounded border border-slate-800">
            &lt;ID&gt;: (BlackHole|WhiteHole|Neutral) -&lt;OPCODE&gt; -&lt;MASS&gt; -&lt;KEY&gt;=&lt;JSON_VALUE&gt;
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div>
              <div className="font-mono font-semibold text-slate-200">ID</div>
              <p className="text-slate-400 mt-0.5">
                Starts with an ASCII letter, followed by up to 63 letters, digits, underscores, or
                hyphens (`[A-Za-z][A-Za-z0-9_-]{'{0,63}'}`). Unique per blueprint.
              </p>
            </div>
            <div>
              <div className="font-mono font-semibold text-slate-200">TYPE (Polarity)</div>
              <p className="text-slate-400 mt-0.5">
                Must be `BlackHole` (input capture), `WhiteHole` (boundary guard), or `Neutral`
                (state/relationship). All three share the exact same 5-slot record shape.
              </p>
            </div>
            <div>
              <div className="font-mono font-semibold text-slate-200">-OPCODE &amp; -MASS</div>
              <p className="text-slate-400 mt-0.5">
                Two uppercase hex digits (`[0-9A-F]{'{2}'}`). `-01` emits literal text; `-10` guards
                external boundaries; `-20` admits input; `-30` applies functions. `-00` is session-local
                mass.
              </p>
            </div>
            <div>
              <div className="font-mono font-semibold text-slate-200">-VARIABLE</div>
              <p className="text-slate-400 mt-0.5">
                Lowercase key (`[a-z][a-z0-9_]*`) followed by `=` and a valid JSON value (e.g.,
                `-text="Hello, World!"` or `-policy="deny_unverified_external_effects"`).
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Pinned Execution Primers */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-emerald-400" />
          <h3 className="text-base font-semibold text-slate-100">
            03. Pinned Execution Primers
          </h3>
        </div>
        <div className="space-y-4">
          {primers.map((p) => (
            <div
              key={p.id}
              className="p-4 bg-slate-900/80 border border-slate-800 rounded-lg space-y-2.5"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="text-sm font-semibold text-slate-100">{p.name}</span>
                  <div className="text-xs font-mono text-slate-400 mt-0.5">
                    {p.status} · SHA256: {p.sha256.slice(0, 20)}…
                  </div>
                </div>
                <button
                  onClick={() => copyText(p.id, p.content)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors self-start"
                >
                  {copiedId === p.id ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied Primer
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy Exact Primer
                    </>
                  )}
                </button>
              </div>
              <p className="text-xs text-slate-400">{p.scope}</p>
              <pre className="p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                {p.content}
              </pre>
            </div>
          ))}
        </div>
      </section>

      {/* Section 4: KPP CLI Command Equivalence */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-amber-400" />
          <h3 className="text-base font-semibold text-slate-100">
            04. Kitchen Party Protocol CLI Equivalence
          </h3>
        </div>
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-lg space-y-3">
          <p className="text-xs text-slate-400">
            Studio projections are local previews. The native check uses the configured KPP runtime to validate the current document.
          </p>
          <pre className="p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`# 1. Inspect and execute a native .anchor blueprint
python -m kpp anchor inspect YOUR_PROGRAM.anchor
python -m kpp anchor run YOUR_PROGRAM.anchor

# 2. Materialize EMIT_TEXT/0.2 to Python without executing it
python -m kpp anchor bridge-python YOUR_PROGRAM.anchor --out output.py

# 3. Run NOTEPAD_LLM/1.3 with an explicit JSON command
python -m kpp anchor run XPNotepad_LLM_v1.anchor --input COMMAND.json

# 4. Validate universal Anchor structure and anchor.design/1 contracts
python -m mantleos.anchor_engine.tools.anchor_structure YOUR_PROGRAM.anchor
python -m mantleos kpp design-check --recipe recipes/journal-engram-design.json
python -m mantleos kpp design-view --recipe recipes/journal-engram-design.json`}
          </pre>
          <div className="text-xs font-mono text-slate-400">
            N-RULE-ECONOMY: {RULE_ECONOMY}
          </div>
        </div>
      </section>
    </div>
  );
};
