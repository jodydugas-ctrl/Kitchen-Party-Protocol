/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect } from 'react';
import { requestKpp, saveText, type NativeResult } from './lib/nativeKppClient';
import { KppWorkspaceView } from './components/KppWorkspaceView';
import { NativeRecipeProposal } from './components/NativeRecipeProposal';
import nativeNotepad from './specimens/notepad.anchor?raw';
import {
  AnchorDesignContract,
  AnchorPolarity,
  NotepadState,
  NotepadStepResult,
  PRIMER_EMIT_TEXT_V0_2,
  canonicalJson,
  initialNotepadState,
  inspectAnchorDocument,
  renderEmitTextBlueprint,
  stepNotepadCommand,
} from './lib/kppEngine';
import {
  ANCHOR_JOURNAL_DESIGN,
  KPP_SPECIMENS,
  KppSpecimen,
} from './lib/kppSpecimens';
import { TopologyVisualizer } from './components/TopologyVisualizer';
import { CodeToAnchorConverter } from './components/CodeToAnchorConverter';
import { ReferenceDocsView } from './components/ReferenceDocsView';
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  Copy,
  Download,
  FileCode,
  FilePlus2,
  FileText,
  FolderOpen,
  Layers,
  Play,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Terminal,
  Wrench,
} from 'lucide-react';

type ActiveSection = 'workbench' | 'converter' | 'topology' | 'reference' | 'workspace';
type InspectorTab = 'qualification' | 'interpreter' | 'python_bridge' | 'contract_view';

interface WorkspaceFile {
  id: string;
  title: string;
  filename: string;
  category: string;
  description: string;
  content: string;
}

const PRESET_NOTEPAD_COMMANDS: { label: string; cmd: Record<string, unknown> }[] = [
  { label: 'INSERT "Hello KPP\\n"', cmd: { op: 'INSERT', text: 'Hello Kitchen Party Protocol!\n' } },
  { label: 'INSERT "Anchor Line 2"', cmd: { op: 'INSERT', text: 'Deterministic state transition.\n' } },
  { label: 'SELECT [0, 5]', cmd: { op: 'SELECT', start: 0, end: 5 } },
  { label: 'COPY', cmd: { op: 'COPY' } },
  { label: 'FIND "Protocol"', cmd: { op: 'FIND', query: 'Protocol', match_case: true, direction: 'down' } },
  {
    label: 'REPLACE "Kitchen" -> "MantleOS"',
    cmd: { op: 'REPLACE', find: 'Kitchen', with: 'MantleOS', all: false, match_case: true },
  },
  { label: 'UNDO', cmd: { op: 'UNDO' } },
  {
    label: 'SAVE_AS "notes.txt"',
    cmd: { op: 'SAVE_AS', filename: 'notes.txt', encoding: 'UTF-8', codepage: null },
  },
  { label: 'NEW (triggers UNSAVED if dirty)', cmd: { op: 'NEW' } },
  { label: 'CONFIRM discard', cmd: { op: 'CONFIRM', choice: 'discard' } },
];

