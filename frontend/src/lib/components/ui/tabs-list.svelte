<script lang="ts">
  import { cn } from '$lib/utils';
  type Props = { class?: string; children?: import('svelte').Snippet };
  let { class: className = '', children }: Props = $props();
</script>

<div class={cn('inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground', className)}>
  {@render children?.()}
</div>
