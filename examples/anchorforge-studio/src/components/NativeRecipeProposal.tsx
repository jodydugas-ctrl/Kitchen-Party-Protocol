import { useState } from 'react';
import { requestKpp, saveText, type NativeResult } from '../lib/nativeKppClient';

export function NativeRecipeProposal({ spec, editable = false }: { spec: string; editable?: boolean }) {
  const [draft, setDraft] = useState<string>();
  const source = draft ?? spec;
  const [result, setResult] = useState<{ spec: string; data: NativeResult }>();
  const [busy, setBusy] = useState(false);
  const data = result?.spec === source ? result.data : undefined;

  async function propose() {
    setBusy(true);
    try {
      setResult({ spec: source, data: await requestKpp('propose', source) });
    } catch {
      setResult({ spec: source, data: { status: 'unavailable', message: 'Studio server unavailable.' } });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-2 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs">
      {editable && (
        <details>
          <summary className="cursor-pointer text-slate-200">Review and edit AnchorForge input</summary>
          <textarea aria-label="AnchorForge input" className="mt-2 h-52 w-full rounded bg-slate-900 p-2 font-mono text-slate-100"
            spellCheck={false} value={source} onChange={(event) => setDraft(event.target.value)} />
        </details>
      )}
      <button type="button" disabled={busy} onClick={propose}
        className="rounded bg-amber-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-50">
        {busy ? 'Checking with AnchorForge…' : 'Propose Recipe with AnchorForge'}
      </button>
      <div aria-live="polite" className="text-slate-300">
        {data?.message}
        {data?.recipe && data.review && (
          <div className="space-y-2">
            <p>{data.recipe.id} passed native structural checks. Baker acceptance pending.</p>
            <p className="break-all font-mono">Recipe SHA-256 {data.review.recipe_sha256}</p>
            <div className="flex flex-wrap gap-3 text-sky-300">
              <button onClick={() => saveText(JSON.stringify(data.recipe, null, 2) + '\n', `${data.recipe!.id}.json`)}>Download Recipe</button>
              <button onClick={() => saveText(JSON.stringify(data.review, null, 2) + '\n', `${data.recipe!.id}.review.json`)}>Download review</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
