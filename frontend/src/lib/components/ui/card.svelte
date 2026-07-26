<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements';
  import { cn } from '$lib/utils';

  type Props = HTMLAttributes<HTMLDivElement> & { class?: string; children?: import('svelte').Snippet };
  let { class: className = '', children, ...rest }: Props = $props();
</script>

<div class={cn('rounded-lg border bg-card text-card-foreground shadow-sm', className)} {...rest}>
  {@render children?.()}
</div>
