<script lang="ts">
  import Card from '$lib/components/ui/card.svelte';
  import CardHeader from '$lib/components/ui/card-header.svelte';
  import CardTitle from '$lib/components/ui/card-title.svelte';
  import CardContent from '$lib/components/ui/card-content.svelte';
  import Badge from '$lib/components/ui/badge.svelte';
  import { cn } from '$lib/utils';
  import type { DetectionResult } from '$lib/types';

  type Props = {
    result: DetectionResult | null;
    running?: boolean;
    error?: string | null;
  };
  let { result, running = false, error = null }: Props = $props();

  const cols = $derived(result && result.rows.length > 0 ? Object.keys(result.rows[0]) : []);
</script>

<Card class="flex h-full min-h-0 flex-col">
  <CardHeader class="flex flex-row items-center justify-between">
    <CardTitle>Detection Results</CardTitle>
    {#if result}
      <Badge variant="outline">{result.rows.length} row(s)</Badge>
    {/if}
  </CardHeader>
  <CardContent class="min-h-0 flex-1 overflow-y-auto">
    {#if running}
      <p class="text-sm text-muted-foreground">Running detection…</p>
    {:else if error}
      <p class="text-sm text-destructive">{error}</p>
    {:else if !result}
      <p class="text-sm text-muted-foreground">
        Pick an event and click <span class="font-mono">Run Detection</span>.
      </p>
    {:else if result.rows.length === 0}
      <p class="text-sm text-muted-foreground">No matches for this event with the current deltas.</p>
    {:else}
      <div class="overflow-x-auto">
        <table class={cn('w-full text-left text-sm')}>
          <thead class="border-b border-border text-xs uppercase text-muted-foreground">
            <tr>
              {#each cols as c (c)}
                <th class="px-2 py-2 font-medium">{c}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each result.rows as row, i (i)}
              <tr class="border-b border-border/50 last:border-0">
                {#each cols as c (c)}
                  <td class="px-2 py-1.5">
                    {#if typeof row[c] === 'object' && row[c] !== null}
                      <code class="text-xs">{JSON.stringify(row[c])}</code>
                    {:else}
                      <span>{row[c]}</span>
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
