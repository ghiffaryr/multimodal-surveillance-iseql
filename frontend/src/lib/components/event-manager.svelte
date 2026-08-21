<script lang="ts">
  import { api } from '$lib/api';
  import Input from '$lib/components/ui/input.svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { Trash2 } from 'lucide-svelte';
  import type { Condition, EventTypeInfo } from '$lib/types';

  type Props = {
    condition: Condition;
    onOpen: (id: string) => void;
    onNew: () => void;
  };
  let { condition, onOpen, onNew }: Props = $props();

  let events = $state<EventTypeInfo[]>([]);
  let search = $state('');
  let error = $state<string | null>(null);
  let loading = $state(false);

  async function load() {
    loading = true;
    error = null;
    try {
      const resp = await api.get<{ events: EventTypeInfo[] }>(`/api/events?condition=${condition}`);
      events = resp.events;
    } catch (e) {
      error = `Failed to load events: ${(e as Error).message}`;
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  const filtered = $derived(
    events.filter((e) => e.id.toLowerCase().includes(search.toLowerCase()))
  );

  async function remove(e: EventTypeInfo) {
    if (!confirm(`Delete event '${e.id}' for condition ${condition}?`)) return;
    try {
      await api.del(`/api/events/${e.id}?condition=${condition}`);
      await load();
    } catch (err) {
      error = `Failed to delete event: ${(err as Error).message}`;
    }
  }
</script>

<div class="flex h-full flex-col gap-3 overflow-y-auto">
  {#if error}<p class="text-sm text-destructive">{error}</p>{/if}

  <div class="flex flex-wrap items-center gap-2">
    <Button type="button" size="sm" variant="outline" onclick={onNew}>＋ New Event</Button>
    <Input class="h-8 flex-1 font-mono text-xs" placeholder="Search events…" value={search} oninput={(e) => (search = (e.currentTarget as HTMLInputElement).value)} />
    <span class="text-xs text-muted-foreground">{filtered.length} event{filtered.length === 1 ? '' : 's'}</span>
  </div>

  <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
    {#each filtered as e (e.id)}
      <div
        role="button"
        tabindex="0"
        class="group cursor-pointer rounded-md border p-2 transition-colors hover:border-primary/50 hover:bg-muted/40"
        onclick={() => onOpen(e.id)}
        onkeydown={(ev) => { if (ev.key === 'Enter') onOpen(e.id); }}
        title="Click to edit"
      >
        <div class="flex items-center justify-between gap-1">
          <span class="min-w-0 truncate font-mono text-sm font-medium">{e.id}</span>
          <button
            class="shrink-0 p-1.5 text-muted-foreground/50 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
            onclick={(ev) => { ev.stopPropagation(); remove(e); }}
            title="Delete event"
          >
            <Trash2 class="size-3" />
          </button>
        </div>
      </div>
    {:else}
      <p class="col-span-full text-sm text-muted-foreground">
        {loading ? 'Loading events…' : 'No events yet. Create your first one.'}
      </p>
    {/each}
  </div>
</div>
