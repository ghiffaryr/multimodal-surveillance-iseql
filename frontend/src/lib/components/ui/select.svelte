<script lang="ts">
  import type { HTMLSelectAttributes } from 'svelte/elements';
  import { cn } from '$lib/utils';

  type Option = { value: string; label: string };

  type Props = Omit<HTMLSelectAttributes, 'children'> & {
    class?: string;
    value?: string;
    options: Option[];
    children?: import('svelte').Snippet;
  };

  let { class: className = '', value = $bindable(''), options, ...rest }: Props = $props();
</script>

<select
  bind:value
  class={cn(
    'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>option]:bg-background',
    className
  )}
  {...rest}
>
  {#each options as opt (opt.value)}
    <option value={opt.value} selected={opt.value === value}>{opt.label}</option>
  {/each}
</select>
