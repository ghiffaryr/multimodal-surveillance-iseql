<script lang="ts">
  import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';
  import { buttonClasses, type ButtonVariant, type ButtonSize } from './button';

  type Props = (HTMLButtonAttributes | HTMLAnchorAttributes) & {
    variant?: ButtonVariant;
    size?: ButtonSize;
    class?: string;
    href?: string;
    type?: 'button' | 'submit' | 'reset';
    children?: import('svelte').Snippet;
  };

  let {
    class: className = '',
    variant = 'default',
    size = 'default',
    href = undefined,
    type = 'button',
    children,
    ...rest
  }: Props = $props();
</script>

{#if href}
  <a {href} class={buttonClasses(variant, size, [className])} {...rest as HTMLAnchorAttributes}>
    {@render children?.()}
  </a>
{:else}
  <button {type} class={buttonClasses(variant, size, [className])} {...rest as HTMLButtonAttributes}>
    {@render children?.()}
  </button>
{/if}
