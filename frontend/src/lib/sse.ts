import type { LogEvent } from './types';

export type LogHandler = (event: LogEvent) => void;
export type StageHandler = (stage: string) => void;
export type DoneHandler = () => void;
export type ErrorHandler = (err: Error) => void;

export function openLogStream(
  url: string,
  onLog: LogHandler,
  onEnd: DoneHandler,
  onError: ErrorHandler
): () => void {
  const es = new EventSource(url);
  es.addEventListener('log', (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data);
      onLog(data as LogEvent);
    } catch (e) {
      onError(e as Error);
    }
  });
  es.addEventListener('end', () => {
    es.close();
    onEnd();
  });
  es.onerror = (e) => {
    es.close();
    onError(new Error('SSE stream error'));
  };
  return () => es.close();
}
