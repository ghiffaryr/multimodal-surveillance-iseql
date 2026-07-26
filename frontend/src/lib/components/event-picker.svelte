<script lang="ts">
  import Select from '$lib/components/ui/select.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import type { Condition, EventTypeInfo, Deltas } from '$lib/types';
  import { inputInt } from '$lib/dom-helpers';
  import { Database } from 'lucide-svelte';

  const DELTA_FIELDS: Array<{ key: keyof Deltas; label: string; id: string; fallback: number }> = [
    { key: 'delta_visual_vehicle_escape', label: 'delta_visual_vehicle_escape', id: 'd-visual-vehicle-escape', fallback: 50 },
    { key: 'delta_visual_loitering', label: 'delta_visual_loitering', id: 'd-visual-loitering', fallback: 150 },
    { key: 'delta_visual_handoff', label: 'delta_visual_handoff', id: 'd-visual-handoff', fallback: 240 },
    { key: 'delta_visual_fight', label: 'delta_visual_fight', id: 'd-visual-fight', fallback: 60 },
    { key: 'delta_sound_fight', label: 'delta_sound_fight', id: 'd-s-fight', fallback: 120 },
    { key: 'delta_sound_gunshot_or_explosion', label: 'delta_sound_gunshot_or_explosion', id: 'd-s-ge', fallback: 60 },
    { key: 'delta_sound_vehicle_escape', label: 'delta_sound_vehicle_escape', id: 'd-s-ve', fallback: 150 },
    { key: 'delta_sound_vehicle_collision', label: 'delta_sound_vehicle_collision', id: 'd-s-vc', fallback: 60 },
    { key: 'delta_audio_visual_proximity', label: 'delta_audio_visual_proximity', id: 'd-av-prox', fallback: 60 },
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
    selected,
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
  const currentDeltaKey2 = $derived(currentEvent?.delta_param2);

  function handleSelect(e: Event) {
    onChangeSelected((e.currentTarget as HTMLSelectElement).value);
  }

  const visualFields = DELTA_FIELDS.filter(f => f.key.startsWith('delta_visual_'));
  const soundFields = DELTA_FIELDS.filter(f => f.key.startsWith('delta_sound_'));
</script>

{#if condition === 'A'}
  {@const evts = eventsByCondition.A}
  <Field>
    <Label for="event-a">Visual ISEQL event (condition A)</Label>
    <Select id="event-a" options={evts.map(e => ({ value: e.id, label: e.label }))} value={selected}
      onchange={handleSelect} {disabled} />
  </Field>
{:else if condition === 'B'}
  {@const evts = eventsByCondition.B}
  <Field>
    <Label for="event-b">Sound ISEQL event (condition B)</Label>
    <Select id="event-b" options={evts.map(e => ({ value: e.id, label: e.label }))} value={selected}
      onchange={handleSelect} {disabled} />
  </Field>
  <p class="mt-1 text-xs text-muted-foreground">
    Temporal sound sequence query over SoundIntervals. No VLM.
  </p>
{:else}
  {@const evts = eventsByCondition.C}
  <Field>
    <Label for="event-c">Multimodal fusion event (condition C)</Label>
    <Select id="event-c" options={evts.map(e => ({ value: e.id, label: e.label }))} value={selected}
      onchange={handleSelect} {disabled} />
  </Field>
  <p class="mt-1 text-xs text-muted-foreground">
    Visual JOIN sound with ISEQL temporal operators.
  </p>
{/if}

{#if currentEvent}
  <div class="mt-3 rounded-md border border-border bg-muted/30 p-3 text-xs">
    <p class="flex items-center gap-1 font-medium text-foreground">
      <Database class="size-3.5 text-sky-500" /> Pure SQL (ISEQL)
    </p>
    {#if currentDeltaKey}
      <p class="mt-1 text-muted-foreground">
        Tunable delta: <code class="rounded bg-muted px-1 text-foreground">{currentDeltaKey}</code>
        {#if currentDeltaKey2}
          , <code class="rounded bg-muted px-1 text-foreground">{currentDeltaKey2}</code>
        {/if}
      </p>
    {/if}
  </div>
{/if}

{#if condition === 'A'}
  <div class="mt-4 grid grid-cols-2 gap-3">
    {#each visualFields as f}
      <Field>
        <Label for={f.id}>{f.label}</Label>
        <Input id={f.id} type="number" min="0" value={deltas[f.key]}
          onchange={(e) => patch({ [f.key]: inputInt(e, f.fallback) } as Partial<Deltas>)}
          {disabled} />
      </Field>
    {/each}
  </div>
{:else if condition === 'B'}
  <div class="mt-4 grid grid-cols-2 gap-3">
    {#each soundFields as f}
      <Field>
        <Label for={f.id}>{f.label}</Label>
        <Input id={f.id} type="number" min="0" value={deltas[f.key]}
          onchange={(e) => patch({ [f.key]: inputInt(e, f.fallback) } as Partial<Deltas>)}
          {disabled} />
      </Field>
    {/each}
  </div>
{:else}
  <div class="mt-4 grid grid-cols-2 gap-3">
    {#each DELTA_FIELDS as f}
      <Field>
        <Label for={f.id}>{f.label}</Label>
        <Input id={f.id} type="number" min="0" value={deltas[f.key]}
          onchange={(e) => patch({ [f.key]: inputInt(e, f.fallback) } as Partial<Deltas>)}
          {disabled} />
      </Field>
    {/each}
  </div>
{/if}
