import React, { useState } from 'react';
import { requestKpp, saveText } from '../lib/nativeKppClient';

const EXAMPLE = {
  schema: 'anchor.transition-trace/1',
  authority: 'NONE',
  baker_acceptance: 'NOT_GRANTED',
  contract_ref: 'Notepad Fidelity 9 logical contract (illustrative, not executed)',
  initial_state: { text: '', revision: 0, dirty: false },
  steps: [{
    id: 'S1',
    stimulus: { action: 'insert', payload: { text: 'Hello' } },
    before: { text: '', revision: 0, dirty: false },
    gate: { family: 'G-COMMIT', decision: 'admit', clauses: ['G-CMD-02'] },
    transition: 'changed',
    after: { text: 'Hello', revision: 1, dirty: true },
    effects: [],
    output: { kind: 'snapshot' },
    evidence: { kind: 'none', ref: null },
  }],
  final_state: { text: 'Hello', revision: 1, dirty: true },
};

export const TransitionLab: React.FC = () => {
  const [source, setSource] = useState(() => JSON.stringify(EXAMPLE, null, 2));
  const [report, setReport] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const validate = async () => {
    setPending(true);
    setReport(null);
    try {
      const result = await requestKpp('transition', source);
      setReport(result);
    } catch (error) {
      setReport({ status: 'unavailable', message: error instanceof Error ? error.message : 'Native KPP request failed.' });
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1440px] px-6 py-8 space-y-5">
      <div>
        <p className="text-xs tracking-[0.2em] text-amber-400 uppercase">Proposed standard · data-only</p>
        <h1 className="text-2xl font-semibold text-slate-100 mt-2">Anchor Transition Lab</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-4xl">
          Inspect a portable trace of actions, Gate decisions, before/after state,
          effects and declared evidence. Validation checks structure and continuity only:
          no command runs, no effect is authenticated and no Baker acceptance is granted.
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="rounded-xl border border-slate-700 bg-[#0E1420] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-slate-200">Trace JSON</h2>
            <div className="flex gap-2 text-xs">
              <button type="button" onClick={() => { setSource(JSON.stringify(EXAMPLE, null, 2)); setReport(null); }} className="rounded-md border border-slate-600 px-3 py-2 hover:bg-slate-700">Example</button>
              <button type="button" onClick={() => saveText(source, 'anchor-transition-trace.json')} className="rounded-md border border-slate-600 px-3 py-2 hover:bg-slate-700">Export</button>
            </div>
          </div>
          <textarea aria-label="Logical transition trace JSON" spellCheck={false}
            value={source} onChange={event => { setSource(event.target.value); setReport(null); }}
            className="w-full min-h-[510px] rounded-lg border border-slate-700 bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500" />
          <button type="button" onClick={validate} disabled={pending}
            className="rounded-lg bg-amber-400 px-4 py-2 font-semibold text-sm text-slate-950 hover:bg-amber-300 disabled:opacity-60">
            {pending ? 'Checking…' : 'Validate with native KPP'}
          </button>
        </div>
        <div className="rounded-xl border border-slate-700 bg-[#0E1420] p-4 space-y-3">
          <h2 className="font-semibold text-slate-200">Validation receipt</h2>
          <p className="text-xs text-slate-400">
            A passed receipt is not evidence of semantic execution, model accuracy,
            real host effects, or official KPP admission.
          </p>
          <pre aria-live="polite" className="min-h-[510px] max-h-[70vh] overflow-auto whitespace-pre-wrap break-all rounded-lg border border-slate-700 bg-slate-950 p-4 text-xs text-emerald-200">
            {report === null ? 'Run validation to inspect the proposed trace.' : JSON.stringify(report, null, 2)}
          </pre>
          <p className="text-xs text-slate-500">Format: anchor.transition-trace/1 · Authority: NONE · Baker acceptance: NOT_GRANTED</p>
        </div>
      </div>
    </div>
  );
};
