<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';
  import { ModeWatcher } from 'mode-watcher';
  import { CircleHelp } from 'lucide-svelte';
  import TourOverlay from '$lib/components/tour-overlay.svelte';
  import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
  import { restartTour } from '$lib/tour.svelte';
  let { children } = $props();

  const SIZE = 40;
  const MARGIN = 12;
  let pos = $state({ x: 0, y: 0 });
  let dragging = $state(false);
  let moved = $state(false);
  let offset = $state({ x: 0, y: 0 });

  onMount(() => {
    pos = { x: window.innerWidth - MARGIN - SIZE, y: window.innerHeight - MARGIN - SIZE };
  });

  function onPointerDown(e: PointerEvent) {
    dragging = true;
    moved = false;
    offset = { x: e.clientX - pos.x, y: e.clientY - pos.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragging) return;
    const nx = e.clientX - offset.x;
    const ny = e.clientY - offset.y;
    if (Math.abs(nx - pos.x) > 3 || Math.abs(ny - pos.y) > 3) moved = true;
    pos = {
      x: Math.max(MARGIN, Math.min(nx, window.innerWidth - MARGIN - SIZE)),
      y: Math.max(MARGIN, Math.min(ny, window.innerHeight - MARGIN - SIZE)),
    };
  }

  function onPointerUp() {
    dragging = false;
  }

  function onClick() {
    if (moved) return;
    restartTour();
  }
</script>

<ModeWatcher defaultMode="dark" />
{@render children?.()}
<TourOverlay />
<ConfirmDialog />
<button
  type="button"
  title="Guided tour (drag to move)"
  aria-label="Start guided tour"
  class={['fixed z-[90] flex size-10 items-center justify-center rounded-full border bg-popover text-popover-foreground shadow-lg transition-colors hover:bg-accent', dragging ? 'cursor-grabbing' : 'cursor-grab touch-none'].join(' ')}
  style="left: {pos.x}px; top: {pos.y}px;"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
  onclick={onClick}
>
  <CircleHelp class="size-5" />
</button>
