import { browser } from '$app/environment';

// Whether the analysis backend has responded to a health check. On HPC the
// GPU-node backend can take minutes to boot, so pages gate their data loading
// and the guided tour on this flag while +layout shows a centered wait overlay.
//
// This must be self-recovering: the flag is reset on every mount, re-checked
// whenever the tab regains visibility (or is restored from the back/forward
// cache), and polled continuously so a backend that dies mid-session re-shows
// the overlay instead of leaving a stale UI.
export const backendStatus = $state({ ready: false, attempts: 0 });

const FAST_MS = 4000;
const SLOW_MS = 15000;

let stopped = false;
let polling = false;
let timer: ReturnType<typeof setTimeout> | null = null;
let listenersBound = false;

export function startBackendHealthCheck() {
  if (!browser) return;
  stopped = false;
  backendStatus.ready = false;
  bindListeners();
  if (polling) return;
  polling = true;
  void runCheck();
}

export function stopBackendHealthCheck() {
  stopped = true;
  polling = false;
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

export function markBackendDown() {
  backendStatus.ready = false;
  startBackendHealthCheck();
}

export function markBackendUp() {
  backendStatus.ready = true;
}

function bindListeners() {
  if (!browser || listenersBound) return;
  listenersBound = true;
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') recheckNow();
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) startBackendHealthCheck();
  });
}

function recheckNow() {
  if (!browser || stopped) return;
  void checkOnce().then((ok) => {
    if (!stopped) backendStatus.ready = ok;
  });
}

async function runCheck() {
  if (stopped) {
    polling = false;
    return;
  }
  backendStatus.attempts += 1;
  const ok = await checkOnce();
  if (stopped) {
    polling = false;
    return;
  }
  backendStatus.ready = ok;
  timer = setTimeout(() => void runCheck(), ok ? SLOW_MS : FAST_MS);
}

async function checkOnce(): Promise<boolean> {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch('/api/health', { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}
