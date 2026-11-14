export interface NativeResult {
  status: 'passed' | 'rejected' | 'unsupported' | 'unavailable';
  message?: string;
  sourceSha256?: string;
  kind?: string;
  python?: string;
  recipe?: { id: string };
  review?: { recipe_sha256: string; added_obligation_ids?: string[] };
  workPacket?: string;
}

export async function requestKpp(
  operation: 'inspect' | 'bridge' | 'propose' | 'extend' | 'brief',
  source: string,
  signal?: AbortSignal,
): Promise<NativeResult> {
  const response = await fetch(`/api/kpp/${operation}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
    signal,
  });
  return response.json();
}

export function saveText(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
