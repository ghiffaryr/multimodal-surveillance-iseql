<script lang="ts">
  import Input from '$lib/components/ui/input.svelte';
  import Label from '$lib/components/ui/label.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import Field from '$lib/components/ui/field.svelte';

  export type AudioConfig = {
    provider: string;
    model: string;
    quantization: string;
  };

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
    // Auto-fill default model when provider changes
    if (provider === 'huggingface' && !model) {
      patch({ model: 'Qwen/Qwen2-Audio-7B-Instruct' });
    } else if (provider === 'panns' && !model) {
      patch({ model: 'cnn14' });
    }
  });

  function handleProviderChange(e: Event) {
    const newProvider = (e.currentTarget as HTMLSelectElement).value;
    const defaultModel = newProvider === 'huggingface' ? 'Qwen/Qwen2-Audio-7B-Instruct' : 'cnn14';
    patch({ provider: newProvider, model: defaultModel });
  }

  let providerOptions = $derived(
    availableProviders.map(p => ({
      value: p,
      label: p === 'panns' ? 'PANNs CNN14 (local)' : 'HuggingFace LALM',
    }))
  );

  let quantizationOptions = [
    { value: 'none', label: 'None (full precision)' },
    { value: '8bit', label: '8-bit' },
    { value: '4bit', label: '4-bit (recommended)' },
  ];
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
        options={quantizationOptions}
        value={value.quantization}
        onchange={(e) => patch({ quantization: (e.currentTarget as HTMLSelectElement).value })}
        {disabled}
      />
    </Field>
  {/if}
</div>
