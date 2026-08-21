<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import Button from '$lib/components/ui/button.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import type { Condition } from '$lib/types';
  import { inputStr } from '$lib/dom-helpers';

  type Props = {
    condition: Condition;
    initialId?: string | null;
    mode?: 'new' | 'open';
    onBack?: () => void;
    onSaved?: (id: string) => void;
  };
  let { condition, initialId = null, mode = 'open', onBack = () => undefined, onSaved = () => undefined }: Props = $props();

  let eventId = $state('');
  let query = $state('');
  let sql = $state('');
  let error = $state<string | null>(null);
  let status = $state<string | null>(null);
  let loadedId = $state<string | null>(null);
  let taRef = $state<HTMLTextAreaElement | null>(null);

  const TEMPLATE = `π_{M1.arg1, M2.arg1, M1.sf, M2.ef} (
  σ_{M1.arg1=M2.arg1} (
    σ_{pred="running" ∧ arg1="person"}(M1)
    Bef(δ:10; ζ:<=, ρ:0)
    σ_{pred="enter_or_exit_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}(M2)))`;

  const SYMBOLS = ['π', 'σ', '∪', '\\', '∩', '∧', '∨', '≠', '≤', '≥', '<', '>', 'δ', 'ε', 'ζ', 'η', 'ρ', '∞'];

  function errorReason(e: unknown): string {
    const body = (e as { body?: unknown })?.body;
    if (body && typeof body === 'object' && 'detail' in body) {
      return String((body as { detail: unknown }).detail);
    }
    return (e as Error).message;
  }

  async function loadEvent() {
    if (!initialId) return;
    try {
      const resp = await api.get<{ model_json: string | null }>(`/api/events/${initialId}?condition=${condition}`);
      eventId = initialId;
      loadedId = initialId;
      let prefilled = '';
      if (resp.model_json) {
        try {
          const m = JSON.parse(resp.model_json);
          prefilled = m.iseql_text || '';
          if (!prefilled && m.intervals?.length) {
            const p = await api.postJson<{ iseql: string }>('/api/iseql/preview', { model: m });
            prefilled = p.iseql || '';
          }
        } catch { /* ignore */ }
      }
      query = prefilled || TEMPLATE;
    } catch (e) {
      error = `Failed to load event: ${(e as Error).message}`;
    }
  }

  onMount(() => {
    if (initialId && mode === 'open') {
      loadEvent();
    } else {
      eventId = '';
      query = TEMPLATE;
    }
  });

  function insertText(text: string) {
    const ta = taRef;
    if (!ta) { query = query + text; return; }
    const start = ta.selectionStart ?? query.length;
    const end = ta.selectionEnd ?? query.length;
    query = query.slice(0, start) + text + query.slice(end);
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(start + text.length, start + text.length);
    });
  }

  async function refresh() {
    if (!query.trim()) { sql = ''; error = null; return; }
    try {
      const resp = await api.postJson<{ sql: string; iseql: string }>('/api/iseql/compile', {
        query,
        name: eventId.trim() || 'event',
      });
      sql = resp.sql;
      error = null;
    } catch (err) {
      sql = '';
      error = errorReason(err);
    }
  }
  let timer: ReturnType<typeof setTimeout> | null = null;
  $effect(() => {
    void query;
    void eventId;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { refresh(); }, 400);
  });

  async function save() {
    error = null;
    status = null;
    if (!eventId.trim()) { error = 'Event ID is required.'; return; }
    let model: Record<string, unknown>;
    try {
      const resp = await api.postJson<{ model: Record<string, unknown> }>('/api/iseql/compile', {
        query,
        name: eventId.trim(),
      });
      model = resp.model;
    } catch (e) {
      error = `Query does not compile: ${errorReason(e)}`;
      return;
    }
    try {
      const updating = loadedId && loadedId === eventId.trim();
      if (updating) {
        await api.putJson(`/api/events/${eventId.trim()}`, {
          condition, model_json: JSON.stringify(model),
        });
      } else {
        await api.postJson('/api/events', {
          id: eventId.trim(), condition,
          model_json: JSON.stringify(model),
        });
      }
      loadedId = eventId.trim();
      status = updating ? `Updated event '${eventId.trim()}'.` : `Created event '${eventId.trim()}'.`;
      onSaved(eventId.trim());
    } catch (e) {
      error = `Failed to save event: ${(e as Error).message}`;
    }
  }

  const textareaClass =
    'h-full w-full resize-none rounded-md border border-input bg-background p-2 font-mono text-xs leading-relaxed ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
</script>

<div class="flex h-full flex-col gap-2">
  <div class="flex flex-wrap items-center gap-2 rounded-md border p-2">
    <Button type="button" size="icon" variant="ghost" class="h-8 w-8" title="Back to events" onclick={onBack}>⌂</Button>
    <Input class="w-48 font-mono" placeholder="event_name" value={eventId} onchange={(e) => (eventId = inputStr(e))} />
    <div class="flex-1"></div>
    <Button type="button" variant="secondary" onclick={save}>Save event</Button>
    <Button type="button" variant="ghost" onclick={() => { eventId = ''; query = TEMPLATE; }}>Clear</Button>
  </div>

  {#if error}<p class="text-xs text-destructive">{error}</p>{/if}
  {#if status}<p class="text-xs text-emerald-600">{status}</p>{/if}

  <div class="flex items-center gap-1 rounded-md border px-2 py-1 text-xs text-muted-foreground">
    <span class="mr-1 shrink-0">Insert:</span>
    {#each SYMBOLS as s (s)}
      <button type="button" class="rounded border px-1.5 py-0.5 font-mono hover:bg-muted" onclick={() => insertText(s)} title={`Insert ${s}`}>{s}</button>
    {/each}
    <span class="ml-2 hidden shrink-0 md:inline">
      π projection · σ selection · ∪/∖/∩ set ops · ∧/∨ and/or · operators SP EF Bef Aft DJ RDJ LOJ ROJ with δ/ε/ζ/η/ρ
    </span>
  </div>

  <p class="rounded-md border border-muted bg-muted/30 px-2 py-1 text-xs text-muted-foreground">
    In the projection, use <code class="font-mono text-foreground">st</code>/<code class="font-mono text-foreground">et</code> to operate in
    <strong class="text-foreground">time</strong> (δ/ε in <strong class="text-foreground">seconds</strong>), or
    <code class="font-mono text-foreground">sf</code>/<code class="font-mono text-foreground">ef</code> to operate in
    <strong class="text-foreground">frames</strong>. Mixing <code>st</code>/<code>et</code> with <code>sf</code>/<code>ef</code> is not allowed.
  </p>

  <div class="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-2">
    <div class="flex min-h-0 flex-col rounded-md border">
      <div class="border-b px-2 py-1 text-sm font-semibold">ISEQL Query</div>
      <div class="min-h-0 flex-1 p-2">
        <textarea
          bind:this={taRef}
          class={textareaClass}
          spellcheck="false"
          value={query}
          oninput={(e) => (query = (e.currentTarget as HTMLTextAreaElement).value)}
        ></textarea>
      </div>
    </div>
    <div class="flex min-h-0 flex-col rounded-md border">
      <div class="border-b px-2 py-1 text-sm font-semibold">SQL</div>
      <pre class="min-h-0 flex-1 overflow-auto p-2 font-mono text-xs leading-relaxed">{sql || '-- compile to see the SQL conversion'}</pre>
    </div>
  </div>
</div>
