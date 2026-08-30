<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { api } from '$lib/api';
  import Button from '$lib/components/ui/button.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import IseqlTimeline from '$lib/components/iseql-timeline.svelte';
  import { normalizeModel, type IseqlModel, type Vocabulary } from '$lib/iseql-model';
  import type { Condition } from '$lib/types';
  import { inputStr } from '$lib/dom-helpers';

  type Props = {
    condition: Condition;
    initialId?: string | null;
    mode?: 'new' | 'open';
    onBack?: () => void;
    onSaved?: (id: string) => void;
    onOpenPredicate?: (name: string, modality: 'visual' | 'audio') => void;
  };
  let { condition, initialId = null, mode = 'open', onBack = () => undefined, onSaved = () => undefined, onOpenPredicate = () => undefined }: Props = $props();

  let view = $state<'text' | 'timeline'>('text');
  let eventId = $state('');
  let loadedId = $state<string | null>(null);
  let error = $state<string | null>(null);
  let status = $state<string | null>(null);

  let model = $state<IseqlModel | null>(null);
  let text = $state('');
  let sql = $state('');
  let vocabulary = $state<Vocabulary>({ predicates: [], participant_classes: [] });
  let taRef = $state<HTMLTextAreaElement | null>(null);

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
      let m: IseqlModel | null = null;
      if (resp.model_json) {
        try {
          m = normalizeModel(JSON.parse(resp.model_json));
        } catch { /* ignore */ }
      }
      model = m;
      let prefilled = (m as { iseql_text?: string } | null)?.iseql_text ?? '';
      if (!prefilled && m?.intervals?.length) {
        try {
          const p = await api.postJson<{ iseql: string }>('/api/iseql/preview', { model: m });
          prefilled = p.iseql || '';
        } catch { /* ignore */ }
      }
      text = prefilled || '';
    } catch (e) {
      error = `Failed to load event: ${(e as Error).message}`;
    }
  }

  onMount(async () => {
    try {
      vocabulary = await api.get<Vocabulary>('/api/iseql/vocabulary');
    } catch (e) {
      error = `Failed to load vocabulary: ${(e as Error).message}`;
    }
    if (initialId && mode === 'open') {
      await loadEvent();
      if (model) scheduleModelCompile();
    } else {
      eventId = '';
      model = null;
      text = '';
      sql = '';
    }
  });

  onMount(() => {
    if (!browser) return;
    const mq = window.matchMedia('(max-width: 639px)');
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) view = 'text';
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  });

  // -------------------------------------------------------------------------
  // text <-> model synchronization
  // -------------------------------------------------------------------------

  function onTextInput(e: Event) {
    text = (e.currentTarget as HTMLTextAreaElement).value;
    scheduleTextCompile();
  }

  let textTimer: ReturnType<typeof setTimeout> | null = null;
  function scheduleTextCompile() {
    if (textTimer) clearTimeout(textTimer);
    textTimer = setTimeout(async () => {
      if (!text.trim()) { sql = ''; return; }
      try {
        const resp = await api.postJson<{ model: IseqlModel; sql: string }>('/api/iseql/compile', {
          query: text,
          name: eventId.trim() || 'event',
        });
        model = normalizeModel(resp.model);
        sql = resp.sql;
        error = null;
      } catch (e) {
        sql = '';
        error = errorReason(e);
      }
    }, 400);
  }

  function onModelChange(m: IseqlModel) {
    model = m;
    scheduleModelCompile();
  }

  let modelTimer: ReturnType<typeof setTimeout> | null = null;
  function scheduleModelCompile() {
    if (modelTimer) clearTimeout(modelTimer);
    modelTimer = setTimeout(async () => {
      if (!model || !model.intervals?.length) { sql = ''; return; }
      try {
        const resp = await api.postJson<{ iseql: string; sql: string }>('/api/iseql/model/compile', { model });
        text = resp.iseql;
        sql = resp.sql;
        error = null;
      } catch (e) {
        error = errorReason(e);
      }
    }, 300);
  }

  // -------------------------------------------------------------------------
  // save
  // -------------------------------------------------------------------------

  async function save() {
    error = null;
    status = null;
    if (!eventId.trim()) { error = 'Event ID is required.'; return; }
    let m = model;
    if (!m) {
      try {
        const resp = await api.postJson<{ model: IseqlModel }>('/api/iseql/compile', {
          query: text,
          name: eventId.trim(),
        });
        m = resp.model;
      } catch (e) {
        error = `Query does not compile: ${errorReason(e)}`;
        return;
      }
    }
    let iseqlText = (m as { iseql_text?: string }).iseql_text ?? '';
    if (!iseqlText) {
      try {
        const p = await api.postJson<{ iseql: string }>('/api/iseql/preview', { model: m });
        iseqlText = p.iseql || '';
      } catch { /* keep empty */ }
    }
    const full = { ...m, iseql_text: iseqlText };
    try {
      const updating = loadedId && loadedId === eventId.trim();
      if (updating) {
        await api.putJson(`/api/events/${eventId.trim()}`, {
          condition, model_json: JSON.stringify(full),
        });
      } else {
        await api.postJson('/api/events', {
          id: eventId.trim(), condition, model_json: JSON.stringify(full),
        });
      }
      loadedId = eventId.trim();
      status = updating ? `Updated event '${eventId.trim()}'.` : `Created event '${eventId.trim()}'.`;
      onSaved(eventId.trim());
    } catch (e) {
      error = `Failed to save event: ${(e as Error).message}`;
    }
  }

  function clear() {
    eventId = '';
    model = null;
    text = '';
    sql = '';
    error = null;
    status = null;
  }

  function insertText(s: string) {
    const ta = taRef;
    if (!ta) { text = text + s; scheduleTextCompile(); return; }
    const start = ta.selectionStart ?? text.length;
    const end = ta.selectionEnd ?? text.length;
    text = text.slice(0, start) + s + text.slice(end);
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(start + s.length, start + s.length);
    });
    scheduleTextCompile();
  }

  function setView(v: 'text' | 'timeline') {
    view = v;
    if (v === 'text' && model) scheduleModelCompile();
  }

  const textareaClass =
    'h-full w-full resize-none rounded-md border border-input bg-background p-2 font-mono text-xs leading-relaxed ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
