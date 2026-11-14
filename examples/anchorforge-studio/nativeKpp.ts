import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const adapter = fileURLToPath(new URL('./native/kpp_bridge.py', import.meta.url));

export function nativeKpp(operation: 'inspect' | 'bridge' | 'propose' | 'workspace', source: string) {
  const root = process.env.KPP_ROOT || fileURLToPath(new URL('../../', import.meta.url));
  const workspace = process.env.KPP_WORKSPACE;
  if (operation === 'workspace' && !workspace) {
    return Promise.resolve({ status: 'unavailable', message: 'Set KPP_WORKSPACE to inspect an existing pinned workspace.' });
  }
  const args = ['-I', adapter, path.resolve(root), operation];
  if (operation === 'workspace' && workspace) args.push(path.resolve(workspace));
  return new Promise<Record<string, unknown>>((resolve) => {
    const child = spawn(process.env.KPP_PYTHON || 'python3', args, {
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    const unavailable = (message: string) => resolve({ status: 'unavailable', message });
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      unavailable('Native KPP timed out.');
    }, 8000);
    let output = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk: string) => {
      output += chunk;
      if (output.length > 4 * 1024 * 1024) {
        child.kill('SIGKILL');
        unavailable('Native KPP output exceeds the Studio limit.');
      }
    });
    child.stdin.on('error', () => {});
    child.on('error', () => {
      clearTimeout(timer);
      unavailable('Could not start the configured Python executable.');
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      try {
        if (code !== 0) throw new Error();
        resolve(JSON.parse(output));
      } catch {
        unavailable('Native KPP did not return an inspection result.');
      }
    });
    child.stdin.end(source, 'utf8');
  });
}