export default function App() {
  const [activeSection, setActiveSection] = useState<ActiveSection>('workbench');
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('qualification');

  const [files, setFiles] = useState<WorkspaceFile[]>(() =>
    KPP_SPECIMENS.map((s: KppSpecimen) => ({
      id: s.id,
      title: s.title,
      filename: s.filename,
      category: s.category,
      description: s.description,
      content: s.content,
    }))
  );
  const [activeFileId, setActiveFileId] = useState<string>(KPP_SPECIMENS[1].id); // ChaseStop default
  const [sidebarSearch, setSidebarSearch] = useState('');

  // Quick Anchor Entry Builder state
  const [entryId, setEntryId] = useState('Unit_2');
  const [entryPolarity, setEntryPolarity] = useState<AnchorPolarity>('Neutral');
  const [entryOpcode, setEntryOpcode] = useState('01');
  const [entryMass, setEntryMass] = useState('00');
  const [entryKey, setEntryKey] = useState('text');
  const [entryVal, setEntryVal] = useState('# Appended Anchor literal line\n');

  // Interactive Topology state
  const [activeDesign, setActiveDesign] = useState<AnchorDesignContract>(ANCHOR_JOURNAL_DESIGN);

  // NOTEPAD_LLM/1.3 Interactive Session state
  const [notepadState, setNotepadState] = useState<NotepadState>(() => initialNotepadState());
  const [notepadCommandJson, setNotepadCommandJson] = useState(
    JSON.stringify({ op: 'INSERT', text: 'Hello Kitchen Party Protocol!\n' })
  );
  const [notepadHistory, setNotepadHistory] = useState<
    { step: number; command: Record<string, unknown>; outcome: NotepadStepResult }[]
  >([]);
  const [notepadCmdError, setNotepadCmdError] = useState<string | null>(null);

  const [copiedBanner, setCopiedBanner] = useState<string | null>(null);

  const activeFile = useMemo(
    () => files.find((f) => f.id === activeFileId) ?? files[0],
    [files, activeFileId]
  );

  const inspection = useMemo(
    () => inspectAnchorDocument(activeFile.content),
    [activeFile.content]
  );

  const [nativeResult, setNativeResult] = useState<{ source: string; data: NativeResult }>();
  const [bridgeResult, setBridgeResult] = useState<{ source: string; data: NativeResult }>();
  const [bridgeBusy, setBridgeBusy] = useState(false);
  const source = activeFile.content;
  const native = nativeResult?.source === source ? nativeResult.data : undefined;
  const bridge = bridgeResult?.source === source ? bridgeResult.data : undefined;
  const nativeLabel = {
    passed: 'NATIVE KPP CHECK PASSED',
    rejected: 'NATIVE KPP REJECTED',
    unsupported: 'NATIVE CHECK NOT AVAILABLE FOR THIS FORMAT',
    unavailable: 'NATIVE KPP UNAVAILABLE',
  }[native?.status ?? 'unavailable'];
  const organSpec = useMemo(() => {
    try {
      return JSON.parse(source)?.schema === 'anchorforge.organ-spec/1';
    } catch {
      return false;
    }
  }, [source]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const data = source.trim()
          ? await requestKpp('inspect', source, controller.signal)
          : { status: 'unsupported' as const, message: 'Enter a source document to check.' };
        if (!controller.signal.aborted) setNativeResult({ source, data });
      } catch {
        if (!controller.signal.aborted) {
          setNativeResult({ source, data: { status: 'unavailable', message: 'Studio server unavailable.' } });
        }
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [source]);

  async function materializePython() {
    setBridgeBusy(true);
    try {
      setBridgeResult({ source, data: await requestKpp('bridge', source) });
    } catch {
      setBridgeResult({ source, data: { status: 'unavailable', message: 'Studio server unavailable.' } });
    } finally {
      setBridgeBusy(false);
    }
  }

  const filteredFiles = useMemo(() => {
    const q = sidebarSearch.trim().toLowerCase();
    if (!q) return files;
    return files.filter(
      (f) =>
        f.title.toLowerCase().includes(q) ||
        f.filename.toLowerCase().includes(q) ||
        f.category.toLowerCase().includes(q)
    );
  }, [files, sidebarSearch]);

  const updateActiveContent = (newContent: string) => {
    setFiles((prev) =>
      prev.map((f) => (f.id === activeFile.id ? { ...f, content: newContent } : f))
    );
  };

  const handleLoadIntoWorkbench = (content: string, filename: string) => {
    const cleanContent = content.replace(/\r\n/g, '\n');
    const existing = files.find((f) => f.filename === filename);
    if (existing) {
      setFiles((prev) =>
        prev.map((f) => (f.id === existing.id ? { ...f, content: cleanContent } : f))
      );
      setActiveFileId(existing.id);
    } else {
      const newId = `custom-${Date.now()}`;
      const newEntry: WorkspaceFile = {
        id: newId,
        title: filename,
        filename,
        category: 'Workspace Buffer',
        description: 'Loaded or generated in AnchorForge Studio session.',
        content: cleanContent.endsWith('\n') ? cleanContent : cleanContent + '\n',
      };
      setFiles((prev) => [newEntry, ...prev]);
      setActiveFileId(newId);
    }
    setActiveSection('workbench');
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const raw = typeof reader.result === 'string' ? reader.result : '';
      handleLoadIntoWorkbench(raw, file.name);
    };
    reader.readAsText(file);
  };

  const handleExportActiveArtifact = () => {
    const normalized =
      activeFile.content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const finalContent = normalized.endsWith('\n') ? normalized : normalized + '\n';
    const blob = new Blob([finalContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = activeFile.filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleNormalizeLineEndings = () => {
    let cleaned = activeFile.content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (!cleaned.endsWith('\n')) cleaned += '\n';
    updateActiveContent(cleaned);
  };

  const handleSyncBlueprintNames = () => {
    const lines = activeFile.content.split('\n');
    const bpMatch = /^ANCHOR BLUEPRINT:\s*([A-Za-z][A-Za-z0-9_]*)/.exec(lines[0] || '');
    const targetName = bpMatch ? bpMatch[1] : 'AnchorProgram';
    const updated = activeFile.content
      .replace(/^ANCHOR BLUEPRINT:\s*.*$/m, `ANCHOR BLUEPRINT: ${targetName}`)
      .replace(/^BEGIN MOLECULE\s+[A-Za-z0-9_-]*$/m, `BEGIN MOLECULE ${targetName}`)
      .replace(/^RUN\s+[A-Za-z0-9_-]*$/m, `RUN ${targetName}`);
    updateActiveContent(updated);
  };

  const handleInsertAnchorLine = (e: React.FormEvent) => {
    e.preventDefault();
    const safeId = entryId.trim().replace(/[^A-Za-z0-9_-]/g, '') || 'AnchorUnit';
    const safeOp = /^[0-9A-F]{2}$/.test(entryOpcode.trim().toUpperCase())
      ? entryOpcode.trim().toUpperCase()
      : '01';
    const safeMass = /^[0-9A-F]{2}$/.test(entryMass.trim().toUpperCase())
      ? entryMass.trim().toUpperCase()
      : '00';
    const safeKey = entryKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, '') || 'text';
    const encodedVal = JSON.stringify(entryVal);
    const newLine = `${safeId}: ${entryPolarity} -${safeOp} -${safeMass} -${safeKey}=${encodedVal}`;

    if (activeFile.content.includes('END MOLECULE')) {
      const idx = activeFile.content.lastIndexOf('END MOLECULE');
      const updated =
        activeFile.content.slice(0, idx) +
        newLine +
        '\n' +
        activeFile.content.slice(idx);
      updateActiveContent(updated);
    } else {
      const updated =
        activeFile.content.replace(/\n?$/, '\n') + newLine + '\n';
      updateActiveContent(updated);
    }
  };

  const handleCreateTemplate = (
    templateType: 'EMIT_TEXT/0.2' | 'NOTEPAD_LLM/1.3' | 'anchor.design/1'
  ) => {
    if (templateType === 'EMIT_TEXT/0.2') {
      const content = renderEmitTextBlueprint('NewModule', 'Hello from KPP EMIT_TEXT/0.2!\n');
      handleLoadIntoWorkbench(content, 'NewModule.anchor');
    } else if (templateType === 'NOTEPAD_LLM/1.3') {
      const content = nativeNotepad;
      handleLoadIntoWorkbench(content, 'XPNotepad_LLM_v1.anchor');
    } else {
      const content = JSON.stringify(ANCHOR_JOURNAL_DESIGN, null, 2) + '\n';
      handleLoadIntoWorkbench(content, 'custom-design.json');
    }
  };

  const executeNotepadStep = (cmdObj: Record<string, unknown>) => {
    setNotepadCmdError(null);
    const outcome = stepNotepadCommand(notepadState, cmdObj, true);
    setNotepadState(outcome.state);
    setNotepadHistory((prev) => [
      { step: prev.length + 1, command: cmdObj, outcome },
      ...prev,
    ]);
  };

  const handleRunCustomNotepadJson = (e: React.FormEvent) => {
    e.preventDefault();
    setNotepadCmdError(null);
    try {
      const parsed = JSON.parse(notepadCommandJson);
      executeNotepadStep(parsed);
    } catch (err: unknown) {
      setNotepadCmdError(err instanceof Error ? err.message : 'Invalid JSON command');
    }
  };

  const copyToClipboard = (label: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedBanner(label);
    setTimeout(() => setCopiedBanner(null), 1800);
  };

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex flex-col">
      {/* STRICT 3-ZONE TOP BAR CONTRACT */}
      <header className="flex items-center justify-between gap-8 px-6 py-3.5 bg-[#0F1623] border-b border-slate-800">
        {/* Zone 1: Single text element Brand wordmark */}
        <a
          href="#workbench"
          onClick={(e) => {
            e.preventDefault();
            setActiveSection('workbench');
          }}
          className="text-lg font-bold tracking-tight text-slate-100 whitespace-nowrap shrink-0 font-display"
        >
          AnchorForge Studio
        </a>

        {/* Zone 2: 4 concise single-line navigation links */}
        <nav className="flex items-center gap-6 text-sm font-medium text-slate-400 overflow-x-auto">
          <a
            href="#workbench"
            onClick={(e) => {
              e.preventDefault();
              setActiveSection('workbench');
            }}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeSection === 'workbench'
                ? 'text-amber-400 border-amber-400'
                : 'border-transparent hover:text-slate-100'
            }`}
          >
            Workbench
          </a>
          <a
            href="#converter"
            onClick={(e) => {
              e.preventDefault();
              setActiveSection('converter');
            }}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeSection === 'converter'
                ? 'text-amber-400 border-amber-400'
                : 'border-transparent hover:text-slate-100'
            }`}
          >
            Code Converter
          </a>
          <a
            href="#topology"
            onClick={(e) => {
              e.preventDefault();
              if (inspection.designContract) {
                setActiveDesign(inspection.designContract);
              }
              setActiveSection('topology');
            }}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeSection === 'topology'
                ? 'text-amber-400 border-amber-400'
                : 'border-transparent hover:text-slate-100'
            }`}
          >
            Topology &amp; Design
          </a>
          <button type="button" onClick={() => setActiveSection('workspace')}
            className={`py-1 whitespace-nowrap border-b-2 ${activeSection === 'workspace' ? 'text-amber-400 border-amber-400' : 'border-transparent hover:text-slate-100'}`}>
            KPP Workspace
          </button>
          <a
            href="#reference"
            onClick={(e) => {
              e.preventDefault();
              setActiveSection('reference');
            }}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeSection === 'reference'
                ? 'text-amber-400 border-amber-400'
                : 'border-transparent hover:text-slate-100'
            }`}
          >
            Protocol Specs
          </a>
        </nav>

        {/* Zone 3: 1 Primary Action */}
        <div className="flex items-center shrink-0">
          <button
            onClick={handleExportActiveArtifact}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-slate-950 bg-amber-400 hover:bg-amber-300 rounded-lg transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="w-3.5 h-3.5" />
            Export Artifact
          </button>
        </div>
      </header>

      {/* MAIN VIEWPORT */}
      {activeSection === 'workbench' && (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-[calc(100vh-57px)]">
          {/* LEFT SIDEBAR: Specimen & File Pantry (2.5 cols on desktop) */}
          <aside className="lg:col-span-3 xl:col-span-2 bg-[#0E1420] border-r border-slate-800 p-4 flex flex-col justify-between gap-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-slate-300">
                  KPP SPECIMENS &amp; FILES
                </span>
                <span className="text-xs font-mono text-slate-500 tabular-nums">
                  {files.length}
                </span>
              </div>

              {/* File Upload & New Template Buttons */}
              <div className="grid grid-cols-2 gap-2">
                <label className="flex items-center justify-center gap-1.5 px-2.5 py-2 text-xs font-medium text-slate-200 bg-slate-800/90 hover:bg-slate-700 border border-slate-700 rounded cursor-pointer transition-colors whitespace-nowrap">
                  <FolderOpen className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  Load File
                  <input
                    type="file"
                    accept=".anchor,.txt,.json,.py,.js,.ts,.md"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
                <button
                  onClick={() => handleCreateTemplate('EMIT_TEXT/0.2')}
                  className="flex items-center justify-center gap-1.5 px-2.5 py-2 text-xs font-medium text-slate-200 bg-slate-800/90 hover:bg-slate-700 border border-slate-700 rounded transition-colors whitespace-nowrap"
                >
                  <FilePlus2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  New .anchor
                </button>
              </div>

              {/* Search Filter */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  value={sidebarSearch}
                  onChange={(e) => setSidebarSearch(e.target.value)}
                  placeholder="Filter specimens…"
                  className="w-full bg-slate-950 border border-slate-800 rounded pl-8 pr-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
                />
              </div>

              {/* File List */}
              <div className="space-y-1.5 max-h-[54vh] overflow-y-auto pr-1">
                {filteredFiles.map((item) => {
                  const isActive = item.id === activeFile.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActiveFileId(item.id)}
                      className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                        isActive
                          ? 'bg-slate-800/90 border-amber-400/60 text-slate-100'
                          : 'bg-slate-950/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      }`}
                    >
                      <div className="text-xs font-semibold truncate">{item.title}</div>
                      <div className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                        {item.filename} · {item.category}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Quick Template Generators */}
            <div className="pt-3 border-t border-slate-800 space-y-2">
              <div className="text-[11px] font-mono text-slate-400">
                QUICK PROFILE TEMPLATES
              </div>
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={() => handleCreateTemplate('NOTEPAD_LLM/1.3')}
                  className="text-left px-2.5 py-1.5 text-xs font-mono text-slate-300 hover:text-amber-300 bg-slate-950 border border-slate-800 rounded transition-colors truncate"
                >
                  + NOTEPAD_LLM/1.3 Blueprint
                </button>
                <button
                  onClick={() => handleCreateTemplate('anchor.design/1')}
                  className="text-left px-2.5 py-1.5 text-xs font-mono text-slate-300 hover:text-amber-300 bg-slate-950 border border-slate-800 rounded transition-colors truncate"
                >
                  + anchor.design/1 Contract
                </button>
              </div>
            </div>
          </aside>

          {/* CENTER WORKSPACE: Anchor Code Editor & Authoring Tools (5 cols) */}
          <main className="lg:col-span-5 xl:col-span-5 border-r border-slate-800 flex flex-col bg-[#0B0F17]">
            {/* Editor Context Bar */}
            <div className="px-4 py-3 bg-[#111827] border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="font-semibold text-slate-100 truncate">
                    {activeFile.filename}
                  </span>
                  <span aria-hidden="true" className="text-slate-600">
                    ·
                  </span>
                  <span className="text-amber-400">{inspection.profile}</span>
                </div>
                <p className="text-xs text-slate-400 truncate mt-0.5">
                  {activeFile.description}
                </p>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {(inspection.hasCrLfWarning || inspection.missingFinalLfWarning) && (
                  <button
                    onClick={handleNormalizeLineEndings}
                    className="px-2.5 py-1 text-xs font-mono text-amber-300 bg-amber-950/50 border border-amber-700/60 rounded hover:bg-amber-900/50 transition-colors whitespace-nowrap"
                  >
                    Fix Line Endings (LF)
                  </button>
                )}
                {inspection.kind === 'EMIT_TEXT/0.2' && (
                  <button
                    onClick={handleSyncBlueprintNames}
                    title="Ensure ANCHOR BLUEPRINT, BEGIN MOLECULE, and RUN names match"
                    className="px-2.5 py-1 text-xs font-mono text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors whitespace-nowrap"
                  >
                    Sync IDs
                  </button>
                )}
                <button
                  onClick={() => copyToClipboard('Source', activeFile.content)}
                  className="p-1.5 text-slate-400 hover:text-slate-100 bg-slate-800/80 border border-slate-700 rounded"
                  title="Copy Source"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Code Editor Textarea */}
            <div className="flex-1 relative flex flex-col">
              <textarea
                value={activeFile.content}
                onChange={(e) => updateActiveContent(e.target.value)}
                spellCheck={false}
                className="flex-1 w-full bg-[#090D14] text-slate-100 font-mono text-xs leading-relaxed p-4 focus:outline-none resize-none"
                placeholder="Write or load Kitchen Party Protocol Anchor Code here…"
              />

              {/* Unboxed Metadata Footer Bar */}
              <div className="px-4 py-2 bg-[#0F1623] border-t border-slate-800 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="tabular-nums">{inspection.lineCount} lines</span>
                  <span aria-hidden="true">·</span>
                  <span className="tabular-nums">{inspection.byteLength} UTF-8 bytes</span>
                  <span aria-hidden="true">·</span>
                  <span>SHA256: {inspection.sourceSha256.slice(0, 12)}…</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>AUTHORITY: {inspection.authority}</span>
                  <span aria-hidden="true">·</span>
                  <span className={native?.status === 'passed' ? 'text-emerald-400' : 'text-slate-300'}>
                    {native ? nativeLabel : 'NATIVE CHECK PENDING'}
                  </span>
                </div>
              </div>
            </div>

            {/* Bottom Authoring Helper: Universal Anchor Entry Builder */}
            <div className="p-4 bg-[#111827] border-t border-slate-800 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-amber-400" />
                  INSERT UNIVERSAL ANCHOR ENTRY (`ID: TYPE -OP -MASS -KEY=JSON`)
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (!activeFile.content.includes('BEGIN ANCHOR EXECUTION PRIMER')) {
                      updateActiveContent(
                        `ANCHOR BLUEPRINT: CustomProgram\nSTATUS: EXPERIMENTAL EMIT_TEXT/0.2\n\n${PRIMER_EMIT_TEXT_V0_2}\n\nBEGIN MOLECULE CustomProgram\nA: Neutral -01 -00 -text="Hello"\nEND MOLECULE\n\nBEGIN EXECUTION\nRUN CustomProgram\nEND EXECUTION\n`
                      );
                    }
                  }}
                  className="text-[11px] font-mono text-amber-400 hover:underline"
                >
                  Insert Pinned EMIT_TEXT/0.2 Primer
                </button>
              </div>

              <form onSubmit={handleInsertAnchorLine} className="space-y-2">
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  <input
                    type="text"
                    value={entryId}
                    onChange={(e) => setEntryId(e.target.value)}
                    placeholder="ID (e.g. A)"
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                  <select
                    value={entryPolarity}
                    onChange={(e) => {
                      const pol = e.target.value as AnchorPolarity;
                      setEntryPolarity(pol);
                      if (pol === 'WhiteHole') {
                        setEntryOpcode('10');
                        setEntryKey('policy');
                      } else if (pol === 'BlackHole') {
                        setEntryOpcode('20');
                        setEntryKey('input');
                      } else {
                        setEntryOpcode('01');
                        setEntryKey('text');
                      }
                    }}
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="Neutral">Neutral</option>
                    <option value="BlackHole">BlackHole</option>
                    <option value="WhiteHole">WhiteHole</option>
                  </select>
                  <input
                    type="text"
                    value={entryOpcode}
                    onChange={(e) => setEntryOpcode(e.target.value)}
                    placeholder="OP (01)"
                    maxLength={2}
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                  <input
                    type="text"
                    value={entryMass}
                    onChange={(e) => setEntryMass(e.target.value)}
                    placeholder="MASS (00)"
                    maxLength={2}
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                  <input
                    type="text"
                    value={entryKey}
                    onChange={(e) => setEntryKey(e.target.value)}
                    placeholder="key (text)"
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={entryVal}
                    onChange={(e) => setEntryVal(e.target.value)}
                    placeholder="Raw string value (automatically JSON-escaped on insert)…"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                  />
                  <button
                    type="submit"
                    className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 text-xs font-medium rounded border border-slate-700 whitespace-nowrap shrink-0"
                  >
                    <Plus className="w-3.5 h-3.5 text-amber-400" />
                    Append Anchor
                  </button>
                </div>
              </form>
            </div>
          </main>

          {/* RIGHT INSPECTOR: Qualification, Live Interpreter & Python Bridge (4.5 cols) */}
          <section className="lg:col-span-4 xl:col-span-5 bg-[#0E1420] flex flex-col">
            {/* Segmented Control Tabs */}
            <div className="p-2.5 bg-[#111827] border-b border-slate-800 flex items-center gap-1 overflow-x-auto">
              <button
                onClick={() => setInspectorTab('qualification')}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 ${
                  inspectorTab === 'qualification'
                    ? 'bg-slate-800 text-amber-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Qualification &amp; Receipt
              </button>
              <button
                onClick={() => setInspectorTab('interpreter')}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 ${
                  inspectorTab === 'interpreter'
                    ? 'bg-slate-800 text-amber-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Live Interpreter
              </button>
              <button
                onClick={() => setInspectorTab('python_bridge')}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 ${
                  inspectorTab === 'python_bridge'
                    ? 'bg-slate-800 text-amber-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                bridge-python Target
              </button>
              <button
                onClick={() => setInspectorTab('contract_view')}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 ${
                  inspectorTab === 'contract_view'
                    ? 'bg-slate-800 text-amber-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Design &amp; Topology
              </button>
            </div>

            {copiedBanner && (
              <div className="px-4 py-1.5 bg-emerald-950/60 border-b border-emerald-800/60 text-xs font-mono text-emerald-300">
                Copied {copiedBanner} to clipboard.
              </div>
            )}

            <div className="p-4 flex-1 overflow-y-auto space-y-5">
              {/* TAB 1: QUALIFICATION & RECEIPT */}
              {inspectorTab === 'qualification' && (
                <div className="space-y-5">
                  <section aria-live="polite" className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs">
                    <p className="font-semibold text-slate-100">{native ? nativeLabel : 'Native check pending'}</p>
                    {native?.message && <p className="mt-1 text-slate-300">{native.message}</p>}
                    {native?.status === 'passed' && (
                      <p className="mt-1 text-slate-300">
                        {native.kind} checked against the configured KPP runtime. Baker acceptance remains separate.
                      </p>
                    )}
                  </section>
                  {organSpec && <NativeRecipeProposal spec={source} />}
                  {/* Local projection */}
                  <div
                    className={`p-3.5 rounded-lg border ${
                      inspection.valid
                        ? 'bg-emerald-950/20 border-emerald-800/60'
                        : 'bg-red-950/30 border-red-800/60'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {inspection.valid ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                      )}
                      <div className="space-y-1 text-xs">
                        <div className="font-mono font-semibold text-slate-100">
                          {inspection.valid
                            ? `LOCAL PROJECTION · ${inspection.anchors.length} Anchor(s) (${inspection.profile})`
                            : `LOCAL PROJECTION · ${inspection.errors.length} issue(s)`}
                        </div>
                        {inspection.errors.length > 0 ? (
                          <ul className="space-y-1 text-red-300 font-mono">
                            {inspection.errors.map((err, i) => (
                              <li key={i}>• {err}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-300">
                            Uniform Anchor shape (`id`, `type`, `opcode`, `mass`, `variable`) and
                            stage skeleton (`REACH`, `QUALIFY`, `ROUTE`) shown.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Qualification Receipt JSON */}
                  {inspection.qualificationReceipt && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-semibold text-slate-300">
                          LOCAL EMIT_TEXT RECEIPT
                        </span>
                        <button
                          onClick={() =>
                            copyToClipboard(
                              'Qualification Receipt',
                              JSON.stringify(inspection.qualificationReceipt, null, 2)
                            )
                          }
                          className="text-xs font-mono text-amber-400 hover:underline"
                        >
                          Copy Receipt JSON
                        </button>
                      </div>
                      <pre className="p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                        {JSON.stringify(inspection.qualificationReceipt, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Parsed Universal Anchor Entries Table */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-semibold text-slate-300">
                        SERIALIZED ANCHOR ENTRIES ({inspection.anchors.length})
                      </span>
                      <span className="text-xs font-mono text-slate-500">
                        Polarities: {inspection.polarities.join(', ') || 'None'}
                      </span>
                    </div>
                    <div className="border border-slate-800 rounded overflow-hidden">
                      <table className="w-full text-left border-collapse text-xs font-mono">
                        <thead>
                          <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
                            <th className="py-2 px-2.5">ID</th>
                            <th className="py-2 px-2.5">Polarity</th>
                            <th className="py-2 px-2.5">OP/Mass</th>
                            <th className="py-2 px-2.5">Variable Slot</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/70">
                          {inspection.anchors.length === 0 ? (
                            <tr>
                              <td colSpan={4} className="py-4 px-3 text-slate-500 text-center">
                                No valid Anchor entries parsed.
                              </td>
                            </tr>
                          ) : (
                            inspection.anchors.map((a) => (
                              <tr key={a.id} className="hover:bg-slate-900/60">
                                <td className="py-2 px-2.5 text-slate-100 font-semibold">
                                  {a.id}
                                </td>
                                <td className="py-2 px-2.5">
                                  <span
                                    className={
                                      a.type === 'BlackHole'
                                        ? 'text-indigo-400'
                                        : a.type === 'WhiteHole'
                                        ? 'text-sky-400'
                                        : 'text-emerald-400'
                                    }
                                  >
                                    {a.type}
                                  </span>
                                </td>
                                <td className="py-2 px-2.5 text-slate-400 tabular-nums">
                                  -{a.opcode} -{a.mass}
                                </td>
                                <td className="py-2 px-2.5 text-slate-300 truncate max-w-[200px]">
                                  {a.variable}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: LIVE INTERPRETER */}
              {inspectorTab === 'interpreter' && (
                <div className="space-y-5">
                  {inspection.kind === 'EMIT_TEXT/0.2' ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs font-mono font-semibold text-emerald-400">
                            EMIT_TEXT/0.2 DETERMINISTIC STDOUT (`program_stdout`)
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Concatenated decoded JSON string literals in Molecule order. Emitted text
                            remains data (`effect_claim: NONE`).
                          </p>
                        </div>
                        {inspection.stdout !== undefined && (
                          <button
                            onClick={() => copyToClipboard('Program Stdout', inspection.stdout!)}
                            className="px-2.5 py-1 text-xs font-mono text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded whitespace-nowrap"
                          >
                            Copy Output
                          </button>
                        )}
                      </div>

                      {inspection.stdout !== undefined ? (
                        <>
                          <div className="flex items-center gap-3 text-xs font-mono text-slate-400 bg-slate-950 px-3 py-2 rounded border border-slate-800">
                            <span className="tabular-nums">
                              BYTES: {inspection.qualificationReceipt?.stdout_bytes}
                            </span>
                            <span aria-hidden="true">·</span>
                            <span>
                              STDOUT SHA256:{' '}
                              {inspection.qualificationReceipt?.stdout_sha256.slice(0, 16)}…
                            </span>
                          </div>
                          <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-emerald-300 overflow-x-auto max-h-[52vh] leading-relaxed">
                            {inspection.stdout}
                          </pre>
                        </>
                      ) : (
                        <div className="p-4 bg-red-950/30 border border-red-800/60 rounded text-xs font-mono text-red-300">
                          Cannot emit stdout until Blueprint validation errors are resolved.
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Interactive NOTEPAD_LLM/1.3 Session Stepper */
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs font-mono font-semibold text-amber-400">
                            LOCAL NOTEPAD COMMAND SIMULATION
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Step explicit JSON commands against the stateful KPP editor session and
                            inspect every `AFTER` checkpoint.
                          </p>
                        </div>
                        <button
                          onClick={() => {
                            setNotepadState(initialNotepadState());
                            setNotepadHistory([]);
                          }}
                          className="flex items-center gap-1 px-2.5 py-1 text-xs font-mono text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded whitespace-nowrap"
                        >
                          <RotateCcw className="w-3 h-3" /> Reset Session
                        </button>
                      </div>

                      {/* Preset Commands */}
                      <div className="flex flex-wrap gap-1.5">
                        {PRESET_NOTEPAD_COMMANDS.map((preset, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              setNotepadCommandJson(JSON.stringify(preset.cmd));
                              executeNotepadStep(preset.cmd);
                            }}
                            className="px-2.5 py-1 text-[11px] font-mono text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded transition-colors whitespace-nowrap"
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>

                      {/* Custom JSON Command Input */}
                      <form onSubmit={handleRunCustomNotepadJson} className="flex gap-2">
                        <input
                          type="text"
                          value={notepadCommandJson}
                          onChange={(e) => setNotepadCommandJson(e.target.value)}
                          className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
                        />
                        <button
                          type="submit"
                          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-semibold rounded whitespace-nowrap shrink-0"
                        >
                          <Play className="w-3.5 h-3.5" /> Step Command
                        </button>
                      </form>
                      {notepadCmdError && (
                        <div className="text-xs font-mono text-red-400">{notepadCmdError}</div>
                      )}

                      {/* Current Buffer & State Summary */}
                      <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono text-slate-400">
                          <span>
                            FILE: <strong className="text-slate-200">{notepadState.filename ?? 'Untitled'}</strong>
                          </span>
                          <span aria-hidden="true">·</span>
                          <span>
                            DIRTY:{' '}
                            <strong className={notepadState.dirty ? 'text-amber-400' : 'text-emerald-400'}>
                              {String(notepadState.dirty)}
                            </strong>
                          </span>
                          <span aria-hidden="true">·</span>
                          <span className="tabular-nums">
                            CARET: {notepadState.caret} · SEL: [{notepadState.selection[0]},{' '}
                            {notepadState.selection[1]}]
                          </span>
                          {notepadState.pending && (
                            <>
                              <span aria-hidden="true">·</span>
                              <span className="text-amber-400">
                                PENDING: {JSON.stringify(notepadState.pending)}
                              </span>
                            </>
                          )}
                        </div>
                        <pre className="p-2.5 bg-[#090D14] border border-slate-800/80 rounded text-xs font-mono text-slate-200 min-h-[72px] whitespace-pre-wrap">
                          {notepadState.text || '(empty document buffer)'}
                        </pre>
                      </div>

                      {/* Step Trace History */}
                      <div className="space-y-2">
                        <div className="text-xs font-mono text-slate-400">
                          COMMAND TRACE &amp; AFTER CHECKPOINTS ({notepadHistory.length})
                        </div>
                        <div className="space-y-2 max-h-56 overflow-y-auto">
                          {notepadHistory.map((item) => (
                            <div
                              key={item.step}
                              className="p-2.5 bg-slate-950 border border-slate-800 rounded text-xs font-mono space-y-1"
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-slate-300">
                                  #{item.step} { canonicalJson(item.command) }
                                </span>
                                <span
                                  className={
                                    item.outcome.result === 'OK'
                                      ? 'text-emerald-400'
                                      : 'text-amber-400'
                                  }
                                >
                                  {item.outcome.result} · {item.outcome.effect_claim}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: BRIDGE-PYTHON TARGET COMPILER */}
              {inspectorTab === 'python_bridge' && (
                <div className="space-y-3 text-xs">
                  <p className="font-semibold text-sky-400">Native KPP Python bridge</p>
                  <p className="text-slate-300">
                    Materialize syntax-checked Python from an EMIT_TEXT/0.2 carrier. KPP treats the emitted source as data.
                  </p>
                  <button onClick={materializePython} disabled={bridgeBusy}
                    className="rounded bg-slate-800 px-3 py-2 text-slate-100 disabled:opacity-50">
                    {bridgeBusy ? 'Checking carrier…' : 'Run bridge-python'}
                  </button>
                  {bridge?.message && <p role="status" className="text-slate-300">{bridge.message}</p>}
                  {bridge?.status === 'passed' && bridge.python !== undefined && (
                    <>
                      <button className="ml-3 text-sky-300"
                        onClick={() => saveText(bridge.python!, activeFile.filename.replace(/\.[^.]+$/, '') + '.py')}>
                        Save .py
                      </button>
                      <pre className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-3 text-sky-300">
                        {bridge.python}
                      </pre>
                    </>
                  )}
                </div>
              )}

              {/* TAB 4: DESIGN CONTRACT & TOPOLOGY PREVIEW */}
              {inspectorTab === 'contract_view' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-mono font-semibold text-amber-400">
                        RESPONSIBILITY TOPOLOGY &amp; .ANCHOR.TXT PROJECTION
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Structural projection of `BlackHole`, `WhiteHole`, and `Neutral`
                        responsibilities.
                      </p>
                    </div>
                    {inspection.designContract && (
                      <button
                        onClick={() => {
                          setActiveDesign(inspection.designContract!);
                          setActiveSection('topology');
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-950 bg-amber-400 hover:bg-amber-300 rounded whitespace-nowrap"
                      >
                        <Layers className="w-3.5 h-3.5" /> Open Full Topology Editor
                      </button>
                    )}
                  </div>

                  {inspection.renderedDesignText ? (
                    <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                      {inspection.renderedDesignText}
                    </pre>
                  ) : inspection.designContract ? (
                    <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                      {JSON.stringify(inspection.designContract, null, 2)}
                    </pre>
                  ) : (
                    <div className="p-4 bg-slate-950 border border-slate-800 rounded text-xs text-slate-400">
                      No responsibility projection available for the current buffer.
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* VIEW 2: CODE-TO-ANCHOR CONVERTER */}
      {activeSection === 'converter' && (
        <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6">
          <CodeToAnchorConverter
            onOpenInWorkbench={(content, filename) =>
              handleLoadIntoWorkbench(content, filename)
            }
            onSendDesignToTopology={(design) => {
              setActiveDesign(design);
              setActiveSection('topology');
            }}
          />
        </main>
      )}

      {/* VIEW 3: INTERACTIVE TOPOLOGY & DESIGN STUDIO */}
      {activeSection === 'topology' && (
        <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6">
          <TopologyVisualizer
            design={activeDesign}
            onUpdateDesign={setActiveDesign}
            onLoadIntoEditor={(content, filename) =>
              handleLoadIntoWorkbench(content, filename)
            }
          />
        </main>
      )}

      {activeSection === 'workspace' && <main className="flex-1"><KppWorkspaceView /></main>}

      {/* VIEW 4: PROTOCOL REFERENCE & SPECS */}
      {activeSection === 'reference' && (
        <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6">
          <ReferenceDocsView />
        </main>
      )}
    </div>
  );
}
