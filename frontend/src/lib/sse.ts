import type { LogEvent } from './types';

const SENTINEL_RUN_DONE = '<<RUN_DONE>>';
const SENTINEL_RUN_FAILED = '<<RUN_FAILED>>';

export type LogHandler = (event: LogEvent) => void;
export type DoneHandler = () => void;
export type ErrorHandler = (err: Error) => void;

export function openLogStream(
  url: string,
  onLog: LogHandler,
  onEnd: DoneHandler,
  onError: ErrorHandler,
): () => void {
  const es = new EventSource(url);
  let closed = false;

  function close() {
    if (closed) return;
    closed = true;
    es.close();
  }

  es.addEventListener('log', (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data);
      onLog(data as LogEvent);
    } catch (e) {
      close();
      onError(e as Error);
    }
  });
  es.addEventListener('end', () => {
    close();
    onEnd();
  });
  es.onerror = () => {
    close();
    onError(new Error('SSE stream error'));
  };
  return close;
}
