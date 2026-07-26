<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements';
  import { cn } from '$lib/utils';
  type Props = HTMLAttributes<HTMLDivElement> & { class?: string };
  let { class: className = '', ...rest }: Props = $props();
</script>

<div role="separator" class={cn('shrink-0 bg-border h-[1px] w-full', className)} {...rest}></div>
