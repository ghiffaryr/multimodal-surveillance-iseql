// Promise-backed confirmation dialog state. Replaces the native `confirm()`
// (which is unreliable/blocked in some mobile browsers and PWA/standalone
// contexts) with a focused in-app modal.

export type ConfirmOptions = {
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
};

type ConfirmState = {
  open: boolean;
  message: string;
  title: string;
  confirmLabel: string;
  cancelLabel: string;
};

export const confirmState = $state<ConfirmState>({
  open: false,
  message: '',
  title: 'Confirm',
  confirmLabel: 'Delete',
  cancelLabel: 'Cancel',
});

let resolver: ((v: boolean) => void) | null = null;

export function askConfirm(message: string, opts: ConfirmOptions = {}): Promise<boolean> {
  confirmState.message = message;
  confirmState.title = opts.title ?? 'Confirm';
  confirmState.confirmLabel = opts.confirmLabel ?? 'Delete';
  confirmState.cancelLabel = opts.cancelLabel ?? 'Cancel';
  confirmState.open = true;
  return new Promise((resolve) => {
    resolver = resolve;
  });
}

export function resolveConfirm(v: boolean) {
  confirmState.open = false;
  const r = resolver;
  resolver = null;
  r?.(v);
}
