<script lang="ts">
  import Select from '$lib/components/ui/select.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import Tabs from '$lib/components/ui/tabs.svelte';
  import TabsList from '$lib/components/ui/tabs-list.svelte';
  import TabsTrigger from '$lib/components/ui/tabs-trigger.svelte';
  import TabsContent from '$lib/components/ui/tabs-content.svelte';
  import type { Condition, EventTypeInfo, Deltas } from '$lib/types';
  import { inputInt } from '$lib/dom-helpers';
  import { Database } from 'lucide-svelte';

  const DELTA_FIELDS: Array<{ key: keyof Deltas; label: string; id: string; fallback: number; conditions: string[] }> = [
    { key: 'delta_visual_vehicle_escape', label: 'delta_visual_vehicle_escape', id: 'd-visual-vehicle-escape', fallback: 50, conditions: ['A', 'C'] },
    { key: 'delta_visual_loitering', label: 'delta_visual_loitering', id: 'd-visual-loitering', fallback: 150, conditions: ['A', 'C'] },
    { key: 'delta_visual_handoff', label: 'delta_visual_handoff', id: 'd-visual-handoff', fallback: 240, conditions: ['A', 'C'] },
    { key: 'delta_visual_fight', label: 'delta_visual_fight', id: 'd-visual-fight', fallback: 60, conditions: ['A', 'C'] },
    { key: 'delta_sound_fight', label: 'delta_sound_fight', id: 'd-s-fight', fallback: 120, conditions: ['B', 'C'] },
    { key: 'delta_sound_gunshot_or_explosion', label: 'delta_sound_gunshot_or_explosion', id: 'd-s-ge', fallback: 60, conditions: ['B', 'C'] },
    { key: 'delta_sound_vehicle_escape', label: 'delta_sound_vehicle_escape', id: 'd-s-ve', fallback: 150, conditions: ['B', 'C'] },
    { key: 'delta_sound_vehicle_collision', label: 'delta_sound_vehicle_collision', id: 'd-s-vc', fallback: 60, conditions: ['B', 'C'] },
    { key: 'delta_audio_visual_proximity', label: 'delta_audio_visual_proximity', id: 'd-av-prox', fallback: 60, conditions: ['C'] },
  ];

  const CONDITION_TABS: Array<{ value: Condition; label: string; desc: string }> = [
    { value: 'A', label: 'A. Visual', desc: 'Visual ISEQL event (condition A)' },
    { value: 'B', label: 'B. Sound only', desc: 'Sound ISEQL event (condition B)' },
    { value: 'C', label: 'C. Multimodal', desc: 'Multimodal fusion event (condition C)' },
  ];

  type Props = {
    condition: Condition;
    aEvents: EventTypeInfo[];
    bEvents: EventTypeInfo[];
    cEvents: EventTypeInfo[];
    selected: string;
    onChangeSelected: (id: string) => void;
    deltas: Deltas;
    onChangeDeltas: (d: Deltas) => void;
    disabled?: boolean;
  };
  let {
    condition,
    aEvents,
    bEvents,
    cEvents,
    selected = $bindable(),
    onChangeSelected,
    deltas = $bindable(),
    onChangeDeltas,
    disabled = false,
  }: Props = $props();

  function patch(p: Partial<Deltas>) {
    onChangeDeltas({ ...deltas, ...p });
  }

  const eventsByCondition = $derived<Record<Condition, EventTypeInfo[]>>({ A: aEvents, B: bEvents, C: cEvents });
  const currentList = $derived(eventsByCondition[condition]);
  const currentEvent = $derived(currentList.find((e) => e.id === selected));
  const currentDeltaKey = $derived(currentEvent?.delta_param);
  const visibleDeltaFields = $derived(DELTA_FIELDS.filter(f => f.conditions.includes(condition)));

  function handleSelect(e: Event) {
    onChangeSelected((e.currentTarget as HTMLSelectElement).value);
  }
</script>

<Tabs value={condition} class="w-full">
  <TabsList class="w-full">
    {#each CONDITION_TABS as tab}
      <TabsTrigger value={tab.value}>{tab.label} ({eventsByCondition[tab.value].length})</TabsTrigger>
    {/each}
  </TabsList>

  {#each CONDITION_TABS as tab}
    <TabsContent value={tab.value}>
      <Field>
        <Label for="event-{tab.value}">{tab.desc}</Label>
        <Select
          id="event-{tab.value}"
          options={eventsByCondition[tab.value].map((e) => ({ value: e.id, label: e.label }))}
          value={selected}
          onchange={handleSelect}
          {disabled}
        />
      </Field>
      {#if tab.value === 'B' || tab.value === 'C'}
        <p class="mt-1 text-xs text-muted-foreground">
          {tab.value === 'B' ? 'Temporal sound sequence query over SoundIntervals. No VLM.' : 'Visual JOIN sound with ISEQL temporal operators.'}
        </p>
      {/if}
    </TabsContent>
  {/each}
</Tabs>

<div class="mt-4 grid grid-cols-2 gap-3">
  {#each visibleDeltaFields as f}
    <Field>
      <Label for={f.id}>{f.label}</Label>
      <Input
        id={f.id} type="number" min="0"
        value={deltas[f.key]}
        onchange={(e) => patch({ [f.key]: inputInt(e, f.fallback) } as Partial<Deltas>)}
        {disabled}
      />
    </Field>
  {/each}
</div>

{#if currentEvent}
  <div class="mt-3 rounded-md border border-border bg-muted/30 p-3 text-xs">
    <p class="flex items-center gap-1 font-medium text-foreground">
      <Database class="size-3.5 text-sky-500" /> Pure SQL (ISEQL)
    </p>
    {#if currentDeltaKey}
      <p class="mt-1 text-muted-foreground">
        Tunable delta: <code class="rounded bg-muted px-1 text-foreground">{currentDeltaKey}</code>
      </p>
    {/if}
  </div>
{/if}
