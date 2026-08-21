<script lang="ts">
  import Card from '$lib/components/ui/card.svelte';
  import CardHeader from '$lib/components/ui/card-header.svelte';
  import CardTitle from '$lib/components/ui/card-title.svelte';
  import CardContent from '$lib/components/ui/card-content.svelte';
  import Badge from '$lib/components/ui/badge.svelte';
  import UnitToggle from '$lib/components/unit-toggle.svelte';
  import { DatabaseZap } from 'lucide-svelte';
  import { cn } from '$lib/utils';
  import type { DetectionResult, Unit } from '$lib/types';

  type Props = {
    result: DetectionResult | null;
    running?: boolean;
    error?: string | null;
    unit: Unit;
    onUnitChange: (u: Unit) => void;
    onMemory?: () => void;
  };
  let { result, running = false, error = null, unit, onUnitChange, onMemory }: Props = $props();

  const cols = $derived(
    result && result.rows.length > 0
      ? Object.keys(result.rows[0])
          .filter((k) => !k.startsWith('__p'))
          .filter((k) =>
            unit === 'seconds'
              ? !k.endsWith('_sf') && !k.endsWith('_ef')
              : !k.endsWith('.st') && !k.endsWith('.et')
          )
          .map((k) => ({ label: k.replace(/^M(\d+)_/, 'M$1.'), key: k }))
      : []
  );
</script>

<Card class="flex h-full min-h-0 flex-col">
  <CardHeader class="flex flex-row items-center justify-between">
    <CardTitle>Results</CardTitle>
    <div class="flex items-center gap-2">
      {#if onMemory}
        <button
          type="button"
          title="View object memory"
          class="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          onclick={onMemory}
        >
          <DatabaseZap class="size-3.5" /> Object memory
        </button>
      {/if}
      <UnitToggle {unit} {onUnitChange} secondsLabel="Time" />
      {#if result}
        <Badge variant="outline">{result.rows.length} row(s)</Badge>
      {/if}
    </div>
  </CardHeader>
  <CardContent class="min-h-0 flex-1 overflow-y-auto">
    {#if running}
      <p class="text-sm text-muted-foreground">Running detection...</p>
    {:else if error}
      <p class="text-sm text-destructive">{error}</p>
    {:else if !result}
      <p class="text-sm text-muted-foreground">
        Start or load an analysis to see results.
      </p>
    {:else if result.rows.length === 0}
      <p class="text-sm text-muted-foreground">No events detected.</p>
    {:else}
      <div class="overflow-x-auto">
        <table class={cn('w-full text-left text-sm')}>
          <thead class="border-b border-border text-xs uppercase text-muted-foreground">
            <tr>
              {#each cols as c (c.key)}
                <th class="px-2 py-2 font-medium">{c.label}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each result.rows as row, i (i)}
              <tr class="border-b border-border/50 last:border-0">
                {#each cols as c (c.key)}
                  <td class="px-2 py-1.5">
                    {#if typeof row[c.key] === 'object' && row[c.key] !== null}
                      <code class="text-xs">{JSON.stringify(row[c.key])}</code>
                    {:else}
                      <span>{row[c.key]}</span>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </CardContent>
</Card>
