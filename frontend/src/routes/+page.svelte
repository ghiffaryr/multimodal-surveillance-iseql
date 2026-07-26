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
  import { Play, AlertTriangle, Square } from 'lucide-svelte';

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
    vlm_delay: 3.0,
    quantization: 'none',
    max_retries: 10,
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

  let analysisId = $state<string | null>(null);
  let stage = $state<string>('idle');
  let logs = $state<LogEvent[]>([]);
  let result = $state<DetectionResult | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let detecting = $state(false);

  let previousAnalyses = $state<AnalysisRecord[]>([]);
  let detectedFps = $state(0);
  let analysisDone = $state(false);
  let lastConfigSnapshot = $state('');

  let closeSse: (() => void) | null = null;

  function takeConfigSnapshot(): string {
    return JSON.stringify({
      condition, vlm_provider: vlmConfig.provider, vlm_model: vlmConfig.model,
      grid_rows: vlmConfig.grid_rows, grid_cols: vlmConfig.grid_cols,
      audio_provider: audioConfig.provider, audio_model: audioConfig.model,
    });
  }

  function onlyDeltasChanged(): boolean {
    return takeConfigSnapshot() === lastConfigSnapshot && analysisDone && !!analysisId;
  }

  // Reset restart shortcut when non-delta config changes
  $effect(() => {
    if (stage !== 'done') return;
    const snap = takeConfigSnapshot();
    if (snap && lastConfigSnapshot) {
      analysisDone = snap === lastConfigSnapshot;
    }
  });

  async function refreshAnalysisList() {
    try {
      previousAnalyses = await api.get<AnalysisRecord[]>('/api/analysis/list');
    } catch { /* non-fatal */ }
  }

  async function deleteAnalysis(id: string) {
    try {
      await api.post(`/api/analysis/${id}/delete`);
    } catch { /* non-fatal */ }
    if (analysisId === id) reset();
    await refreshAnalysisList();
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
    analysisDone = false;
  }

  function getAllEventIds(): string[] {
    if (condition === 'A') return eventTypes.A_visual.map(e => e.id);
    if (condition === 'B') return eventTypes.B_sound_only.map(e => e.id);
    return eventTypes.C_sound_visual.map(e => e.id);
  }

  function loadAnalysis(item: AnalysisRecord) {
    reset();
    analysisId = item.id;
    condition = item.condition as Condition;
    stage = item.stage;
    appendLog('info', `>>> Loaded previous analysis ${item.id} (condition ${item.condition}, stage ${item.stage})`);
    if (item.stage === 'done') {
      lastConfigSnapshot = takeConfigSnapshot();
      analysisDone = true;
      setTimeout(() => runAllDetections(), 300);
    } else {
      appendLog('warning', `Analysis is not complete (stage: ${item.stage}). Detection may not be available.`);
    }
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
      detectedFps = resp.sampling_rate;
      lastConfigSnapshot = takeConfigSnapshot();
      analysisDone = false;
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
          analysisDone = true;
          appendLog('done', '>>> Run finished, running detection on all events...');
          try {
            const s = await api.get<AnalysisStatusResponse>(`/api/analysis/${analysisId}/status`);
            stage = s.stage;
          } catch { /* ignore */ }
          await refreshAnalysisList();
          runAllDetections();
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

  async function runAllDetections() {
    if (!analysisId || stage !== 'done') return;
    const events = getAllEventIds();
    if (events.length === 0) return;

    detecting = true;
    result = null;
    error = null;
    appendLog('detection', `>>> Auto-detecting all ${events.length} events for condition ${condition}`);

    const allRows: Array<Record<string, unknown>> = [];
    for (const evt of events) {
      try {
        const r = await api.post<DetectionResult>(
          `/api/analysis/${analysisId}/detect?event_type=${encodeURIComponent(evt)}`
        );
        for (const row of r.rows) {
          allRows.push({ Event: evt, ...row });
        }
      } catch (e) {
        appendLog('failed', `Detection query failed for '${evt}': ${(e as Error).message}`);
      }
    }
    result = { analysis_id: analysisId!, event_type: 'all', condition: condition, rows: allRows };
    appendLog('detection', `<<< ${allRows.length} total row(s) across ${events.length} events.`);
    detecting = false;
  }

  const canStart = $derived(video !== null && !busy);
  const canStop = $derived(busy);

  function triggerAnalysis() {
    if (onlyDeltasChanged()) {
      runAllDetections();
    } else {
      startAnalysis();
    }
  }

  async function stopAnalysis() {
    if (!analysisId) return;
    try {
      await api.post(`/api/analysis/${analysisId}/stop`);
      busy = false;
      appendLog('info', '>>> Analysis stopped by user');
    } catch (e) {
      appendLog('failed', `Stop request failed: ${(e as Error).message}`);
    }
  }
</script>

<div class="flex h-screen w-screen overflow-hidden bg-background text-foreground">
  <AppSidebar currentStage={stage} {previousAnalyses} {analysisId} {loadAnalysis}
    onDeleteAnalysis={deleteAnalysis} onResetDb={reset} />

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
              onChange={(c) => { condition = c; }}
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
              {detectedFps}
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
          <CardHeader><CardTitle>5. Deltas</CardTitle></CardHeader>
          <CardContent>
            <EventPicker
              condition={condition}
              deltas={deltas}
              onChangeDeltas={(d) => (deltas = d)}
              disabled={busy}
            />
          </CardContent>
        </Card>

        <div class="flex gap-2">
          {#if canStop}
            <Button class="flex-1" variant="destructive" onclick={stopAnalysis}>
              <Square class="size-4" /> Stop analysis
            </Button>
          {:else if onlyDeltasChanged()}
            <Button class="flex-1" variant="secondary" onclick={triggerAnalysis}>
              <Play class="size-4" /> Re-run detection (deltas only)
            </Button>
          {:else if analysisDone && canStart}
            <Button class="flex-1" onclick={triggerAnalysis}>
              <Play class="size-4" /> Restart analysis
            </Button>
          {:else}
            <Button class="flex-1" onclick={triggerAnalysis} disabled={!canStart}>
              <Play class="size-4" /> Start analysis
            </Button>
          {/if}
        </div>

        {#if error}
          <div class="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle class="size-4 shrink-0" />
            <p class="break-all">{error}</p>
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
