// Server-side fetch wrappers. The Next.js rewrite in next.config.ts proxies
// /api/v1/* to the FastAPI service on localhost:8000.

const BASE = process.env.COGENCY_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} ${path}: ${body.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export type CaseListItem = {
  id: string;
  case_number: string | null;
  subject: string | null;
  status: string | null;
  priority: string | null;
  contact_id: string | null;
  system_modstamp: string;
  has_runs: boolean;
};

export type CaseDetail = {
  id: string;
  case_number: string | null;
  subject: string | null;
  description: string | null;
  status: string | null;
  priority: string | null;
  origin: string | null;
  contact_id: string | null;
  account_id: string | null;
  custom_fields: Record<string, unknown>;
  created_date: string | null;
  system_modstamp: string;
  contact: {
    id: string;
    first_name: string | null;
    last_name: string | null;
    email: string | null;
    account_id: string | null;
  } | null;
  runs: {
    id: string;
    aop_version_id: string;
    status: string;
    started_at: string;
    ended_at: string | null;
    cost_usd: number;
  }[];
};

export type AOPListItem = {
  id: string;
  name: string;
  description: string | null;
  current_version_id: string | null;
  current_version_number: number | null;
  versions_count: number;
};

export type InboxItem = {
  id: string;
  case_id: string;
  escalation_reason: string;
  recommended_action: Record<string, unknown> | null;
  confidence: number | null;
  status: string;
  sla_deadline: string | null;
  created_at: string;
};

export type RunStep = {
  step_index: number;
  tool_name: string;
  input: unknown;
  output: unknown;
  status: string;
  latency_ms: number | null;
  error: string | null;
};

export type RunSummary = {
  id: string;
  aop_version_id: string;
  case_id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  cost_usd: number;
  token_in: number;
  token_out: number;
  trace_id: string | null;
  steps: RunStep[];
};

export type SyncStatus = {
  connected: boolean;
  last_run_at: string | null;
  last_status: string | null;
  watermark_ts: string | null;
  cases_mirrored: number;
  api_version: string;
};

export const api = {
  listCases: (params: { q?: string; status?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.status) qs.set("status", params.status);
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    return fetchJson<{ items: CaseListItem[]; total: number }>(`/v1/cases?${qs}`);
  },
  getCase: (id: string) => fetchJson<CaseDetail>(`/v1/cases/${id}`),
  listAops: () => fetchJson<{ items: AOPListItem[] }>(`/v1/aops`),
  listInbox: (status: string = "pending") =>
    fetchJson<{ items: InboxItem[] }>(`/v1/inbox?status=${status}`),
  getRun: (id: string) => fetchJson<RunSummary>(`/v1/aop_runs/${id}`),
  syncStatus: () => fetchJson<SyncStatus>(`/v1/integrations/salesforce/sync_status`),
  startRun: (body: { aop_name: string; case_id: string }) =>
    fetchJson<{ workflow_id: string; run_id: string; aop_version_id: string }>(
      `/v1/aop_runs`,
      { method: "POST", body: JSON.stringify(body) },
    ),
};
