<script lang="ts">
  import { getContext } from 'svelte';
  import { cn } from '$lib/utils';

  type Props = { class?: string; value: string; children?: import('svelte').Snippet };
  let { class: className = '', value, children }: Props = $props();

  const ctx = getContext<{ value: string }>('tabs');
  const active = $derived(ctx.value === value);
</script>

{#if active}
  <div role="tabpanel" class={cn('mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2', className)}>
    {@render children?.()}
  </div>
{/if}
