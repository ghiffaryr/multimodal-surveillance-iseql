<script lang="ts">
  import { page } from '$app/state';
  import Button from '$lib/components/ui/button.svelte';
  import ObjectMemoryViewer from '$lib/components/object-memory-viewer.svelte';
  import { ArrowLeft } from 'lucide-svelte';

  const analysis_id = $derived(String(page.params.analysis_id ?? ''));
</script>

<div class="mx-auto flex h-screen w-full max-w-7xl flex-col gap-3 p-4">
  <header class="flex items-center justify-between">
    <div>
      <h1 class="text-lg font-semibold">Object Memory</h1>
      <p class="text-xs text-muted-foreground">Analysis <span class="font-mono">{analysis_id}</span></p>
    </div>
    <Button href="/" variant="outline" size="sm"><ArrowLeft /> Back to analysis</Button>
  </header>

  {#if analysis_id}
    <ObjectMemoryViewer analysisId={analysis_id} />
  {/if}
</div>
