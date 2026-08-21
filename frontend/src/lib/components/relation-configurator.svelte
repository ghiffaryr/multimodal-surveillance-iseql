<script lang="ts">
  import { api } from '$lib/api';
  import Input from '$lib/components/ui/input.svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { Trash2 } from 'lucide-svelte';
  import type { PromptOverrides } from '$lib/types';
  import { DEFAULT_RELATION_VOCAB_TEMPLATE } from '$lib/types';
  import { inputStr } from '$lib/dom-helpers';

  interface RelationRow {
    name: string;
    classid: string;
    description: string;
  }

  let rows = $state<RelationRow[]>([]);
  let search = $state('');
  let error = $state<string | null>(null);
  let savedMsg = $state<string | null>(null);

  let editing = $state(false);
  let activeIndex = $state<number | null>(null);
  let draft = $state<RelationRow>({ name: '', classid: '(ID)', description: '' });

  function toRows(vocab: PromptOverrides): RelationRow[] {
    const classids = vocab.relation_classids ?? [];
    const descriptions = vocab.relation_descriptions ?? {};
    if (!classids.length) return [];
    return classids.map(([name, classid]) => ({
      name,
      classid,
      description: descriptions[name] ?? '',
    }));
  }

  async function load() {
    error = null;
    try {
      const resp = await api.get<{ sections: Record<string, object> }>('/api/config');
      const t = (resp.sections || {}).relation_vocab as PromptOverrides | undefined;
      rows = toRows(t ?? {
        relation_classids: [...DEFAULT_RELATION_VOCAB_TEMPLATE.relation_classids],
        relation_descriptions: { ...DEFAULT_RELATION_VOCAB_TEMPLATE.relation_descriptions },
      });
    } catch (e) {
      error = `Failed to load relations: ${(e as Error).message}`;
    }
  }

  $effect(() => {
    load();
  });

  const filtered = $derived(
    rows.filter((r) => r.name.toLowerCase().includes(search.toLowerCase()))
  );

  function open(i: number) {
    activeIndex = i;
    draft = { ...rows[i] };
    editing = true;
    error = null;
    savedMsg = null;
  }

  function openNew() {
    activeIndex = null;
    draft = { name: '', classid: '(ID)', description: '' };
    editing = true;
    error = null;
    savedMsg = null;
  }

  function toVocab(list: RelationRow[]): PromptOverrides {
    const valid = list.filter((r) => r.name.trim());
    return {
      relation_classids: valid.map((r) => [r.name.trim(), r.classid.trim() || '(ID)']),
      relation_descriptions: Object.fromEntries(valid.map((r) => [r.name.trim(), r.description.trim()])),
    };
  }

  async function save() {
    error = null;
    savedMsg = null;
    if (!draft.name.trim()) { error = 'Relation name is required.'; return; }
    const next = activeIndex === null
      ? [...rows, { ...draft, name: draft.name.trim() }]
      : rows.map((r, i) => (i === activeIndex ? { ...draft, name: draft.name.trim() } : r));
    try {
      await api.putJson('/api/config/relation_vocab', toVocab(next));
      rows = next;
      editing = false;
      savedMsg = activeIndex === null ? `Created relation '${draft.name.trim()}'.` : `Updated relation '${draft.name.trim()}'.`;
      setTimeout(() => (savedMsg = null), 3000);
    } catch (e) {
      error = `Failed to save relation: ${(e as Error).message}`;
    }
  }

  async function remove(i: number) {
    if (!confirm(`Delete relation '${rows[i].name}'?`)) return;
    const next = rows.filter((_, idx) => idx !== i);
    try {
      await api.putJson('/api/config/relation_vocab', toVocab(next));
      rows = next;
      if (editing && activeIndex === i) editing = false;
    } catch (err) {
      error = `Failed to delete relation: ${(err as Error).message}`;
    }
  }

  const textareaClass =
    'w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
</script>

<div class="flex h-full flex-col gap-3 overflow-hidden">
  {#if error}<p class="text-sm text-destructive">{error}</p>{/if}
  {#if savedMsg}<p class="text-sm text-emerald-600">{savedMsg}</p>{/if}

  {#if editing}
    <!-- editor (like the ISEQL event editor) -->
    <div class="flex flex-wrap items-center gap-2 rounded-md border p-2">
      <Button type="button" size="icon" variant="ghost" class="h-8 w-8" title="Back to relations" onclick={() => (editing = false)}>⌂</Button>
      <span class="text-sm text-muted-foreground">{activeIndex === null ? 'New relation' : `Edit ${draft.name || 'relation'}`}</span>
      <div class="flex-1"></div>
      <Button type="button" variant="secondary" onclick={save}>Save relation</Button>
      <Button type="button" variant="ghost" onclick={() => (editing = false)}>Cancel</Button>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto rounded-md border p-3">
      <div class="space-y-3">
        <div>
          <div class="mb-1 text-xs font-medium">Name</div>
          <Input class="w-full font-mono" placeholder="relation_name" value={draft.name} onchange={(e) => (draft = { ...draft, name: inputStr(e) })} />
        </div>
        <div>
          <div class="mb-1 text-xs font-medium">Class ID</div>
          <Input class="w-full font-mono" placeholder="(PersonID, VehicleID)" value={draft.classid} onchange={(e) => (draft = { ...draft, classid: inputStr(e) })} />
        </div>
        <div>
          <div class="mb-1 text-xs font-medium">Description</div>
          <textarea class={textareaClass} rows={6} placeholder="Describe the relation (used in the prompt)" value={draft.description}
            onchange={(e) => (draft = { ...draft, description: (e.currentTarget as HTMLTextAreaElement).value })}></textarea>
        </div>
      </div>
    </div>
  {:else}
    <!-- list -->
    <div class="flex flex-wrap items-center gap-2">
      <Button type="button" size="sm" variant="outline" onclick={openNew}>＋ New Relation</Button>
      <Input class="h-8 flex-1 font-mono text-xs" placeholder="Search relations…" value={search} oninput={(e) => (search = (e.currentTarget as HTMLInputElement).value)} />
      <span class="text-xs text-muted-foreground">{filtered.length} relation{filtered.length === 1 ? '' : 's'}</span>
    </div>

    <div class="min-h-0 flex-1 space-y-1 overflow-y-auto">
      {#each filtered as r, i (rows.indexOf(r))}
        <div
          role="button"
          tabindex="0"
          class="group flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 transition-colors hover:border-primary/50 hover:bg-muted/40"
          onclick={() => open(rows.indexOf(r))}
          onkeydown={(ev) => { if (ev.key === 'Enter') open(rows.indexOf(r)); }}
          title="Click to edit"
        >
          <span class="w-48 shrink-0 truncate font-mono text-sm font-medium">{r.name || '(unnamed)'}</span>
          <span class="w-40 shrink-0 truncate font-mono text-xs text-muted-foreground">{r.classid}</span>
          <span class="min-w-0 flex-1 truncate text-xs text-muted-foreground">{r.description || '-'}</span>
          <button
            class="shrink-0 p-1.5 text-muted-foreground/50 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
            onclick={(ev) => { ev.stopPropagation(); remove(rows.indexOf(r)); }}
            title="Delete relation"
          >
            <Trash2 class="size-3" />
          </button>
        </div>
      {:else}
        <p class="pt-2 text-sm text-muted-foreground">
          {rows.length === 0 ? 'No relations defined.' : 'No relations match your search.'}
        </p>
      {/each}
    </div>
  {/if}
</div>
