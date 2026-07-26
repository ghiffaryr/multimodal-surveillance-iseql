<script lang="ts" module>
  export type TabsContext = {
    value: string;
    setValue: (v: string) => void;
  };
</script>

<script lang="ts">
  import { setContext, getContext } from 'svelte';
  import { writable, type Writable } from 'svelte/store';
  import { cn } from '$lib/utils';

  type Props = { class?: string; value?: string; children?: import('svelte').Snippet };
  let { class: className = '', value = $bindable(''), children }: Props = $props();

  const store = writable(value);
  $effect(() => { store.set(value); });
  $effect(() => { value = $store; });
  setContext<TabsContext>('tabs', {
    get value() { return $store; },
    setValue: (v) => store.set(v),
  });
</script>

<div class={cn('w-full', className)} data-tabs-root>
  {@render children?.()}
</div>
