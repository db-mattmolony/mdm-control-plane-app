import type {
  AuditRow,
  Bootstrap,
  Coverage,
  ReferenceDetail,
  Row,
  ValidateResult,
} from "./types";

// Demo role override ("view as"). Sent on every request so the backend can gate
// admin actions the same way UC groups will in production.
let viewAsRole: string | null = null;
export function setViewAsRole(role: string | null) {
  viewAsRole = role;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (viewAsRole) headers["X-View-As-Role"] = viewAsRole;
  const res = await fetch(path, { ...init, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok && res.status !== 422) {
    const detail = (body && (body.detail || body.error)) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return body as T;
}

export interface WriteResult {
  ok: boolean;
  row?: Row;
  errors?: string[];
  problems?: { row: number; errors: string[] }[];
  committed?: number;
}

export const api = {
  bootstrap: () => req<Bootstrap>("/api/bootstrap"),
  list: () => req<{ rows: Row[]; coverage: Coverage }>("/api/authorisations"),
  validate: (values: Record<string, any>, pk_value?: number | null) =>
    req<ValidateResult>("/api/validate", {
      method: "POST",
      body: JSON.stringify({ values, pk_value: pk_value ?? null }),
    }),
  create: (values: Record<string, any>) =>
    req<WriteResult>("/api/authorisations", {
      method: "POST",
      body: JSON.stringify({ values }),
    }),
  update: (pk: number, values: Record<string, any>) =>
    req<WriteResult>(`/api/authorisations/${pk}`, {
      method: "PUT",
      body: JSON.stringify({ values }),
    }),
  retire: (pk: number) =>
    req<WriteResult>(`/api/authorisations/${pk}/retire`, { method: "POST" }),
  audit: () => req<{ rows: AuditRow[] }>("/api/audit"),
  reference: (key: string) => req<ReferenceDetail>(`/api/reference/${key}`),
  addReference: (key: string, data: Record<string, any>) =>
    req<WriteResult>(`/api/reference/${key}`, {
      method: "POST",
      body: JSON.stringify({ data }),
    }),
  updateReference: (key: string, id: number, data: Record<string, any>) =>
    req<WriteResult>(`/api/reference/${key}/${id}`, {
      method: "PUT",
      body: JSON.stringify({ data }),
    }),
  bulkValidate: (rows: Record<string, any>[]) =>
    req<{ valid: number; total: number; problems: { row: number; errors: string[] }[]; expected_columns: string[] }>(
      "/api/bulk/validate",
      { method: "POST", body: JSON.stringify({ rows }) }
    ),
  bulkCommit: (rows: Record<string, any>[]) =>
    req<WriteResult>("/api/bulk/commit", {
      method: "POST",
      body: JSON.stringify({ rows }),
    }),
};
