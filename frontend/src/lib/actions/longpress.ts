type LongpressOptions = {
  onLongPress: (e: PointerEvent) => void;
  delay?: number;
  threshold?: number;
};

/**
 * Touch equivalent of right-click: fires `onLongPress` after the pointer has
 * been held without moving for `delay` ms. Mouse input is ignored so desktop
 * right-click keeps working. The click that follows the long-press on touch is
 * swallowed so an already-open menu isn't immediately closed again.
 */
export function longpress(node: HTMLElement, options: LongpressOptions) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let startX = 0;
  let startY = 0;
  let active = false;
  let fired = false;

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function reset() {
    clearTimer();
    active = false;
    fired = false;
  }

  function swallowNextClick() {
    const stop = (e: Event) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      cleanup();
    };
    const cleanup = () => {
      document.removeEventListener('click', stop, true);
      clearTimeout(fallback);
    };
    const fallback = setTimeout(cleanup, 800);
    document.addEventListener('click', stop, true);
  }

  function trigger() {
    if (fired) return;
    fired = true;
    swallowNextClick();
  }

  function onDown(e: PointerEvent) {
    if (e.pointerType === 'mouse') return;
    active = true;
    fired = false;
    startX = e.clientX;
    startY = e.clientY;
    clearTimer();
    timer = setTimeout(() => {
      timer = null;
      trigger();
      options.onLongPress(e);
    }, options.delay ?? 500);
  }

  function onMove(e: PointerEvent) {
    if (!active) return;
    if (Math.hypot(e.clientX - startX, e.clientY - startY) > (options.threshold ?? 10)) {
      reset();
    }
  }

  function onUp() {
    reset();
  }

  function onContextMenu() {
    // Android fires a native contextmenu after a long-press; swallow the
    // follow-up click even if our own timer has not fired yet.
    if (active) trigger();
  }

  node.addEventListener('pointerdown', onDown);
  node.addEventListener('pointermove', onMove);
  node.addEventListener('pointerup', onUp);
  node.addEventListener('pointercancel', onUp);
  node.addEventListener('pointerleave', onUp);
  node.addEventListener('contextmenu', onContextMenu);

  return {
    destroy() {
      reset();
      node.removeEventListener('pointerdown', onDown);
      node.removeEventListener('pointermove', onMove);
      node.removeEventListener('pointerup', onUp);
      node.removeEventListener('pointercancel', onUp);
      node.removeEventListener('pointerleave', onUp);
      node.removeEventListener('contextmenu', onContextMenu);
    },
  };
}
