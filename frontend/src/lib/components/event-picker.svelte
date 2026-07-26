<script lang="ts">
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import type { Condition, Deltas } from '$lib/types';
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

  const visualFields = DELTA_FIELDS.filter(f => f.key.startsWith('delta_visual_'));
  const soundFields = DELTA_FIELDS.filter(f => f.key.startsWith('delta_sound_'));

  type Props = {
    condition: Condition;
    deltas: Deltas;
    onChangeDeltas: (d: Deltas) => void;
    disabled?: boolean;
  };
  let {
    condition,
    deltas = $bindable(),
    onChangeDeltas,
    disabled = false,
  }: Props = $props();

  function patch(p: Partial<Deltas>) {
    onChangeDeltas({ ...deltas, ...p });
  }
</script>

<div class="rounded-md border border-border bg-muted/30 p-3 text-xs mb-4">
  <p class="flex items-center gap-1 font-medium text-foreground">
    <Database class="size-3.5 text-sky-500" /> All events auto-detected via ISEQL SQL queries
  </p>
</div>

{#if condition === 'A'}
  <div class="grid grid-cols-2 gap-3">
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
  <div class="grid grid-cols-2 gap-3">
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
  <div class="grid grid-cols-2 gap-3">
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
