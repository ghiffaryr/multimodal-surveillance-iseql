<script lang="ts">
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import Badge from '$lib/components/ui/badge.svelte';
  import { Eye, Ear, Layers } from 'lucide-svelte';
  import type { Condition } from '$lib/types';

  type Props = {
    value: Condition;
    onChange: (c: Condition) => void;
    disabled?: boolean;
  };
  let { value = $bindable(), onChange, disabled = false }: Props = $props();

  const audioLabel = $derived('Audio Model');

  const CONDITIONS = $derived([{
      id: 'A' as Condition,
      label: 'Visual only',
      description: 'VLM + ISEQL, no sound. The VIS MODE baseline.',
      icon: Eye,
      badge: 'A',
      badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
    }, {
      id: 'B' as Condition,
      label: 'Sound only',
      description: `${audioLabel} + ISEQL, no VLM. Off-camera events.`,
      icon: Ear,
      badge: 'B',
      badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
    }, {
      id: 'C' as Condition,
      label: 'Full multimodal',
      description: `VLM + ${audioLabel} + ISEQL. Visual guards against acoustic FP.`,
      icon: Layers,
      badge: 'C',
      badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    },
  ]);
</script>

<Field>
  <Label for="condition-a">Ablation condition</Label>
  <div class="mt-2 grid grid-cols-1 gap-2">
    {#each CONDITIONS as c (c.id)}
      {@const selected = value === c.id}
      {@const Icon = c.icon}
      <label
        class={[
          'flex cursor-pointer items-start gap-3 rounded-md border p-3 text-left transition-colors',
          selected
            ? 'border-primary/60 bg-primary/10'
            : 'border-border bg-muted/30 hover:bg-muted/50',
          disabled ? 'cursor-not-allowed opacity-50' : '',
        ].join(' ')}
      >
        <input
          id={`condition-${c.id}`}
          type="radio"
          name="condition"
          value={c.id}
          checked={selected}
          onchange={() => onChange(c.id)}
          {disabled}
          class="mt-1 size-4 accent-primary"
        />
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <Icon class="size-4 text-foreground" />
            <span class="text-sm font-medium text-foreground">{c.label}</span>
            <span class={['rounded border px-1.5 py-0.5 text-[10px] font-semibold', c.badgeClass].join(' ')}>
              {c.badge}
            </span>
          </div>
          <p class="mt-0.5 text-xs text-muted-foreground">{c.description}</p>
        </div>
      </label>
    {/each}
  </div>
  <p class="mt-2 text-xs text-muted-foreground">
    Each condition populates a disjoint subset of the SQLite tables; the
    high-level event detector picks the right query set automatically.
  </p>
</Field>