</script>

<div class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
  <div class="flex shrink-0 flex-wrap items-center gap-2 rounded-md border p-2">
    <Button type="button" size="icon" variant="ghost" class="h-8 w-8" title="Back to events" onclick={onBack}>⌂</Button>
    <Input class="w-48 font-mono" placeholder="event_name" value={eventId} onchange={(e) => (eventId = inputStr(e))} />

    <div class="hidden items-center gap-1 rounded-md border px-1 py-0.5 text-xs sm:flex">
      <button
        type="button"
        class={['rounded px-2 py-0.5', view === 'text' ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/40'].join(' ')}
        onclick={() => setView('text')}
      >Text</button>
      <button
        type="button"
        class={['rounded px-2 py-0.5', view === 'timeline' ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/40'].join(' ')}
        onclick={() => setView('timeline')}
      >Timeline</button>
    </div>

    <div class="flex-1"></div>
    <Button type="button" variant="secondary" onclick={save}>Save event</Button>
    <Button type="button" variant="ghost" onclick={clear}>Clear</Button>
  </div>

  {#if error}<p class="text-xs text-destructive">{error}</p>{/if}
  {#if status}<p class="text-xs text-emerald-600">{status}</p>{/if}

  {#if view === 'timeline'}
    <IseqlTimeline
      {condition}
      {model}
      {vocabulary}
      eventName={eventId.trim() || 'event'}
      onChange={onModelChange}
      {onOpenPredicate}
    />
  {:else}
    <div class="flex shrink-0 items-center gap-1 overflow-x-auto rounded-md border px-2 py-1 text-xs text-muted-foreground">
      <span class="mr-1 shrink-0">Insert:</span>
      {#each SYMBOLS as s (s)}
        <button type="button" class="shrink-0 rounded border px-1.5 py-0.5 font-mono hover:bg-muted" onclick={() => insertText(s)} title={`Insert ${s}`}>{s}</button>
      {/each}
      <span class="ml-2 hidden shrink-0 md:inline">
        π projection · σ selection · ∪/∖/∩ set ops · ∧/∨ and/or · operators SP EF Bef Aft DJ RDJ LOJ ROJ with δ/ε/ζ/η/ρ
      </span>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 grid-rows-2 gap-2 lg:grid-cols-2 lg:grid-rows-1">
      <div class="flex min-h-0 flex-col rounded-md border">
        <div class="shrink-0 border-b px-2 py-1 text-sm font-semibold">ISEQL Query</div>
        <div class="min-h-0 flex-1 p-2">
          <textarea
            bind:this={taRef}
            class={textareaClass}
            spellcheck="false"
            value={text}
            oninput={onTextInput}
          ></textarea>
        </div>
      </div>
      <div class="flex min-h-0 flex-col rounded-md border">
        <div class="shrink-0 border-b px-2 py-1 text-sm font-semibold">SQL</div>
        <pre class="min-h-0 flex-1 overflow-auto p-2 font-mono text-xs leading-relaxed">{sql || '-- compile to see the SQL conversion'}</pre>
      </div>
    </div>
  {/if}
</div>
