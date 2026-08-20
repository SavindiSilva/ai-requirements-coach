// Base URL for the FastAPI backend. Configured via VITE_API_BASE_URL; falls
// back to the local dev default (uvicorn app.main:app --reload -> :8000).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export type ApiErrorKind = 'validation' | 'request' | 'network';

// FastAPI's automatic 422 body for a failed Pydantic field validator.
interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
  }
}

function extractDetailMessage(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return (detail as ValidationErrorDetail[])
        .map((d) => d.msg)
        .filter(Boolean)
        .join('; ');
    }
  }
  return 'Request failed.';
}

export async function apiPost<TResponse>(path: string, body: unknown): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      'Could not reach the server. Check that the backend is running.',
      'network',
    );
  }

  if (!response.ok) {
    let parsedBody: unknown = null;
    try {
      parsedBody = await response.json();
    } catch {
      // Non-JSON error body — fall through to the generic message.
    }
    const message = extractDetailMessage(parsedBody);
    const kind: ApiErrorKind = response.status === 422 ? 'validation' : 'request';
    throw new ApiError(message, kind, response.status);
  }

  return response.json() as Promise<TResponse>;
}
