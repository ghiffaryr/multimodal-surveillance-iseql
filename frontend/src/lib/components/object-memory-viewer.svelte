<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { ObjectMemoryResponse, ObjectMemoryStats } from '$lib/types';
  import Button from '$lib/components/ui/button.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import Badge from '$lib/components/ui/badge.svelte';
  import { DatabaseZap, Search } from 'lucide-svelte';

  type Props = {
    analysisId: string;
  };
  let { analysisId }: Props = $props();

  let stats = $state<ObjectMemoryStats | null>(null);
  let mem = $state<ObjectMemoryResponse>({ items: [], count: 0, total: 0 });
  let error = $state<string | null>(null);
  let loading = $state(false);

  let limit = $state(200);
  let offset = $state(0);
  let classFilter = $state('');
  let frameMin = $state<number | null>(null);
  let frameMax = $state<number | null>(null);

  const CLASS_COLORS: Record<string, string> = {
    person: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
    vehicle: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    object: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  };

  function buildQuery(): string {
    const parts: string[] = [`limit=${limit}`, `offset=${offset}`];
    if (classFilter) parts.push(`class_name=${encodeURIComponent(classFilter)}`);
    if (frameMin != null && !Number.isNaN(frameMin)) parts.push(`frame_min=${frameMin}`);
    if (frameMax != null && !Number.isNaN(frameMax)) parts.push(`frame_max=${frameMax}`);
    return parts.join('&');
  }

  async function load(): Promise<void> {
    if (!analysisId) return;
    loading = true;
    error = null;
    try {
      const [s, m] = await Promise.all([
        api.get<ObjectMemoryStats>(`/api/analysis/${analysisId}/memory/stats`),
        api.get<ObjectMemoryResponse>(`/api/analysis/${analysisId}/memory/objects?${buildQuery()}`),
      ]);
      stats = s;
      mem = m;
    } catch (e) {
      error = (e as Error).message;
      stats = null;
      mem = { items: [], count: 0, total: 0 };
    } finally {
      loading = false;
    }
  }

  function resetFilters() {
    classFilter = '';
    frameMin = null;
    frameMax = null;
    limit = 200;
    offset = 0;
  }

  onMount(load);

  $effect(() => {
    if (analysisId) load();
  });
</script>

<div class="flex h-full min-h-0 flex-col gap-3">
  {#if error}
    <div class="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
  {/if}

  {#if !error && analysisId}
    <section class="flex flex-wrap items-center gap-2">
      <Badge variant="secondary"><DatabaseZap class="size-3 mr-1" />{stats?.total ?? 0} stored object detections</Badge>
      {#if stats?.frame_min != null}
        <Badge variant="secondary">frames {stats.frame_min}–{stats.frame_max}</Badge>
      {/if}
      {#if stats?.per_class}
        {#each Object.entries(stats.per_class) as [cls, n] (cls)}
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs {CLASS_COLORS[cls] || 'bg-muted text-muted-foreground'}"
            class:border-primary={classFilter === cls}
            class:ring-2={classFilter === cls}
            onclick={() => { classFilter = classFilter === cls ? '' : cls; load(); }}>
            {cls} · {n}
          </button>
        {/each}
      {/if}
    </section>

    <section class="flex flex-wrap items-end gap-3 rounded-md border p-3">
      <Field>
        <Label>Class</Label>
        <Input type="text" value={classFilter} placeholder="person / vehicle / object"
          oninput={(e) => (classFilter = (e.currentTarget as HTMLInputElement).value)} />
      </Field>
      <Field>
        <Label>Frame min</Label>
        <Input type="number" min="0" value={frameMin ?? ''}
          oninput={(e) => (frameMin = (e.currentTarget as HTMLInputElement).value === '' ? null : Number((e.currentTarget as HTMLInputElement).value))} />
      </Field>
      <Field>
        <Label>Frame max</Label>
        <Input type="number" min="0" value={frameMax ?? ''}
          oninput={(e) => (frameMax = (e.currentTarget as HTMLInputElement).value === '' ? null : Number((e.currentTarget as HTMLInputElement).value))} />
      </Field>
      <Field>
        <Label>Rows</Label>
        <Input type="number" min="1" max="1000" value={limit}
          oninput={(e) => (limit = Number((e.currentTarget as HTMLInputElement).value) || 200)} />
      </Field>
      <Button variant="secondary" size="sm" onclick={() => { offset = 0; load(); }}><Search class="size-3 mr-1" /> Apply</Button>
      {#if classFilter || frameMin != null || frameMax != null}
        <Button variant="ghost" size="sm" onclick={() => { resetFilters(); load(); }}>Reset</Button>
      {/if}
    </section>

    <section class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border">
      <div class="min-h-0 flex-1 overflow-auto">
        <table class="w-full text-left text-xs">
          <thead class="sticky top-0 bg-card text-muted-foreground">
            <tr class="border-b">
              <th class="px-3 py-2 font-medium">Frame</th>
              <th class="px-3 py-2 font-medium">Object ID</th>
              <th class="px-3 py-2 font-medium">Class</th>
              <th class="px-3 py-2 font-medium">Blocks</th>
              <th class="px-3 py-2 font-medium">Description</th>
              <th class="px-3 py-2 font-medium">Document</th>
            </tr>
          </thead>
          <tbody>
            {#each mem.items as entry}
              <tr class="border-b last:border-0 hover:bg-muted/40">
                <td class="px-3 py-1.5 font-mono tabular-nums">{entry.frame}</td>
                <td class="px-3 py-1.5 font-mono tabular-nums">{entry.id}</td>
                <td class="px-3 py-1.5">
                  <span class="rounded border px-1.5 py-px text-[10px] font-medium {CLASS_COLORS[entry.class] || 'bg-muted text-muted-foreground'}">
                    {entry.class}
                  </span>
                </td>
                <td class="px-3 py-1.5 font-mono">{entry.blocks.length ? entry.blocks.join(',') : '-'}</td>
                <td class="px-3 py-1.5 max-w-xs truncate" title={entry.description}>{entry.description || '-'}</td>
                <td class="px-3 py-1.5 max-w-sm truncate" title={entry.document}>{entry.document}</td>
              </tr>
            {:else}
              <tr>
                <td colspan="6" class="px-3 py-6 text-center text-muted-foreground">
                  {loading ? 'Loading…' : 'No stored objects for this analysis.'}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <footer class="flex items-center justify-between text-xs text-muted-foreground">
      <span>{mem.count} of {mem.total} shown</span>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" disabled={offset <= 0} onclick={() => { offset = Math.max(0, offset - limit); load(); }}>
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={offset + mem.count >= mem.total} onclick={() => { offset += mem.count; load(); }}>
          Next
        </Button>
      </div>
    </footer>
  {/if}
</div>
