<script lang="ts">
  import { api } from '$lib/api';
  import Label from '$lib/components/ui/label.svelte';
  import Field from '$lib/components/ui/field.svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { DEFAULT_AUDIO_CLASSES, DEFAULT_AUDIO_KEYWORDS } from '$lib/types';

  let classes = $state<string[]>([...DEFAULT_AUDIO_CLASSES]);
  let keywords = $state<Record<string, string[]>>({ ...DEFAULT_AUDIO_KEYWORDS });
  let error = $state<string | null>(null);
  let savedMsg = $state<string | null>(null);

  async function load() {
    error = null;
    try {
      const resp = await api.get<{ sections: Record<string, object> }>('/api/config');
      const t = (resp.sections || {}).audio_taxonomy as Record<string, unknown> | undefined;
      if (t) {
        if (Array.isArray(t.classes)) classes = t.classes as string[];
        if (t.keywords && typeof t.keywords === 'object') keywords = t.keywords as Record<string, string[]>;
      }
    } catch (e) {
      error = `Failed to load audio settings: ${(e as Error).message}`;
    }
  }

  $effect(() => {
    load();
  });

  async function save() {
    error = null;
    savedMsg = null;
    try {
      await api.putJson('/api/config/audio_taxonomy', { classes, keywords });
      savedMsg = 'Saved audio settings.';
      setTimeout(() => (savedMsg = null), 2500);
    } catch (e) {
      error = `Failed to save audio settings: ${(e as Error).message}`;
    }
  }

  function keywordsToText(kw: Record<string, string[]>): string {
    return Object.entries(kw).map(([k, v]) => `${k}: ${v.join(', ')}`).join('\n');
  }
  function parseKeywords(text: string): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const line of text.split('\n')) {
      const idx = line.indexOf(':');
      if (idx < 0) continue;
      const k = line.slice(0, idx).trim();
      const vals = line.slice(idx + 1).split(',').map((s) => s.trim()).filter(Boolean);
      if (k && vals.length) out[k] = vals;
    }
    return out;
  }
  function parseList(text: string): string[] {
    return text.split(',').map((s) => s.trim()).filter(Boolean);
  }

  const textareaClass =
    'flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono leading-relaxed ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
</script>

<div class="space-y-3">
  <p class="text-xs text-muted-foreground">
    These values are stored in the database and apply to every analysis. Edit then press Save.
  </p>
  {#if error}<p class="text-sm text-destructive">{error}</p>{/if}
  {#if savedMsg}<p class="text-sm text-emerald-600">{savedMsg}</p>{/if}

  <Field>
    <Label>Event classes (comma-separated)</Label>
    <textarea class={textareaClass} rows={2} value={classes.join(', ')}
      onchange={(e) => (classes = parseList((e.currentTarget as HTMLTextAreaElement).value))}></textarea>
  </Field>
  <Field>
    <Label>Class keywords (one per line: <code>class: kw1, kw2</code>)</Label>
    <textarea class={textareaClass} rows={5} value={keywordsToText(keywords)}
      onchange={(e) => (keywords = parseKeywords((e.currentTarget as HTMLTextAreaElement).value))}></textarea>
  </Field>
  <div>
    <Button type="button" variant="secondary" onclick={save}>Save audio settings</Button>
  </div>
</div>
