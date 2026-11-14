import { useState } from 'react';
import { requestKpp, saveText, type NativeResult } from '../lib/nativeKppClient';

const extensionTemplate = JSON.stringify({
  schema: 'anchorforge.extension/1',
  new_obligations: [],
}, null, 2);

export function RecipeHandoff({ source, recipeId }: { source: string; recipeId: string }) {
  const [extension, setExtension] = useState(extensionTemplate);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ operation: 'brief' | 'extend'; extension: string; data: NativeResult }>();
  const data = result?.operation === 'brief' || result?.extension === extension ? result?.data : undefined;

  async function run(operation: 'brief' | 'extend') {
    setResult(undefined);
    setBusy(true);
    try {
      const input = operation === 'brief'
        ? source
        : JSON.stringify({ recipe: source, extension });
      const data = await requestKpp(operation, input);
      setResult({ operation, extension, data });
    } catch {
      setResult({ operation, extension, data: { status: 'unavailable', message: 'Could not reach native KPP.' } });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300">
      <h3 className="font-semibold text-slate-100">Recipe handoff</h3>
      <button type="button" disabled={busy} onClick={() => run('brief')}
        className="rounded bg-slate-800 px-3 py-2 text-slate-100 disabled:opacity-50">
        Prepare KPP work packet
      </button>
      <details className="space-y-2">
        <summary className="cursor-pointer">Extend Recipe with AnchorForge</summary>
        <p>Add obligations using `anchorforge.extension/1`. Each new obligation needs an ID, statement, test, depth, and required flag.</p>
        <textarea aria-label="AnchorForge extension" spellCheck={false}
          className="h-40 w-full rounded bg-slate-900 p-2 font-mono text-slate-100"
          value={extension} onChange={(event) => setExtension(event.target.value)} />
        <button type="button" disabled={busy} onClick={() => run('extend')}
          className="rounded bg-amber-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-50">
          Propose Recipe extension
        </button>
      </details>
      <div className="space-y-2" aria-live="polite">
        {busy && <p>Waiting for native KPP…</p>}
        {data?.message && <p>{data.message}</p>}
        {data?.workPacket && (
          <>
            <button type="button" className="text-sky-300" onClick={() => saveText(data.workPacket!, `${recipeId}.work-packet.txt`)}>
              Download work packet
            </button>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-2">{data.workPacket}</pre>
          </>
        )}
        {data?.recipe && data.review && (
          <>
            <p>Added {data.review.added_obligation_ids?.join(', ')}. Baker review is pending.</p>
            <p className="break-all font-mono">Recipe SHA-256 {data.review.recipe_sha256}</p>
            <div className="flex flex-wrap gap-3 text-sky-300">
              <button type="button" onClick={() => saveText(JSON.stringify(data.recipe, null, 2) + '\n', `${recipeId}.extended.json`)}>Download extended Recipe</button>
              <button type="button" onClick={() => saveText(JSON.stringify(data.review, null, 2) + '\n', `${recipeId}.extended.review.json`)}>Download extension review</button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
