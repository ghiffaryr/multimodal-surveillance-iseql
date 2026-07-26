<script lang="ts">
  import { APP_NAME, APP_TAGLINE } from '$lib/app';
  import Separator from '$lib/components/ui/separator.svelte';
  import Badge from '$lib/components/ui/badge.svelte';
  import { cn } from '$lib/utils';

  type Props = { class?: string; currentStage?: string; currentEvent?: string; children?: import('svelte').Snippet };
  let { class: className = '', currentStage = 'idle', currentEvent = '', children }: Props = $props();
</script>

<aside class={cn('flex h-full w-80 shrink-0 flex-col border-r border-border bg-card text-card-foreground', className)}>
  <div class="flex flex-col gap-1 px-6 py-5">
    <h1 class="text-2xl font-bold tracking-tight">{APP_NAME}</h1>
    <p class="text-xs text-muted-foreground">{APP_TAGLINE}</p>
  </div>
  <Separator />
  <div class="flex-1 overflow-y-auto px-4 py-4">
    {@render children?.()}
  </div>
  <Separator />
  <div class="flex flex-col gap-2 px-4 py-4 text-xs text-muted-foreground">
    <div class="flex items-center justify-between">
      <span>Status</span>
      <Badge variant={currentStage === 'done' ? 'default' : currentStage === 'failed' ? 'destructive' : 'secondary'}>
        {currentStage}
      </Badge>
    </div>
    {#if currentEvent}
      <div class="flex items-center justify-between">
        <span>Event</span>
        <code class="rounded bg-muted px-1.5 py-0.5 text-foreground">{currentEvent}</code>
      </div>
    {/if}
  </div>
</aside>
