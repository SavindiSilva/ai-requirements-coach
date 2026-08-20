// overall_readiness / criterion scores are floats on a 0-3 scale (see
// app/analysis/schemas.py) — round(sum/4, 2) can produce values like 1.75,
// not just .5 increments, so this keeps 2 decimals only when needed.
export function formatScore(score: number): string {
  return Number.isInteger(score * 10) ? score.toFixed(1) : score.toFixed(2);
}
