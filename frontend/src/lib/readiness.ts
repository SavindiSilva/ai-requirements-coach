// Mirrors app/core/config.py::Settings.readiness_pass_threshold's default
// (2) — the same "score >= this counts as ready" bar used across the app
// (AnalysisResultView's Ready/Needs Clarification label, and the
// Dashboard's Tickets Ready count) so the threshold lives in one place
// instead of being duplicated as a magic number at each use site.
export const READINESS_PASS_THRESHOLD = 2;
