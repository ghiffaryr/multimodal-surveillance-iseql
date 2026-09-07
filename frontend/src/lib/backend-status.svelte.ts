import { browser } from '$app/environment';

// Whether the analysis backend has responded to a health check. On HPC the
// GPU-node backend can take minutes to boot, so pages gate their data loading
// and the guided tour on this flag while +layout shows a centered wait overlay.
//
// This must be self-recovering: the flag is reset on every mount, re-checked
// immediately whenever the tab regains focus (or is restored from the
// back/forward cache), and polled on a relaxed schedule so a backend that dies
// mid-session re-shows the overlay instead of leaving a stale UI.
export const backendStatus = $state({ ready: false, attempts: 0 });

// Polling is deliberately relaxed: the tab-wake recheck below is what keeps
// the UI responsive, so the background loop only needs to catch mid-session
// death. Per client this is ~6 req/min while down, ~2 req/min while up.
const DOWN_MS = 10000;
const UP_MS = 30000;
// Per-request timeout. Fails fast on hung connections (e.g. dead tunnel) so
// the overlay can appear; the next cycle corrects any premature negative.
const ABORT_MS = 8000;
// Minimum gap between wake-triggered rechecks (prevents fetch storms on
// rapid tab switching).
const WAKE_DEBOUNCE_MS = 3000;
// If no check has completed within this window, the timer chain is assumed
// starved (background-tab throttling) and is torn down + restarted.
const STALE_MS = 2 * UP_MS;

let stopped = false;
let polling = false;
let timer: ReturnType<typeof setTimeout> | null = null;
let listenersBound = false;
let lastCompletedAt = 0;
let lastWakeAt = 0;

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

function bindListeners() {
  if (!browser || listenersBound) return;
  listenersBound = true;
  const onWake = () => {
    if (document.visibilityState === 'visible') wakeRecheck();
  };
  document.addEventListener('visibilitychange', onWake);
  window.addEventListener('focus', wakeRecheck);
  window.addEventListener('online', wakeRecheck);
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) startBackendHealthCheck();
  });
}

function wakeRecheck() {
  if (!browser || stopped) return;
  const now = Date.now();
  if (now - lastWakeAt < WAKE_DEBOUNCE_MS) return;
  lastWakeAt = now;
  if (now - lastCompletedAt > STALE_MS) {
    // Timer chain starved while hidden: restart it instead of trusting it.
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    polling = false;
    startBackendHealthCheck();
    return;
  }
  void checkOnce().then((ok) => {
    lastCompletedAt = Date.now();
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
  lastCompletedAt = Date.now();
  if (stopped) {
    polling = false;
    return;
  }
  backendStatus.ready = ok;
  timer = setTimeout(() => void runCheck(), ok ? UP_MS : DOWN_MS);
}

async function checkOnce(): Promise<boolean> {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), ABORT_MS);
  try {
    const res = await fetch('/api/health', { signal: ctrl.signal, cache: 'no-store' });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}
