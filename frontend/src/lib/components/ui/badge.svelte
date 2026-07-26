<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements';
  import { badgeClasses, type BadgeVariant } from './badge';

  type Props = HTMLAttributes<HTMLDivElement> & { class?: string; variant?: BadgeVariant; children?: import('svelte').Snippet };
  let { class: className = '', variant = 'default', children, ...rest }: Props = $props();
</script>

<div class={badgeClasses(variant, [className])} {...rest}>
  {@render children?.()}
</div>
