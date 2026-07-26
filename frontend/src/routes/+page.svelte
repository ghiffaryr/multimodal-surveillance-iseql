<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '$lib/api';
  import { openLogStream } from '$lib/sse';
  import { APP_NAME, APP_VERSION } from '$lib/app';
  import type {
    AnalysisStartResponse,
    AnalysisStatusResponse,
    AudioConfig,
    Condition,
    Deltas,
    DetectionResult,
    EventTypesResponse,
    LogEvent,
    SchemaResponse,
    VlmConfig,
  } from '$lib/types';

  import AppSidebar from '$lib/components/app-sidebar.svelte';
  import VideoUploader from '$lib/components/video-uploader.svelte';
  import VlmConfigForm from '$lib/components/vlm-config-form.svelte';
  import AudioConfigForm from '$lib/components/audio-config-form.svelte';
  import ConditionSelector from '$lib/components/condition-selector.svelte';
  import EventPicker from '$lib/components/event-picker.svelte';
  import LogConsole from '$lib/components/log-console.svelte';
  import ResultsTable from '$lib/components/results-table.svelte';

  import Card from '$lib/components/ui/card.svelte';
  import CardHeader from '$lib/components/ui/card-header.svelte';
  import CardTitle from '$lib/components/ui/card-title.svelte';
  import CardContent from '$lib/components/ui/card-content.svelte';
  import Button from '$lib/components/ui/button.svelte';
  import Separator from '$lib/components/ui/separator.svelte';
  import { Play, RotateCcw, AlertTriangle, CheckCircle2 } from 'lucide-svelte';

  type AnalysisRecord = {
    id: string;
    video_filename: string;
    condition: string;
    stage: string;
    created_at: string;
  };

  let video = $state<File | null>(null);
  let condition = $state<Condition>('A');
  let availableProviders = $state<string[]>([]);
  let availableAudioProviders = $state<string[]>(['panns', 'huggingface']);
  let vlmConfig = $state<VlmConfig>({
    provider: 'mistral',
    model: '',
    grid_rows: 2,
    grid_cols: 4,
    sampling_rate: 24,
    vlm_delay: 3.0,
    quantization: 'none',
    max_retries: 3,
  });
  let audioConfig = $state<AudioConfig>({
    provider: 'panns',
    model: 'cnn14',
    quantization: 'none',
  });
  let deltas = $state<Deltas>({
    delta_visual_vehicle_escape: 50,
    delta_visual_loitering: 150,
    delta_visual_handoff: 240,
    delta_visual_fight: 60,
    delta_sound_fight: 120,
    delta_sound_gunshot_or_explosion: 60,
    delta_sound_vehicle_escape: 150,
    delta_sound_vehicle_collision: 60,
    delta_audio_visual_proximity: 60,
  });
  let eventTypes = $state<EventTypesResponse>({ A_visual: [], B_sound_only: [], C_sound_visual: [] });
  let selectedEvent = $state<string>('');

  let analysisId = $state<string | null>(null);
  let stage = $state<string>('idle');
  let logs = $state<LogEvent[]>([]);
  let result = $state<DetectionResult | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let detecting = $state(false);

  let previousAnalyses = $state<AnalysisRecord[]>([]);

  let closeSse: (() => void) | null = null;

  async function refreshAnalysisList() {
    try {
      previousAnalyses = await api.get<AnalysisRecord[]>('/api/analysis/list');
    } catch { /* non-fatal */ }
  }

  onMount(async () => {
    try {
      eventTypes = await api.get<EventTypesResponse>('/api/events/types');
    } catch (e) {
      error = `Failed to load event types: ${(e as Error).message}`;
    }
    try {
      const schema = await api.get<SchemaResponse>('/api/schema');
      availableProviders = schema.available_providers || [];
      availableAudioProviders = schema.available_audio_providers || ['panns', 'huggingface'];
    } catch { /* non-fatal */ }
    await refreshAnalysisList();
  });

  $effect(() => {
    const list =
      condition === 'A'
        ? eventTypes.A_visual
        : condition === 'B'
          ? eventTypes.B_sound_only
          : eventTypes.C_sound_visual;
    if (list.length > 0 && !list.some((e) => e.id === selectedEvent)) {
      selectedEvent = list[0].id;
    }
  });

  function appendLog(stage: string, message: string) {
    logs = [...logs, { ts: Date.now() / 1000, stage, message }];
  }
  function clearLogs() { logs = []; }
  function reset() {
    if (closeSse) { closeSse(); closeSse = null; }
    analysisId = null;
    stage = 'idle';
    result = null;
    error = null;
    logs = [];
  }

  function loadAnalysis(item: AnalysisRecord) {
    reset();
    analysisId = item.id;
    condition = item.condition as Condition;
    stage = item.stage;
    appendLog('info', `>>> Loaded previous analysis ${item.id} (condition ${item.condition}, stage ${item.stage})`);
    if (item.stage !== 'done') {
      appendLog('warning', `Analysis is not complete (stage: ${item.stage}). Detection may not be available.`);
    }
  }

  async function startAnalysis() {
    if (!video) {
      error = 'Please choose a video file first.';
      return;
    }
    if (analysisId) { reset(); }

    busy = true;
    error = null;
    appendLog('queued', `>>> Submitting ${video.name} (${(video.size / 1024 / 1024).toFixed(1)} MB)  [condition ${condition}]`);

    const form = new FormData();
    form.append('video', video);
    form.append('condition', condition);
    form.append('vlm_provider', vlmConfig.provider);
    form.append('model', vlmConfig.model);
    form.append('grid_rows', String(vlmConfig.grid_rows));
    form.append('grid_cols', String(vlmConfig.grid_cols));
    form.append('sampling_rate', String(vlmConfig.sampling_rate));
    form.append('vlm_delay', String(vlmConfig.vlm_delay));
    form.append('vlm_quantization', vlmConfig.quantization || 'none');
    form.append('max_retries', String(vlmConfig.max_retries));
    form.append('audio_provider', audioConfig.provider);
    form.append('audio_model', audioConfig.model);
    form.append('audio_quantization', audioConfig.quantization);

    try {
      const resp = await api.postForm<AnalysisStartResponse>('/api/analysis/start', form);
      analysisId = resp.analysis_id;
      stage = resp.stage;
      appendLog('queued', `analysis_id = ${analysisId} (condition ${resp.condition})`);
      await refreshAnalysisList();

      closeSse = openLogStream(
        `/api/analysis/${analysisId}/logs`,
        (evt) => {
          appendLog(evt.stage, evt.message);
          if (evt.stage && evt.stage !== 'queued' && evt.stage !== 'done' && evt.stage !== 'failed') {
            stage = evt.stage;
          }
        },
        async () => {
          stage = 'done';
          busy = false;
          appendLog('done', '>>> Run finished, ready to detect.');
          try {
            const s = await api.get<AnalysisStatusResponse>(`/api/analysis/${analysisId}/status`);
            stage = s.stage;
          } catch { /* ignore */ }
          await refreshAnalysisList();
        },
        (err) => {
          stage = 'failed';
          busy = false;
          appendLog('failed', `SSE error: ${err.message}`);
          refreshAnalysisList();
        }
      );
    } catch (e) {
      busy = false;
      if (e instanceof ApiError) {
        error = `${e.status}: ${typeof e.body === 'string' ? e.body : JSON.stringify(e.body)}`;
      } else {
        error = (e as Error).message;
      }
      appendLog('failed', `Start failed: ${error}`);
    }
  }

  async function runDetection() {
    if (!analysisId) {
      error = 'Run an analysis first.';
      return;
    }
    if (stage !== 'done') {
      error = `Analysis is not done yet (current stage: ${stage}).`;
      return;
    }
    detecting = true;
    result = null;
    error = null;
    appendLog('detection', `>>> Running '${selectedEvent}' (condition ${condition})`);

    try {
      const r = await api.post<DetectionResult>(
        `/api/analysis/${analysisId}/detect?event_type=${encodeURIComponent(selectedEvent)}`
      );
      result = r;
      appendLog('detection', `<<< ${r.rows.length} row(s) for '${selectedEvent}'.`);
      detecting = false;
    } catch (e) {
      detecting = false;
      if (e instanceof ApiError) {
        error = `${e.status}: ${typeof e.body === 'string' ? e.body : JSON.stringify(e.body)}`;
      } else {
        error = (e as Error).message;
      }
      appendLog('failed', `Detection failed: ${error}`);
    }
  }

  const canStart = $derived(video !== null && !busy);
  const canDetect = $derived(analysisId !== null && stage === 'done' && !detecting);
  const canReset = $derived(!busy || stage === 'done' || stage === 'failed');
  const audioLabel = $derived('Audio Model');
  const conditionLabel = $derived(
    condition === 'A'
      ? 'A · Visual only (VLM + ISEQL)'
      : condition === 'B'
        ? `B · Sound only (${audioLabel} + ISEQL)`
        : `C · Full multimodal (VLM + ${audioLabel} + ISEQL)`,
  );
