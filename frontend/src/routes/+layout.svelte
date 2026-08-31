<script lang="ts">
  import '../app.css';
  import { ModeWatcher } from 'mode-watcher';
  import { CircleHelp } from 'lucide-svelte';
  import TourOverlay from '$lib/components/tour-overlay.svelte';
  import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
  import { restartTour } from '$lib/tour.svelte';
  let { children } = $props();
</script>

<ModeWatcher defaultMode="dark" />
{@render children?.()}
<TourOverlay />
<ConfirmDialog />
<button
  type="button"
  title="Guided tour"
  aria-label="Start guided tour"
  class="fixed bottom-4 right-4 z-[90] flex size-10 items-center justify-center rounded-full border bg-popover text-popover-foreground shadow-lg transition-colors hover:bg-accent"
  onclick={restartTour}
>
  <CircleHelp class="size-5" />
</button>
