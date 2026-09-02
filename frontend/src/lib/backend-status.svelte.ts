import { browser } from '$app/environment';

// Whether the analysis backend has responded to a health check. On HPC the
// GPU-node backend can take minutes to boot, so pages gate their data loading
// and the guided tour on this flag while +layout shows a centered wait overlay.
//
// This must be self-recovering: the flag is reset on every mount and whenever a
// real data call fails, so a restored tab (bfcache/client-side state) or a
// backend that died mid-session re-shows the overlay instead of an error banner.
export const backendStatus = $state({ ready: false, attempts: 0 });

let stopped = false;
let polling = false;

export function startBackendHealthCheck() {
  if (!browser) return;
  stopped = false;
  backendStatus.ready = false;
  if (polling) return;
  polling = true;
  void poll();
}

export function stopBackendHealthCheck() {
  stopped = true;
  polling = false;
}

export function markBackendDown() {
  backendStatus.ready = false;
  startBackendHealthCheck();
}

export function markBackendUp() {
  backendStatus.ready = true;
  stopped = true;
  polling = false;
}

async function poll() {
  while (!stopped && !backendStatus.ready) {
    backendStatus.attempts += 1;
    if (await checkOnce()) {
      backendStatus.ready = true;
      polling = false;
      return;
    }
    await new Promise((r) => setTimeout(r, 4000));
  }
  polling = false;
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
