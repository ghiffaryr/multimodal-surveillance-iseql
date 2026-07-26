<script lang="ts">
  import Select from '$lib/components/ui/select.svelte';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import Tabs from '$lib/components/ui/tabs.svelte';
  import TabsList from '$lib/components/ui/tabs-list.svelte';
  import TabsTrigger from '$lib/components/ui/tabs-trigger.svelte';
  import TabsContent from '$lib/components/ui/tabs-content.svelte';
  import type { Condition, EventTypeInfo } from '$lib/types';
  import { Database } from 'lucide-svelte';

  export type Deltas = {
    delta_visual_vehicle_escape: number;
    delta_visual_loitering: number;
    delta_visual_handoff: number;
    delta_visual_fight: number;
    delta_sound_fight: number;
    delta_sound_gunshot_or_explosion: number;
    delta_sound_vehicle_escape: number;
    delta_sound_loitering: number;
    delta_sound_vehicle_collision: number;
    delta_audio_visual_proximity: number;
  };

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

  const currentList = $derived(
    condition === 'A' ? aEvents : condition === 'B' ? bEvents : cEvents,
  );
  const currentEvent = $derived(currentList.find((e) => e.id === selected));
  const currentDeltaKey = $derived(currentEvent?.delta_param);
</script>

<Tabs value={condition} class="w-full">
  <TabsList class="w-full">
    <TabsTrigger value="A" disabled>A. Visual ({aEvents.length})</TabsTrigger>
    <TabsTrigger value="B" disabled>B. Sound only ({bEvents.length})</TabsTrigger>
    <TabsTrigger value="C" disabled>C. Multimodal ({cEvents.length})</TabsTrigger>
  </TabsList>

  <TabsContent value="A">
    <Field>
      <Label for="event-a">Visual ISEQL event (condition A)</Label>
      <Select
        id="event-a"
        options={aEvents.map((e) => ({ value: e.id, label: e.label }))}
        value={selected}
        onchange={(e) => onChangeSelected((e.currentTarget as HTMLSelectElement).value)}
        {disabled}
      />
    </Field>
  </TabsContent>

  <TabsContent value="B">
    <Field>
      <Label for="event-b">Sound ISEQL event (condition B)</Label>
      <Select
        id="event-b"
        options={bEvents.map((e) => ({ value: e.id, label: e.label }))}
        value={selected}
        onchange={(e) => onChangeSelected((e.currentTarget as HTMLSelectElement).value)}
        {disabled}
      />
      <p class="mt-1 text-xs text-muted-foreground">
        Temporal sound sequence query over SoundIntervals. No VLM.
      </p>
    </Field>
  </TabsContent>

  <TabsContent value="C">
    <Field>
      <Label for="event-c">Multimodal fusion event (condition C)</Label>
      <Select
        id="event-c"
        options={cEvents.map((e) => ({ value: e.id, label: e.label }))}
        value={selected}
        onchange={(e) => onChangeSelected((e.currentTarget as HTMLSelectElement).value)}
        {disabled}
      />
      <p class="mt-1 text-xs text-muted-foreground">
        Visual JOIN sound with ISEQL temporal operators.
      </p>
    </Field>
  </TabsContent>
</Tabs>

<div class="mt-4 grid grid-cols-2 gap-3">
  <Field>
    <Label for="d-visual-vehicle-escape">delta_visual_vehicle_escape</Label>
    <Input id="d-visual-vehicle-escape" type="number" min="0" value={deltas.delta_visual_vehicle_escape}
      onchange={(e) => patch({ delta_visual_vehicle_escape: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 50 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-visual-loitering">delta_visual_loitering</Label>
    <Input id="d-visual-loitering" type="number" min="0" value={deltas.delta_visual_loitering}
      onchange={(e) => patch({ delta_visual_loitering: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 150 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-visual-handoff">delta_visual_handoff</Label>
    <Input id="d-visual-handoff" type="number" min="0" value={deltas.delta_visual_handoff}
      onchange={(e) => patch({ delta_visual_handoff: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 240 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-visual-fight">delta_visual_fight</Label>
    <Input id="d-visual-fight" type="number" min="0" value={deltas.delta_visual_fight}
      onchange={(e) => patch({ delta_visual_fight: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 60 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-s-fight">delta_sound_fight</Label>
    <Input id="d-s-fight" type="number" min="0" value={deltas.delta_sound_fight}
      onchange={(e) => patch({ delta_sound_fight: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 120 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-s-ge">delta_sound_gunshot_or_explosion</Label>
    <Input id="d-s-ge" type="number" min="0" value={deltas.delta_sound_gunshot_or_explosion}
      onchange={(e) => patch({ delta_sound_gunshot_or_explosion: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 60 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-s-ve">delta_sound_vehicle_escape</Label>
    <Input id="d-s-ve" type="number" min="0" value={deltas.delta_sound_vehicle_escape}
      onchange={(e) => patch({ delta_sound_vehicle_escape: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 150 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-s-loit">delta_sound_loitering</Label>
    <Input id="d-s-loit" type="number" min="0" value={deltas.delta_sound_loitering}
      onchange={(e) => patch({ delta_sound_loitering: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 30 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-s-vc">delta_sound_vehicle_collision</Label>
    <Input id="d-s-vc" type="number" min="0" value={deltas.delta_sound_vehicle_collision}
      onchange={(e) => patch({ delta_sound_vehicle_collision: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 60 })}
      {disabled} />
  </Field>
  <Field>
    <Label for="d-av-prox">delta_audio_visual_proximity</Label>
    <Input id="d-av-prox" type="number" min="0" value={deltas.delta_audio_visual_proximity}
      onchange={(e) => patch({ delta_audio_visual_proximity: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 60 })}
      {disabled} />
  </Field>
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
