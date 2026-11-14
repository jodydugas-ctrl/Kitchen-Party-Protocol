import { useEffect, useState } from 'react';

interface BuildStep {
  recipe_id: string;
  recipe_sha256: string;
  revision: number;
  phase: string;
  decision: string;
  next: { id: string; statement: string; test: string } | null;
  unmet_anchors?: string[];
  accepted?: string[];
}

export function KppWorkspaceView() {
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<{ workspace?: BuildStep; message?: string }>();

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/kpp/workspace', { signal: controller.signal })
      .then((response) => response.json())
      .then((data) => { if (!controller.signal.aborted) setResult(data); })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ message: 'Studio server unavailable.' });
      });
    return () => controller.abort();
  }, [refresh]);

  const step = result?.workspace;
  return (
    <section className="mx-auto max-w-4xl space-y-5 px-5 py-8">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-slate-100">KPP workspace</h2>
        <button className="rounded bg-slate-800 px-3 py-2 text-xs text-slate-100" onClick={() => {
          setResult(undefined);
          setRefresh((value) => value + 1);
        }}>Refresh</button>
      </div>
      <div aria-live="polite">
        {!step && <p className="text-sm text-slate-300">{result?.message ?? 'Reading native build step…'}</p>}
        {step && (
          <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-5 text-sm text-slate-300">
            <p className="font-mono text-amber-300">{step.phase} · {step.decision.replaceAll('_', ' ')}</p>
            <h3 className="text-lg font-semibold text-slate-100">{step.recipe_id} · revision {step.revision}</h3>
            <p className="break-all font-mono text-xs">Recipe SHA-256 {step.recipe_sha256}</p>
            {step.next && (
              <div className="space-y-2 border-t border-slate-800 pt-3">
                <h4 className="font-semibold text-slate-100">Next obligation · {step.next.id}</h4>
                <p>{step.next.statement}</p>
                <p><strong>Acceptance test</strong> · {step.next.test}</p>
              </div>
            )}
            {step.unmet_anchors?.length ? <p><strong>Unmet</strong> · {step.unmet_anchors.join(', ')}</p> : null}
            {step.accepted?.length ? <p><strong>Accepted</strong> · {step.accepted.join(', ')}</p> : null}
          </div>
        )}
      </div>
    </section>
  );
}
