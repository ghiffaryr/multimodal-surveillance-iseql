<script lang="ts">
  import { api } from '$lib/api';
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import Field from '$lib/components/ui/field.svelte';

  export type VlmConfig = {
    provider: string;
    model: string;
    grid_rows: number;
    grid_cols: number;
    sampling_rate: number;
    vlm_delay: number;
    quantization: string;
    max_retries: number;
  };

  type Props = { 
    value: VlmConfig; 
    onChange: (v: VlmConfig) => void; 
    disabled?: boolean;
    availableProviders?: string[];
  };
  let { value = $bindable(), onChange, disabled = false, availableProviders = [] }: Props = $props();

  let ollamaModels = $state<{ value: string; label: string }[]>([]);
  let ollamaModelsLoading = $state(false);

  let provider = $derived(value.provider);
  let model = $derived(value.model);
  let isOllama = $derived(provider === 'ollama');

  function patch(p: Partial<VlmConfig>) {
    onChange({ ...value, ...p });
  }

  let _fetchedOllama = false;
  async function fetchOllamaModels() {
    if (_fetchedOllama) return;
    _fetchedOllama = true;
    ollamaModelsLoading = true;
    try {
      const resp = await api.get<{ models: { name: string; label: string }[]; error?: string }>(
        '/api/vlm/models?provider=ollama'
      );
      if (!resp.error) {
        ollamaModels = resp.models.map((m) => ({ value: m.name, label: m.label }));
      }
    } catch {
      /* non-fatal */
    } finally {
      ollamaModelsLoading = false;
    }
  }

  $effect(() => {
    if (availableProviders.includes('ollama')) {
      fetchOllamaModels();
    }
  });

  $effect(() => {
    if (availableProviders.length > 0 && !provider) {
      patch({ provider: availableProviders[0], model: '' });
    }
  });

  function handleProviderChange(e: Event) {
    const newProvider = (e.currentTarget as HTMLSelectElement).value;
    patch({ provider: newProvider, model: '' });
  }

  let providerOptions = $derived(
    availableProviders.map(p => ({ value: p, label: p.charAt(0).toUpperCase() + p.slice(1) }))
  );

  let quantizationOptions = [
    { value: 'none', label: 'None (full precision)' },
    { value: '8bit', label: '8-bit' },
    { value: '4bit', label: '4-bit' },
  ];

  $effect(() => {
    if (!isOllama && value.quantization && value.quantization !== 'none') {
      patch({ quantization: 'none' });
    }
  });
</script>

<div class="grid grid-cols-2 gap-4">
  <Field>
    <Label for="vlm-provider">VLM Provider</Label>
    <Select
      id="vlm-provider"
      options={providerOptions}
      value={provider}
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
    {:else if isOllama && ollamaModels.length > 0}
      <Select
        id="vlm-model"
        options={ollamaModels}
        value={model}
        onchange={(e) => patch({ model: (e.currentTarget as HTMLSelectElement).value })}
        {disabled}
      />
    {:else}
      <Input
        id="vlm-model"
        type="text"
        placeholder={isOllama ? 'No models found, type name' : 'Type model name'}
        value={model}
        onchange={(e) => patch({ model: (e.currentTarget as HTMLInputElement).value })}
        {disabled}
      />
    {/if}
  </Field>

  {#if isOllama}
    <Field>
      <Label for="vlm-quantization">Quantization (Ollama only)</Label>
      <Select
        id="vlm-quantization"
        options={quantizationOptions}
        value={value.quantization || 'none'}
        onchange={(e) => patch({ quantization: (e.currentTarget as HTMLSelectElement).value })}
        {disabled}
      />
    </Field>
  {/if}

  <Field>
    <Label for="grid-rows">Grid Rows</Label>
    <Input
      id="grid-rows" type="number" min="1" max="10"
      value={value.grid_rows}
      onchange={(e) => patch({ grid_rows: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 2 })}
      {disabled}
    />
  </Field>

  <Field>
    <Label for="grid-cols">Grid Columns</Label>
    <Input
      id="grid-cols" type="number" min="1" max="10"
      value={value.grid_cols}
      onchange={(e) => patch({ grid_cols: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 4 })}
      {disabled}
    />
  </Field>

  <Field class="col-span-2">
    <Label for="sampling-rate">Sampling Rate (analyze every N frames)</Label>
    <Input
      id="sampling-rate" type="number" min="1"
      value={value.sampling_rate}
      onchange={(e) => patch({ sampling_rate: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 24 })}
      {disabled}
    />
  </Field>

  <Field class="col-span-2">
    <Label for="vlm-delay">Delay between VLM calls (seconds)</Label>
    <Input
      id="vlm-delay" type="number" min="0" step="0.5"
      value={value.vlm_delay}
      onchange={(e) => patch({ vlm_delay: parseFloat((e.currentTarget as HTMLInputElement).value) || 0 })}
      {disabled}
    />
  </Field>

  <Field class="col-span-2">
    <Label for="vlm-max-retries">Max retries on rate limit</Label>
    <Input
      id="vlm-max-retries" type="number" min="0" max="20"
      value={value.max_retries}
      onchange={(e) => patch({ max_retries: parseInt((e.currentTarget as HTMLInputElement).value, 10) || 3 })}
      {disabled}
    />
  </Field>
</div>
