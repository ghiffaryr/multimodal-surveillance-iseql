<script lang="ts">
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import type { AudioConfig } from '$lib/types';
  import { selectValue } from '$lib/dom-helpers';

  const DEFAULT_AUDIO_MODELS: Record<string, string> = {
    huggingface: 'Qwen/Qwen2-Audio-7B-Instruct',
    panns: 'cnn14',
  };
  const PROVIDER_LABELS: Record<string, string> = {
    panns: 'PANNs CNN14 (local)',
    huggingface: 'HuggingFace LALM',
  };
  const DEFAULT_CONFIGS: Record<string, { window: number; hop: number }> = {
    huggingface: { window: 5.0, hop: 2.5 },
    panns: { window: 2.5, hop: 1.25 },
  };
  const WINDOW_HOP_OPTIONS = [
    { window: 1.0, hop: 1.00, label: '1.0s / 1.00s' },
    { window: 1.0, hop: 0.50, label: '1.0s / 0.50s' },
    { window: 2.5, hop: 2.50, label: '2.5s / 2.50s' },
    { window: 2.5, hop: 1.25, label: '2.5s / 1.25s' },
    { window: 5.0, hop: 5.00, label: '5.0s / 5.00s' },
    { window: 5.0, hop: 2.50, label: '5.0s / 2.50s' },
    { window: 10.0, hop: 10.00, label: '10.0s / 10.00s' },
    { window: 10.0, hop: 5.00, label: '10.0s / 5.00s' },
  ];

  const QUANTIZATION_OPTIONS = [
    { value: 'none', label: 'None (full precision)' },
    { value: '8bit', label: '8-bit' },
    { value: '4bit', label: '4-bit (recommended)' },
  ];

  type Props = {
    value: AudioConfig;
    onChange: (v: AudioConfig) => void;
    disabled?: boolean;
    availableProviders?: string[];
  };
  let { value = $bindable(), onChange, disabled = false, availableProviders = ['panns', 'huggingface'] }: Props = $props();

  let provider = $derived(value.provider);
  let model = $derived(value.model);
  let isHuggingface = $derived(provider === 'huggingface');

  function patch(p: Partial<AudioConfig>) {
    onChange({ ...value, ...p });
  }

  $effect(() => {
    if (availableProviders.length > 0 && !provider) {
      patch({ provider: availableProviders[0], model: '', quantization: 'none' });
    }
  });

  $effect(() => {
    if (provider === 'huggingface' && !model) {
      patch({ model: DEFAULT_AUDIO_MODELS.huggingface });
    } else if (provider === 'panns' && !model) {
      patch({ model: DEFAULT_AUDIO_MODELS.panns });
    }
  });

  function handleProviderChange(e: Event) {
    const newProvider = selectValue(e);
    const cfg = DEFAULT_CONFIGS[newProvider] || DEFAULT_CONFIGS.panns;
    patch({ provider: newProvider, model: DEFAULT_AUDIO_MODELS[newProvider] || '', window: cfg.window, hop: cfg.hop });
  }

  let providerOptions = $derived(
    availableProviders.map(p => ({
      value: p,
      label: PROVIDER_LABELS[p] || p,
    }))
  );

  let windowHopOptions = $derived(
    WINDOW_HOP_OPTIONS.map(c => ({ value: c.label, label: c.label }))
  );

  let windowHopLabel = $derived(
    WINDOW_HOP_OPTIONS.find(c => c.window === value.window && c.hop === value.hop)?.label ?? '2.5s / 1.25s'
  );

  function handleWindowHopChange(e: Event) {
    const label = selectValue(e);
    const cfg = WINDOW_HOP_OPTIONS.find(c => c.label === label);
    if (cfg) patch({ window: cfg.window, hop: cfg.hop });
  }

</script>

<div class="grid grid-cols-2 gap-4">
  <Field>
    <Label for="audio-provider">Audio Provider</Label>
    <Select
      id="audio-provider"
      options={providerOptions}
      value={provider}
      onchange={handleProviderChange}
      {disabled}
    />
  </Field>

  <Field>
    <Label for="audio-model">Model</Label>
    {#if isHuggingface}
      <Input
        id="audio-model"
        type="text"
        placeholder="Qwen/Qwen2-Audio-7B-Instruct"
        value={model}
        onchange={(e) => patch({ model: (e.currentTarget as HTMLInputElement).value })}
        {disabled}
      />
    {:else}
      <div class="flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
        PANNs CNN14 (fixed)
      </div>
    {/if}
  </Field>

  <Field>
    <Label for="audio-window-hop">Window / Hop</Label>
    <Select
      id="audio-window-hop"
      options={windowHopOptions}
      value={windowHopLabel}
      onchange={handleWindowHopChange}
      {disabled}
    />
  </Field>

  {#if isHuggingface}
    <Field class="col-span-2">
      <Label for="audio-quantization">Quantization</Label>
      <Select
        id="audio-quantization"
        options={QUANTIZATION_OPTIONS}
        value={value.quantization}
        onchange={(e) => patch({ quantization: (e.currentTarget as HTMLSelectElement).value })}
        {disabled}
      />
    </Field>
  {/if}
</div>
