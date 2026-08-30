// Shared transient UI state for the ISEQL timeline, persisted across the
// Text/Timeline editor toggle so zoom (and other view settings) don't reset.
export const timelineUi = $state({
  scale: 4,
});
