<script lang="ts">
  import Tabs from '$lib/components/ui/tabs.svelte';
  import TabsList from '$lib/components/ui/tabs-list.svelte';
  import TabsTrigger from '$lib/components/ui/tabs-trigger.svelte';
  import TabsContent from '$lib/components/ui/tabs-content.svelte';
  import EventEditor from '$lib/components/event-editor.svelte';
  import EventManager from '$lib/components/event-manager.svelte';
  import RelationConfigurator from '$lib/components/relation-configurator.svelte';
  import AudioSettings from '$lib/components/audio-settings.svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { ArrowLeft } from 'lucide-svelte';
  import type { Condition } from '$lib/types';

  let active = $state('events');
  let condition = $state<Condition>('A');
  let editing = $state(false);
  let activeId = $state<string | null>(null);
  let mode = $state<'new' | 'open'>('new');
</script>

<div class="mx-auto flex h-screen w-full max-w-7xl flex-col gap-3 p-4">
  <header class="flex items-center justify-between">
    <div>
      <h1 class="text-lg font-semibold">Events Configuration</h1>
      <p class="text-xs text-muted-foreground">
        Author ISEQL events, relations, and audio events. Saved to the database.
      </p>
    </div>
    <Button href="/" variant="outline" size="sm"><ArrowLeft /> Back to analysis</Button>
  </header>

  <Tabs bind:value={active} class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border">
    <TabsList class="shrink-0 border-b px-2 py-1">
      <TabsTrigger value="events">Events (ISEQL)</TabsTrigger>
      <TabsTrigger value="relations">Relations</TabsTrigger>
      <TabsTrigger value="audio">Audio events</TabsTrigger>
    </TabsList>

    {#if active === 'events'}
      <TabsContent value="events" class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <span class="text-sm text-muted-foreground">Condition:</span>
          {#each [
            { id: 'A' as Condition, label: 'A · Visual', hint: 'VLM + ISEQL (visual only)' },
            { id: 'B' as Condition, label: 'B · Audio', hint: 'PANNs + ISEQL (audio only)' },
            { id: 'C' as Condition, label: 'C · Multimodal', hint: 'visual + audio via set operations (∪/∖/∩)' },
          ] as c}
            <button
              type="button"
              title={c.hint}
              class={[
                'rounded-md border px-3 py-1 text-sm',
                condition === c.id ? 'border-primary bg-primary/10 font-medium' : 'text-muted-foreground hover:bg-muted/40',
              ].join(' ')}
              onclick={() => { condition = c.id; editing = false; }}
            >
              {c.label}
            </button>
          {/each}
        </div>

        <div class="min-h-0 flex-1 overflow-hidden">
          {#if editing}
            <EventEditor
              condition={condition}
              initialId={activeId}
              mode={mode}
              onBack={() => (editing = false)}
              onSaved={() => { activeId = null; editing = false; }}
            />
          {:else}
            <EventManager
              condition={condition}
              onNew={() => { activeId = null; mode = 'new'; editing = true; }}
              onOpen={(id) => { activeId = id; mode = 'open'; editing = true; }}
            />
          {/if}
        </div>
      </TabsContent>
    {/if}

    {#if active === 'relations'}
      <TabsContent value="relations" class="min-h-0 flex-1 overflow-y-auto p-4">
        <RelationConfigurator />
      </TabsContent>
    {/if}

    {#if active === 'audio'}
      <TabsContent value="audio" class="min-h-0 flex-1 overflow-y-auto p-4">
        <AudioSettings />
      </TabsContent>
    {/if}
  </Tabs>
</div>
