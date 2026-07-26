<script lang="ts">
  import { api } from '$lib/api';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import type { VlmConfig } from '$lib/types';
  import { selectValue, inputInt, inputFloat } from '$lib/dom-helpers';

  const DEFAULT_GRID_ROWS = 2;
  const DEFAULT_GRID_COLS = 4;

  const PROVIDER_DEFAULTS: Record<string, { delay: number; max_retries: number }> = {
    gemini: { delay: 0.1, max_retries: 10 },
    mistral: { delay: 3.0, max_retries: 10 },
    zhipu: { delay: 10.0, max_retries: 10 },
    ollama: { delay: 0, max_retries: 0 },
  };

  const QUANTIZATION_OPTIONS = [
    { value: 'none', label: 'None (full precision)' },
    { value: '8bit', label: '8-bit' },
    { value: '4bit', label: '4-bit' },
  ];

  type Props = {
    value: VlmConfig;
    onChange: (v: VlmConfig) => void;
    disabled?: boolean;
    availableProviders?: string[];
    detectedFps?: number;
  };
  let { value = $bindable(), onChange, disabled = false, availableProviders = [], detectedFps = 0 }: Props = $props();

  let ollamaModels = $state<{ value: string; label: string }[]>([]);
  let ollamaModelsLoading = $state(false);
  let ollamaModelsFailed = $state(false);
  let _ollamaFetched = false;

  let isOllama = $derived(value.provider === 'ollama');
  let providerOptions = $derived(
    availableProviders.map(p => ({ value: p, label: p.charAt(0).toUpperCase() + p.slice(1) }))
  );

  function patch(p: Partial<VlmConfig>) {
    onChange({ ...value, ...p });
  }

  async function fetchOllamaModels() {
    if (_ollamaFetched || ollamaModelsLoading) return;
    _ollamaFetched = true;
    ollamaModelsLoading = true;
    ollamaModelsFailed = false;
    try {
      const resp = await api.get<{ models: { name: string; label: string }[]; error?: string }>(
        '/api/vlm/models?provider=ollama'
      );
      if (!resp.error && resp.models?.length) {
        ollamaModels = resp.models.map((m) => ({ value: m.name, label: m.label }));
      } else {
        ollamaModelsFailed = true;
      }
    } catch {
      ollamaModelsFailed = true;
    } finally {
      ollamaModelsLoading = false;
    }
  }

  $effect(() => {
    if (availableProviders.length > 0 && !value.provider) {
      const p = availableProviders[0];
      const d = PROVIDER_DEFAULTS[p] || { delay: 3, max_retries: 10 };
      patch({ provider: p, model: '', vlm_delay: d.delay, max_retries: d.max_retries });
      if (p === 'ollama') fetchOllamaModels();
    }
  });

  function handleProviderChange(e: Event) {
    const p = selectValue(e);
    const d = PROVIDER_DEFAULTS[p] || { delay: 3, max_retries: 10 };
    patch({ provider: p, model: '', vlm_delay: d.delay, max_retries: d.max_retries });
    if (p === 'ollama') fetchOllamaModels();
  }
</script>

<div class="grid grid-cols-2 gap-4">
  <Field>
    <Label for="vlm-provider">VLM Provider</Label>
    <Select
      id="vlm-provider"
      options={providerOptions}
      value={value.provider}
      onchange={handleProviderChange}
      {disabled}
    />
  </Field>

  <Field>
    <Label for="vlm-model">Model</Label>
    {#if isOllama && ollamaModelsLoading}
      <div class="flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
        Detecting models...
      </div>
    {:else if isOllama && ollamaModelsFailed}
      <div class="flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
        Failed to detect models. <button type="button" class="ml-1 underline" onclick={fetchOllamaModels}>Retry</button>
      </div>
    {:else if isOllama && ollamaModels.length > 0}
      <Select
        id="vlm-model"
        options={ollamaModels}
        value={value.model}
        onchange={(e) => patch({ model: selectValue(e) })}
        {disabled}
      />
    {:else}
      <Input
        id="vlm-model"
        type="text"
        placeholder={isOllama ? 'No models found, type name' : 'Type model name'}
        value={value.model}
        onchange={(e) => patch({ model: selectValue(e) })}
        {disabled}
      />
    {/if}
  </Field>

  {#if isOllama}
    <Field>
      <Label for="vlm-quantization">Quantization (Ollama only)</Label>
      <Select
        id="vlm-quantization"
        options={QUANTIZATION_OPTIONS}
        value={value.quantization || 'none'}
        onchange={(e) => patch({ quantization: selectValue(e) })}
        {disabled}
      />
    </Field>
  {/if}

  <Field>
    <Label for="grid-rows">Grid Rows</Label>
    <Input id="grid-rows" type="number" min="1" max="10"
      value={value.grid_rows}
      onchange={(e) => patch({ grid_rows: inputInt(e, DEFAULT_GRID_ROWS) })}
      {disabled} />
  </Field>

  <Field>
    <Label for="grid-cols">Grid Columns</Label>
    <Input id="grid-cols" type="number" min="1" max="10"
      value={value.grid_cols}
      onchange={(e) => patch({ grid_cols: inputInt(e, DEFAULT_GRID_COLS) })}
      {disabled} />
  </Field>

  <Field class="col-span-2">
    <Label for="sampling-rate">Sampling Rate</Label>
    <div class="flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
      {detectedFps > 0 ? `Auto-detected: ${detectedFps} fps (1 frame/second)` : 'Auto-detected from video'}
    </div>
  </Field>

  {#if !isOllama}
    <Field class="col-span-2">
      <Label for="vlm-delay">Delay between VLM calls (seconds)</Label>
      <Input id="vlm-delay" type="number" min="0" step="0.1"
        value={value.vlm_delay}
        onchange={(e) => patch({ vlm_delay: inputFloat(e, 3) })}
        {disabled} />
    </Field>

    <Field class="col-span-2">
      <Label for="vlm-max-retries">Max retries on rate limit</Label>
      <Input id="vlm-max-retries" type="number" min="0" max="20"
        value={value.max_retries}
        onchange={(e) => patch({ max_retries: inputInt(e, 10) })}
        {disabled} />
    </Field>
  {/if}
</div>
