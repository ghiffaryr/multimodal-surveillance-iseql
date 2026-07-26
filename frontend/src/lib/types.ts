export type Condition = 'A' | 'B' | 'C';

export type AnalysisStage =
  | 'queued'
  | 'vlm'
  | 'interval'
  | 'sound'
  | 'detection'
  | 'done'
  | 'failed';

export interface LogEvent {
  ts: number;
  stage: AnalysisStage | string;
  message: string;
  [k: string]: unknown;
}

export interface AnalysisStartRequest {
  condition: Condition;
  vlm_provider: string;
  model: string;
  grid_rows: number;
  grid_cols: number;
  sampling_rate: number;
  rho_handoff: number;
}

export interface AnalysisStartResponse {
  analysis_id: string;
  condition: Condition;
  stage: AnalysisStage;
}

export interface AnalysisStatusResponse {
  id: string;
  condition: Condition;
  stage: AnalysisStage;
  counters: Record<string, number>;
}

export interface EventTypeInfo {
  id: string;
  label: string;
  delta_param: string | null;
  condition: Condition;
  requires_cpp: boolean;
}

export interface EventTypesResponse {
  A_visual: EventTypeInfo[];
  B_sound_only: EventTypeInfo[];
  C_sound_visual: EventTypeInfo[];
}

export interface SchemaResponse {
  app: string;
  version: string;
  conditions: Condition[];
  available_providers: string[];
  available_audio_providers: string[];
  tables: Record<string, string>;
  events: {
    A_visual: string[];
    B_sound_only: string[];
    C_sound_visual: string[];
  };
}

export interface DetectionResult {
  analysis_id: string;
  event_type: string;
  condition: Condition;
  rows: Array<Record<string, unknown>>;
}
