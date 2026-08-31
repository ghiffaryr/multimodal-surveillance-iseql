// Shared state for the guided highlight tour.

export type TourStep = {
  target: string;
  title: string;
  body: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  action?: () => void;
};

export const tour = $state<{
  steps: TourStep[];
  active: boolean;
  index: number;
  key: string;
}>({ steps: [], active: false, index: 0, key: 'default' });

export function startTour(steps: TourStep[], key = 'default') {
  tour.steps = steps;
  tour.index = 0;
  tour.key = key;
  tour.active = true;
}

export function tourNext() {
  if (tour.index < tour.steps.length - 1) tour.index += 1;
  else tourEnd();
}

export function tourPrev() {
  if (tour.index > 0) tour.index -= 1;
}

export function tourEnd() {
  tour.active = false;
  markTourSeen(tour.key);
}

// The steps for the currently-mounted context. Pages register their steps on
// mount so the floating "Guide" button can re-run the tour on demand.
let registered: TourStep[] = [];
let registeredKey = 'default';

export function registerTourSteps(steps: TourStep[], key = 'default') {
  registered = steps;
  registeredKey = key;
}

export function restartTour() {
  if (registered.length) startTour(registered, registeredKey);
}

// Persist whether a given tour has been completed at least once (used to
// auto-launch on first visit). The delete/right-click hints are intentionally
// NOT gated on these flags so they reappear for every user on a shared device.
export function hasSeenTour(key = 'default'): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(`tour-seen:${key}`) === '1';
}

export function markTourSeen(key = 'default') {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(`tour-seen:${key}`, '1');
}
