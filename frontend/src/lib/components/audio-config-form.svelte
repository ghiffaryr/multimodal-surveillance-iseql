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
    patch({ provider: newProvider, model: DEFAULT_AUDIO_MODELS[newProvider] || '' });
  }

  let providerOptions = $derived(
    availableProviders.map(p => ({
      value: p,
      label: PROVIDER_LABELS[p] || p,
    }))
  );

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
