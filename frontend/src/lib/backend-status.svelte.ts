import { browser } from '$app/environment';

// Whether the analysis backend has responded to a health check. On HPC the
// GPU-node backend can take minutes to boot, so pages gate their data loading
// and the guided tour on this flag while +layout shows a centered wait overlay.
export const backendStatus = $state({ ready: false, attempts: 0 });

let stopped = false;

export function startBackendHealthCheck() {
  if (!browser || backendStatus.ready) return;
  stopped = false;
  void poll();
}

export function stopBackendHealthCheck() {
  stopped = true;
}

async function poll() {
  while (!stopped && !backendStatus.ready) {
    backendStatus.attempts += 1;
    if (await checkOnce()) {
      backendStatus.ready = true;
      return;
    }
    await new Promise((r) => setTimeout(r, 4000));
  }
}

async function checkOnce(): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch('/api/health', { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
