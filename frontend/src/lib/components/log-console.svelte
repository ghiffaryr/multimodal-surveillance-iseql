<script lang="ts">
  import { Trash2, Terminal } from 'lucide-svelte';
  import Button from '$lib/components/ui/button.svelte';
  import type { LogEvent } from '$lib/types';

  type Props = { entries: LogEvent[]; onClear: () => void };
  let { entries, onClear }: Props = $props();

  let logContainer: HTMLDivElement | undefined = $state();

  $effect(() => {
    entries;
    if (logContainer) {
      requestAnimationFrame(() => {
        logContainer!.scrollTop = logContainer!.scrollHeight;
      });
    }
  });

  function fmtTs(ts: number): string {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-GB', { hour12: false });
  }
  function stageClass(s: string) {
    if (s === 'done')  return 'text-emerald-400';
    if (s === 'failed') return 'text-red-400';
    if (s.startsWith('vlm')) return 'text-sky-400';
    if (s.startsWith('interval')) return 'text-violet-400';
    if (s.startsWith('sound')) return 'text-amber-400';
    if (s.startsWith('detection')) return 'text-pink-400';
    return 'text-slate-300';
  }
</script>

<div class="flex h-full min-h-0 flex-col rounded-lg border border-border bg-card">
  <div class="flex items-center justify-between border-b border-border px-4 py-2">
    <div class="flex items-center gap-2 text-sm font-medium">
      <Terminal class="size-4" />
      <span>Log Console</span>
      <span class="text-xs text-muted-foreground">({entries.length} entries)</span>
    </div>
    <Button size="sm" variant="ghost" onclick={onClear} disabled={entries.length === 0}>
      <Trash2 /> Clear
    </Button>
  </div>
  <div bind:this={logContainer} class="flex-1 overflow-y-auto p-3 font-mono text-xs">
    {#if entries.length === 0}
      <p class="text-muted-foreground">No log entries yet. Start an analysis to see output.</p>
    {:else}
      {#each entries as entry, i (i)}
        <div class="flex gap-2 py-0.5">
          <span class="text-muted-foreground">{fmtTs(entry.ts)}</span>
          <span class={stageClass(entry.stage)}>[{entry.stage}]</span>
          <span class="text-foreground/90 break-all">{entry.message}</span>
        </div>
      {/each}
    {/if}
  </div>
</div>
