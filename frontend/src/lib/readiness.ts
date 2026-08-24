// Mirrors app/core/config.py::Settings.readiness_pass_threshold's default
// (2) — the "score >= this counts as ready" bar used for AnalysisResultView's
// Ready/Needs Clarification label. Pre-coaching, this is the only readiness
// signal available at all. Post-coaching, prefer the real coaching
// stop_reason instead (lib/aiReviewStatus.ts) — it's the more accurate
// signal once one exists, so this threshold is intentionally NOT reused for
// any screen showing a ticket that has actually been through coaching.
export const READINESS_PASS_THRESHOLD = 2;
