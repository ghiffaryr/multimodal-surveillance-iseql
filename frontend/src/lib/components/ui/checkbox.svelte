<script lang="ts">
  import { Checkbox as CheckboxPrimitive } from 'bits-ui';
  import { Check } from 'lucide-svelte';
  import { cn } from '$lib/utils';

  type Props = CheckboxPrimitive.Props;
  let { class: className, ...rest }: Props = $props();
</script>

<CheckboxPrimitive.Root
  class={cn(
    'peer size-4 shrink-0 rounded-sm border border-primary shadow focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
    className
  )}
  {...rest}
>
  <CheckboxPrimitive.Indicator class="flex items-center justify-center text-current">
    <Check class="size-4" />
  </CheckboxPrimitive.Indicator>
</CheckboxPrimitive.Root>
