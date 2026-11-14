import React, { useState } from 'react';
import {
  AnchorDesignContract,
  AnchorPolarity,
  DEFINITIONS,
  RULE_ECONOMY,
  createAnchorApplication,
  validateAnchorDesign,
  canonicalJson,
} from '../lib/kppEngine';
import { Plus, Trash2, ArrowRight, FileCode, FileText, CheckCircle2, AlertTriangle } from 'lucide-react';

interface TopologyVisualizerProps {
  design: AnchorDesignContract;
  onUpdateDesign: (updated: AnchorDesignContract) => void;
  onLoadIntoEditor: (content: string, filename: string) => void;
}

export const TopologyVisualizer: React.FC<TopologyVisualizerProps> = ({
  design,
  onUpdateDesign,
  onLoadIntoEditor,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(
    design.applications[0]?.id ?? null
  );
  const [newAppId, setNewAppId] = useState('');
  const [newAppPolarity, setNewAppPolarity] = useState<AnchorPolarity>('Neutral');
  const [newAppResp, setNewAppResp] = useState('');

  const [newFlowFrom, setNewFlowFrom] = useState(design.applications[0]?.id ?? '');
  const [newFlowTo, setNewFlowTo] = useState(design.applications[1]?.id ?? design.applications[0]?.id ?? '');
  const [newFlowRel, setNewFlowRel] = useState('');

  const [newStateId, setNewStateId] = useState('');
  const [newStateOwner, setNewStateOwner] = useState(
    design.applications.find((a) => a.type === 'Neutral')?.id ?? ''
  );

  const [newEffectId, setNewEffectId] = useState('');
  const [newEffectReq, setNewEffectReq] = useState(design.applications[0]?.id ?? '');
  const [newEffectGuard, setNewEffectGuard] = useState(
    design.applications.find((a) => a.type === 'WhiteHole')?.id ?? ''
  );
  const [newEffectConf, setNewEffectConf] = useState('');

  const [formError, setFormError] = useState<string | null>(null);

  const validation = validateAnchorDesign(design);

  const blackHoles = design.applications.filter((a) => a.type === 'BlackHole');
  const whiteHoles = design.applications.filter((a) => a.type === 'WhiteHole');
  const neutrals = design.applications.filter((a) => a.type === 'Neutral');

  const selectedNode = design.applications.find((a) => a.id === selectedNodeId) ?? null;

  const handleAddApplication = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      const app = createAnchorApplication(newAppId.trim(), newAppPolarity, newAppResp.trim());
      if (design.applications.some((a) => a.id === app.id)) {
        setFormError(`Anchor ID "${app.id}" already exists in this design.`);
        return;
      }
      const next: AnchorDesignContract = {
        ...design,
        applications: [...design.applications, app],
      };
      onUpdateDesign(next);
      setNewAppId('');
      setNewAppResp('');
      setSelectedNodeId(app.id);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleRemoveApplication = (id: string) => {
    const next: AnchorDesignContract = {
      ...design,
      applications: design.applications.filter((a) => a.id !== id),
      flows: design.flows.filter((f) => f.from !== id && f.to !== id),
      state: design.state.filter((s) => s.owner !== id),
      effects: design.effects.filter((ef) => ef.requester !== id && ef.guard !== id),
    };
    onUpdateDesign(next);
    if (selectedNodeId === id) {
      setSelectedNodeId(next.applications[0]?.id ?? null);
    }
  };

  const handleAddFlow = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!newFlowFrom || !newFlowTo || !newFlowRel.trim()) {
      setFormError('Select source, destination, and enter a flow relationship description.');
      return;
    }
    const next: AnchorDesignContract = {
      ...design,
      flows: [
        ...design.flows,
        { from: newFlowFrom, to: newFlowTo, relationship: newFlowRel.trim() },
      ],
    };
    onUpdateDesign(next);
    setNewFlowRel('');
  };

  const handleAddState = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!newStateId.trim() || !newStateOwner) {
      setFormError('State ID and a Neutral owner are required.');
      return;
    }
    const next: AnchorDesignContract = {
      ...design,
      state: [...design.state, { id: newStateId.trim(), owner: newStateOwner }],
    };
    onUpdateDesign(next);
    setNewStateId('');
  };

  const handleAddEffect = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!newEffectId.trim() || !newEffectReq || !newEffectGuard || !newEffectConf.trim()) {
      setFormError('Effect ID, requester, WhiteHole guard, and confirmation rule are required.');
      return;
    }
    const next: AnchorDesignContract = {
      ...design,
      effects: [
        ...design.effects,
        {
          id: newEffectId.trim(),
          requester: newEffectReq,
          guard: newEffectGuard,
          confirmation: newEffectConf.trim(),
        },
      ],
    };
    onUpdateDesign(next);
    setNewEffectId('');
    setNewEffectConf('');
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>SCHEMA: {design.schema}</span>
            <span aria-hidden="true">·</span>
            <span>DIGEST: {validation.review.sha256.slice(0, 16)}…</span>
            <span aria-hidden="true">·</span>
            <span>AUTHORITY: DESIGN_ONLY (NONE)</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">{design.id}</h2>
          <p className="text-sm text-slate-400 mt-0.5 max-w-3xl">{design.purpose}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <button
            onClick={() =>
              onLoadIntoEditor(
                validation.renderedText,
                `${design.id}.anchor.txt`
              )
            }
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors whitespace-nowrap shrink-0"
          >
            <FileText className="w-3.5 h-3.5 text-amber-400" />
            Open .anchor.txt in Workbench
          </button>
          <button
            onClick={() =>
              onLoadIntoEditor(
                JSON.stringify(design, null, 2) + '\n',
                `${design.id}.design.json`
              )
            }
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-950 bg-amber-400 hover:bg-amber-300 rounded-lg transition-colors whitespace-nowrap shrink-0"
          >
            <FileCode className="w-3.5 h-3.5" />
            Open anchor.design/1 JSON in Workbench
          </button>
        </div>
      </div>

      {/* Validation & Rule Economy Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-lg">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>CONTRACT CONFORMANCE</span>
            <span className={validation.valid ? 'text-emerald-400' : 'text-red-400'}>
              {validation.valid ? 'VALIDATED' : `${validation.errors.length} ISSUE(S)`}
            </span>
          </div>
          <div className="mt-2 flex items-start gap-2.5">
            {validation.valid ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            )}
            <div className="text-xs text-slate-300 space-y-1">
              {validation.valid ? (
                <p>
                  All {design.applications.length} Anchor applications match immutable singularities, Neutral state
                  owners, and WhiteHole effect guards.
                </p>
              ) : (
                validation.errors.map((err, i) => (
                  <p key={i} className="text-red-300">
                    {err}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-lg">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>N-RULE-ECONOMY AUDIT</span>
            <span className="text-amber-400">{validation.review.decision}</span>
          </div>
          <p className="mt-2 text-xs text-slate-300">{RULE_ECONOMY}</p>
          <div className="mt-2 text-xs font-mono text-slate-400 space-y-1">
            <div>
              Duplicate responsibilities:{' '}
              <span className="text-slate-200 tabular-nums">
                {validation.review.duplicate_responsibilities.length}
              </span>
            </div>
            <div>
              Stateless Neutrals:{' '}
              <span className="text-slate-200">
                {validation.review.neutrals_without_declared_state.length > 0
                  ? validation.review.neutrals_without_declared_state.join(', ')
                  : 'None (all Neutrals own state)'}
              </span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-lg">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>POLARITY DISTRIBUTION</span>
            <span className="tabular-nums">{design.applications.length} TOTAL ANCHORS</span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center font-mono">
            <div className="p-2 bg-slate-950 border border-slate-800 rounded">
              <div className="text-sm font-semibold text-indigo-400 tabular-nums">{blackHoles.length}</div>
              <div className="text-[11px] text-slate-400">BlackHole</div>
            </div>
            <div className="p-2 bg-slate-950 border border-slate-800 rounded">
              <div className="text-sm font-semibold text-sky-400 tabular-nums">{whiteHoles.length}</div>
              <div className="text-[11px] text-slate-400">WhiteHole</div>
            </div>
            <div className="p-2 bg-slate-950 border border-slate-800 rounded">
              <div className="text-sm font-semibold text-emerald-400 tabular-nums">{neutrals.length}</div>
              <div className="text-[11px] text-slate-400">Neutral</div>
            </div>
          </div>
        </div>
      </div>

      {/* Three-Column Polarity Topology Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: BlackHole (Input Reception) */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col">
          <div className="pb-3 mb-3 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-indigo-400">
                01. BLACKHOLE (INPUT CAPTURE)
              </span>
              <span className="text-xs font-mono text-slate-500 tabular-nums">
                {blackHoles.length} node(s)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{DEFINITIONS.BlackHole.singularity}</p>
          </div>

          <div className="space-y-3 flex-1">
            {blackHoles.length === 0 ? (
              <div className="p-4 text-xs text-slate-500 border border-dashed border-slate-800 rounded text-center">
                No BlackHole applications declared. Add one below to capture untrusted input.
              </div>
            ) : (
              blackHoles.map((app) => {
                const isSelected = selectedNodeId === app.id;
                const outFlows = design.flows.filter((f) => f.from === app.id);
                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedNodeId(app.id)}
                    className={`p-3.5 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-950/30 border-indigo-400/60'
                        : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-indigo-300">{app.id}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveApplication(app.id);
                        }}
                        title="Remove Anchor"
                        className="text-slate-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                      {app.attributes.responsibility}
                    </p>
                    {outFlows.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-800/80 space-y-1">
                        {outFlows.map((f, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                            <ArrowRight className="w-3 h-3 text-indigo-400 shrink-0" />
                            <span className="text-slate-200">{f.to}</span>
                            <span className="text-slate-500 truncate">· {f.relationship}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Column 2: WhiteHole (Boundary Guard) */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col">
          <div className="pb-3 mb-3 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-sky-400">
                02. WHITEHOLE (BOUNDARY GUARD)
              </span>
              <span className="text-xs font-mono text-slate-500 tabular-nums">
                {whiteHoles.length} node(s)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{DEFINITIONS.WhiteHole.singularity}</p>
          </div>

          <div className="space-y-3 flex-1">
            {whiteHoles.length === 0 ? (
              <div className="p-4 text-xs text-slate-500 border border-dashed border-slate-800 rounded text-center">
                No WhiteHole guards declared. Every external effect requires a WhiteHole guard.
              </div>
            ) : (
              whiteHoles.map((app) => {
                const isSelected = selectedNodeId === app.id;
                const guardedEffects = design.effects.filter((ef) => ef.guard === app.id);
                const outFlows = design.flows.filter((f) => f.from === app.id);
                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedNodeId(app.id)}
                    className={`p-3.5 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-sky-950/30 border-sky-400/60'
                        : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-sky-300">{app.id}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveApplication(app.id);
                        }}
                        title="Remove Anchor"
                        className="text-slate-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                      {app.attributes.responsibility}
                    </p>
                    {guardedEffects.length > 0 && (
                      <div className="mt-2 text-[11px] font-mono text-sky-400">
                        Guards {guardedEffects.length} effect(s):{' '}
                        {guardedEffects.map((e) => e.id).join(', ')}
                      </div>
                    )}
                    {outFlows.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-800/80 space-y-1">
                        {outFlows.map((f, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                            <ArrowRight className="w-3 h-3 text-sky-400 shrink-0" />
                            <span className="text-slate-200">{f.to}</span>
                            <span className="text-slate-500 truncate">· {f.relationship}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Column 3: Neutral (State Owners & Relationship Processors) */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col">
          <div className="pb-3 mb-3 border-b border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-emerald-400">
                03. NEUTRAL (STATE & RELATIONSHIPS)
              </span>
              <span className="text-xs font-mono text-slate-500 tabular-nums">
                {neutrals.length} node(s)
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{DEFINITIONS.Neutral.singularity}</p>
          </div>

          <div className="space-y-3 flex-1">
            {neutrals.length === 0 ? (
              <div className="p-4 text-xs text-slate-500 border border-dashed border-slate-800 rounded text-center">
                No Neutral applications declared. Authoritative state requires a Neutral owner.
              </div>
            ) : (
              neutrals.map((app) => {
                const isSelected = selectedNodeId === app.id;
                const ownedStates = design.state.filter((s) => s.owner === app.id);
                const outFlows = design.flows.filter((f) => f.from === app.id);
                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedNodeId(app.id)}
                    className={`p-3.5 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-emerald-950/30 border-emerald-400/60'
                        : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-emerald-300">{app.id}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveApplication(app.id);
                        }}
                        title="Remove Anchor"
                        className="text-slate-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                      {app.attributes.responsibility}
                    </p>
                    <div className="mt-2 text-[11px] font-mono text-slate-400">
                      Owned state:{' '}
                      {ownedStates.length > 0 ? (
                        <span className="text-emerald-300">
                          {ownedStates.map((s) => s.id).join(', ')}
                        </span>
                      ) : (
                        <span className="text-slate-500">Stateless computation</span>
                      )}
                    </div>
                    {outFlows.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-800/80 space-y-1">
                        {outFlows.map((f, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                            <ArrowRight className="w-3 h-3 text-emerald-400 shrink-0" />
                            <span className="text-slate-200">{f.to}</span>
                            <span className="text-slate-500 truncate">· {f.relationship}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Selected Application Cryptographic Record Inspector */}
      {selectedNode && (
        <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-slate-400">SELECTED APPLICATION RECORD:</span>
              <span className="text-amber-400 font-semibold">{selectedNode.id}</span>
              <span aria-hidden="true">·</span>
              <span className="text-slate-300">{selectedNode.type}</span>
              <span aria-hidden="true">·</span>
              <span className="text-slate-400">SHA256: {selectedNode.sha256}</span>
            </div>
          </div>
          <pre className="mt-3 text-xs font-mono text-slate-300 overflow-x-auto bg-slate-950 p-3 rounded border border-slate-800">
            {canonicalJson(selectedNode)}
          </pre>
        </div>
      )}

      {/* State Ownership, Guarded Effects & Flow Tables + Interactive Builders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* State Ownership & Guarded Effects */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              State Ownership (Neutral Owners Only)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Every declared state variable in KPP must have exactly one Neutral owner.
            </p>
            <div className="mt-3 border border-slate-800 rounded overflow-hidden">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
                    <th className="py-2 px-3">State Identifier</th>
                    <th className="py-2 px-3">Neutral Owner</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70 font-mono">
                  {design.state.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-3 px-3 text-slate-500 text-center">
                        No state ownership entries declared.
                      </td>
                    </tr>
                  ) : (
                    design.state.map((st, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="py-2 px-3 text-slate-200">{st.id}</td>
                        <td className="py-2 px-3 text-emerald-400">{st.owner}</td>
                        <td className="py-2 px-3 text-right">
                          <button
                            onClick={() =>
                              onUpdateDesign({
                                ...design,
                                state: design.state.filter((_, i) => i !== idx),
                              })
                            }
                            className="text-slate-500 hover:text-red-400"
                          >
                            <Trash2 className="w-3.5 h-3.5 inline" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <form onSubmit={handleAddState} className="mt-2.5 flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={newStateId}
                onChange={(e) => setNewStateId(e.target.value)}
                placeholder="state-id (e.g. document-buffer)"
                className="flex-1 min-w-[140px] bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
              />
              <select
                value={newStateOwner}
                onChange={(e) => setNewStateOwner(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
              >
                <option value="">Select Neutral Owner…</option>
                {neutrals.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.id}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded border border-slate-700 whitespace-nowrap shrink-0"
              >
                Add State
              </button>
            </form>
          </div>

          <div className="pt-4 border-t border-slate-800">
            <h3 className="text-sm font-semibold text-slate-100">
              Guarded Effects (WhiteHole Guards Only)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Host effects require explicit WhiteHole boundary confirmation before state commit.
            </p>
            <div className="mt-3 border border-slate-800 rounded overflow-hidden">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
                    <th className="py-2 px-3">Effect ID</th>
                    <th className="py-2 px-3">Route (Req → Guard)</th>
                    <th className="py-2 px-3">Confirmation</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {design.effects.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-3 px-3 text-slate-500 font-mono text-center">
                        No guarded effects declared.
                      </td>
                    </tr>
                  ) : (
                    design.effects.map((eff, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="py-2 px-3 font-mono text-slate-200">{eff.id}</td>
                        <td className="py-2 px-3 font-mono text-sky-400">
                          {eff.requester} → {eff.guard}
                        </td>
                        <td className="py-2 px-3 text-slate-300">{eff.confirmation}</td>
                        <td className="py-2 px-3 text-right">
                          <button
                            onClick={() =>
                              onUpdateDesign({
                                ...design,
                                effects: design.effects.filter((_, i) => i !== idx),
                              })
                            }
                            className="text-slate-500 hover:text-red-400"
                          >
                            <Trash2 className="w-3.5 h-3.5 inline" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <form onSubmit={handleAddEffect} className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input
                type="text"
                value={newEffectId}
                onChange={(e) => setNewEffectId(e.target.value)}
                placeholder="effect-id (e.g. disk-write)"
                className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
              />
              <div className="flex items-center gap-1.5">
                <select
                  value={newEffectReq}
                  onChange={(e) => setNewEffectReq(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200"
                >
                  <option value="">Requester…</option>
                  {design.applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.id}
                    </option>
                  ))}
                </select>
                <select
                  value={newEffectGuard}
                  onChange={(e) => setNewEffectGuard(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200"
                >
                  <option value="">WhiteHole Guard…</option>
                  {whiteHoles.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.id}
                    </option>
                  ))}
                </select>
              </div>
              <input
                type="text"
                value={newEffectConf}
                onChange={(e) => setNewEffectConf(e.target.value)}
                placeholder="Confirmation rule (e.g. Verified host receipt required)"
                className="sm:col-span-2 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
              />
              <button
                type="submit"
                className="sm:col-span-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded border border-slate-700"
              >
                Add Guarded Effect
              </button>
            </form>
          </div>
        </div>

        {/* Add Anchor Application & Add Flow */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              Add Anchor Application (`anchor.application/1`)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Bind a contextual responsibility to an immutable KPP singularity definition.
            </p>
            {formError && (
              <div className="mt-2 p-2.5 bg-red-950/40 border border-red-800/60 rounded text-xs text-red-300">
                {formError}
              </div>
            )}
            <form onSubmit={handleAddApplication} className="mt-3 space-y-2.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    ANCHOR ID
                  </label>
                  <input
                    type="text"
                    value={newAppId}
                    onChange={(e) => setNewAppId(e.target.value)}
                    placeholder="e.g. BH-INPUT or WH-AUTH"
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-mono text-slate-400 mb-1">
                    CANONICAL DEFINITION
                  </label>
                  <select
                    value={newAppPolarity}
                    onChange={(e) => setNewAppPolarity(e.target.value as AnchorPolarity)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="BlackHole">BlackHole — Receive the declared input.</option>
                    <option value="WhiteHole">WhiteHole — Enforce the declared boundary.</option>
                    <option value="Neutral">Neutral — Apply the declared relationship.</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">
                  DECLARED RESPONSIBILITY
                </label>
                <input
                  type="text"
                  value={newAppResp}
                  onChange={(e) => setNewAppResp(e.target.value)}
                  placeholder="Describe the exact single responsibility of this Anchor…"
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
                />
              </div>
              <button
                type="submit"
                className="flex items-center justify-center gap-1.5 w-full px-3 py-2 bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-semibold rounded transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Anchor Application to Design
              </button>
            </form>
          </div>

          <div className="pt-4 border-t border-slate-800">
            <h3 className="text-sm font-semibold text-slate-100">
              Directed Responsibility Flows ({design.flows.length})
            </h3>
            <div className="mt-2 max-h-44 overflow-y-auto border border-slate-800 rounded divide-y divide-slate-800/70">
              {design.flows.map((fl, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between gap-2 px-3 py-2 text-xs hover:bg-slate-800/30"
                >
                  <div className="min-w-0">
                    <span className="font-mono text-slate-200">{fl.from}</span>
                    <span className="mx-1.5 text-amber-400 font-mono">→</span>
                    <span className="font-mono text-slate-200">{fl.to}</span>
                    <span className="text-slate-400 ml-2">· {fl.relationship}</span>
                  </div>
                  <button
                    onClick={() =>
                      onUpdateDesign({
                        ...design,
                        flows: design.flows.filter((_, i) => i !== idx),
                      })
                    }
                    className="text-slate-500 hover:text-red-400 shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            <form onSubmit={handleAddFlow} className="mt-2.5 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={newFlowFrom}
                  onChange={(e) => setNewFlowFrom(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200"
                >
                  <option value="">From Anchor…</option>
                  {design.applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.id}
                    </option>
                  ))}
                </select>
                <select
                  value={newFlowTo}
                  onChange={(e) => setNewFlowTo(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200"
                >
                  <option value="">To Anchor…</option>
                  {design.applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newFlowRel}
                  onChange={(e) => setNewFlowRel(e.target.value)}
                  placeholder="Relationship description (e.g. Validate input and bindings)"
                  className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded border border-slate-700 whitespace-nowrap shrink-0"
                >
                  Add Flow
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
