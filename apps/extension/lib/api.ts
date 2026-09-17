// Backend client. The base URL is configurable in settings (chrome.storage.local)
// so writers can point at a local dev server or the hosted backend.

import type {
  ClassifyResponse,
  ContentTypeOption,
  EvaluationRequest,
  EvaluationResult,
  ProvidersResponse,
  WorkflowState,
} from './types';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';
const STORAGE_KEY = 'jalebi.backendUrl';
const TOKEN_KEY = 'jalebi.token';

export async function getBackendUrl(): Promise<string> {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return (stored[STORAGE_KEY] as string) || DEFAULT_BASE_URL;
}

export async function setBackendUrl(url: string): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: url.replace(/\/$/, '') });
}

export async function getToken(): Promise<string> {
  const stored = await chrome.storage.local.get(TOKEN_KEY);
  return (stored[TOKEN_KEY] as string) || '';
}

async function setToken(token: string): Promise<void> {
  await chrome.storage.local.set({ [TOKEN_KEY]: token });
}

export async function logout(): Promise<void> {
  await chrome.storage.local.remove(TOKEN_KEY);
}

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  role: string;
}

/** Email + shared-secret sign-in. Stores the returned token. */
export async function login(email: string, secret: string): Promise<AuthUser> {
  const res = await request<{ access_token: string; user: AuthUser }>(
    '/api/auth/dev-login',
    { method: 'POST', body: JSON.stringify({ email, secret }) },
  );
  await setToken(res.access_token);
  return res.user;
}

export function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>('/api/auth/me');
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getBackendUrl();
  const token = await getToken();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = formatDetail(body.detail);
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

/** FastAPI returns `detail` as a string for HTTPException but as an array of
 *  validation objects for a 422. Rendering that array directly throws
 *  "Objects are not valid as a React child" and blanks the panel. */
export function __formatDetailForTest(detail: unknown): string {
  return formatDetail(detail);
}

function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (typeof d === 'string') return d;
        const item = d as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(item.loc)
          ? item.loc.filter((p) => p !== 'body').join('.')
          : '';
        return field && item.msg ? `${field}: ${item.msg}` : item.msg || '';
      })
      .filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return 'Request failed.';
  }
}

export function fetchContentTypes(): Promise<ContentTypeOption[]> {
  return request<ContentTypeOption[]>('/api/content-types');
}

export function fetchProviders(): Promise<ProvidersResponse> {
  return request<ProvidersResponse>('/api/providers');
}

export function classifyContentType(
  text: string,
  title?: string | null,
): Promise<ClassifyResponse> {
  return request<ClassifyResponse>('/api/classify', {
    method: 'POST',
    body: JSON.stringify({ text, title: title || '' }),
  });
}

export function checkText(
  text: string,
  language = 'en-US',
): Promise<import('./inline/types').CheckResponse> {
  return request('/api/check', {
    method: 'POST',
    body: JSON.stringify({ text, language }),
  });
}

export function rewriteText(
  text: string,
  goal = 'clarity',
  context = '',
): Promise<{ options: string[]; engine: string }> {
  return request('/api/rewrite', {
    method: 'POST',
    body: JSON.stringify({ text, goal, context }),
  });
}

export function evaluate(req: EvaluationRequest): Promise<EvaluationResult> {
  return request<EvaluationResult>('/api/evaluate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

// ── Production loop (TIES SOP §3) ────────────────────────────────────────────

export function fetchWorkflow(docId: string): Promise<WorkflowState> {
  return request<WorkflowState>(
    `/api/documents/${encodeURIComponent(docId)}/workflow`,
  );
}

export function transitionDocument(
  docId: string,
  status: string,
  opts: { reason?: string; override_reason?: string } = {},
): Promise<WorkflowState & { ok: boolean }> {
  return request(`/api/documents/${encodeURIComponent(docId)}/status`, {
    method: 'PUT',
    body: JSON.stringify({
      status,
      reason: opts.reason || '',
      override_reason: opts.override_reason || '',
    }),
  });
}

export function assignDocument(
  docId: string,
  brief: {
    assigned_to: string;
    editor?: string;
    word_min?: number | null;
    word_max?: number | null;
  },
): Promise<WorkflowState & { ok: boolean }> {
  return request(`/api/documents/${encodeURIComponent(docId)}/assign`, {
    method: 'PUT',
    body: JSON.stringify(brief),
  });
}

export function recordIntegrity(
  docId: string,
  aiPercent: number,
  plagiarismPercent: number,
): Promise<{ ok: boolean; passed: boolean; breaches: string[] }> {
  return request(`/api/documents/${encodeURIComponent(docId)}/integrity`, {
    method: 'PUT',
    body: JSON.stringify({
      ai_percent: aiPercent,
      plagiarism_percent: plagiarismPercent,
    }),
  });
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request('/api/health');
    return true;
  } catch {
    return false;
  }
}
