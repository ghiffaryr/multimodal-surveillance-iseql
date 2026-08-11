<script lang="ts">
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import type { Condition, Deltas, EventTypeInfo } from '$lib/types';
  import { inputInt } from '$lib/dom-helpers';
  import { Database } from 'lucide-svelte';

  type Props = {
    condition: Condition;
    deltas: Deltas;
    eventTypes: EventTypeInfo[];
    defaultDeltas: Deltas;
    onChangeDeltas: (d: Deltas) => void;
    disabled?: boolean;
  };
  let {
    condition,
    deltas = $bindable(),
    eventTypes,
    defaultDeltas,
    onChangeDeltas,
    disabled = false,
  }: Props = $props();

  const deltaFields = $derived(
    [...new Set(eventTypes.flatMap(e => [e.delta_param, e.delta_param2]).filter((k): k is string => !!k))]
      .sort((a, b) => {
        const va = a.startsWith('delta_visual_') ? 0 : 1;
        const vb = b.startsWith('delta_visual_') ? 0 : 1;
        return va - vb || a.localeCompare(b);
      })
      .map(key => ({
        key,
        label: key,
        id: `d-${key.replace(/^delta_/, '')}`,
      }))
  );

  const fieldsForCondition = $derived(
    condition === 'A'
      ? deltaFields.filter(f => f.key.startsWith('delta_visual_'))
      : condition === 'B'
        ? deltaFields.filter(f => f.key.startsWith('delta_sound_'))
        : deltaFields
  );

  function patch(p: Deltas) {
    onChangeDeltas({ ...deltas, ...p });
  }
</script>

<div class="rounded-md border border-border bg-muted/30 p-3 text-xs mb-4">
  <p class="flex items-center gap-1 font-medium text-foreground">
    <Database class="size-3.5 text-sky-500" /> All events auto-detected via ISEQL SQL queries
  </p>
</div>

<div class="grid grid-cols-2 gap-3">
  {#each fieldsForCondition as f}
    <Field>
      <Label for={f.id}>{f.label}</Label>
      <Input id={f.id} type="number" min="0" value={deltas[f.key] ?? defaultDeltas[f.key] ?? 0}
        onchange={(e) => patch({ [f.key]: inputInt(e, defaultDeltas[f.key] ?? 0) })}
        {disabled} />
    </Field>
  {/each}
</div>