</script>

<div class="flex h-screen w-screen overflow-hidden bg-background text-foreground">
  <AppSidebar currentStage={stage} currentEvent={selectedEvent} {previousAnalyses} {analysisId} {loadAnalysis} />

  <main class="flex flex-1 flex-col gap-4 overflow-hidden p-4">
    <div class="grid flex-1 grid-cols-12 gap-4 overflow-hidden">
      <section class="col-span-5 flex flex-col gap-4 overflow-y-auto pr-1">
        <Card>
          <CardHeader><CardTitle>1. Video</CardTitle></CardHeader>
          <CardContent>
            <VideoUploader file={video} onChange={(f) => (video = f)} disabled={busy} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>2. Ablation condition</CardTitle></CardHeader>
          <CardContent>
            <ConditionSelector
              value={condition}
              onChange={(c) => (condition = c)}
              disabled={busy}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>3. VLM (conditions A and C)</CardTitle></CardHeader>
          <CardContent>
            <VlmConfigForm
              value={vlmConfig}
              onChange={(v) => (vlmConfig = v)}
              disabled={busy || condition === 'B'}
              availableProviders={availableProviders}
            />
            {#if condition === 'B'}
              <p class="mt-2 text-xs text-muted-foreground">
                Condition B does not use the VLM. These settings are ignored.
              </p>
            {/if}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>4. Audio (conditions B and C)</CardTitle></CardHeader>
          <CardContent>
            <AudioConfigForm
              value={audioConfig}
              onChange={(v) => (audioConfig = v)}
              disabled={busy || condition === 'A'}
              availableProviders={availableAudioProviders}
            />
            {#if condition === 'A'}
              <p class="mt-2 text-xs text-muted-foreground">
                Condition A does not use audio. These settings are ignored.
              </p>
            {/if}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>5. Event + deltas</CardTitle></CardHeader>
          <CardContent>
            <EventPicker
              condition={condition}
              aEvents={eventTypes.A_visual}
              bEvents={eventTypes.B_sound_only}
              cEvents={eventTypes.C_sound_visual}
              selected={selectedEvent}
              onChangeSelected={(id) => (selectedEvent = id)}
              deltas={deltas}
              onChangeDeltas={(d) => (deltas = d)}
              disabled={busy}
            />
          </CardContent>
        </Card>

        <div class="flex gap-2">
          <Button class="flex-1" onclick={startAnalysis} disabled={!canStart}>
            <Play class="size-4" /> Start analysis
          </Button>
          <Button variant="outline" onclick={runDetection} disabled={!canDetect}>
            Run detection
          </Button>
          <Button variant="ghost" onclick={reset} disabled={!canReset}>
            <RotateCcw class="size-4" /> Reset
          </Button>
        </div>

        {#if error}
          <div class="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle class="size-4 shrink-0" />
            <p class="break-all">{error}</p>
          </div>
        {/if}
        {#if stage === 'done' && !error}
          <div class="flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300">
            <CheckCircle2 class="size-4" />
            Analysis complete - ready to detect.
          </div>
        {/if}
      </section>

      <section class="col-span-7 flex min-h-0 flex-col gap-4">
        <div class="min-h-0 flex-1">
          <LogConsole entries={logs} onClear={clearLogs} />
        </div>
        <div class="min-h-0 flex-1">
          <ResultsTable result={result} running={detecting} error={null} />
        </div>
      </section>
    </div>
  </main>
</div>
