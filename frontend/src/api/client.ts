import type {
  Analysis,
  DateMessage,
  DateSession,
  DemoPayload,
  NewParticipant,
  Participant,
  PublicSettings,
  Ranking,
  Run,
} from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "";

/** FastAPI validation errors arrive as a list of {msg}; flatten them for display. */
function describeError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => String((d as { msg?: string }).msg ?? JSON.stringify(d)).replace(/^Value error, /, ""))
      .join(" ");
  }
  return JSON.stringify(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      /* ignore */
    }
    throw new Error(describeError(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; llm_configured: boolean }>("/api/health"),
  settings: () => request<PublicSettings>("/api/settings"),
  participants: {
    list: (page = 1, pageSize = 50, synthetic?: boolean) =>
      request<{ items: Participant[]; total: number }>(
        `/api/participants?page=${page}&page_size=${pageSize}` +
          (synthetic === undefined ? "" : `&synthetic=${synthetic}`),
      ),
    get: (id: number) => request<Participant>(`/api/participants/${id}`),
    /** Reads both profiles and analyzes the person in one call. */
    create: (body: NewParticipant) =>
      request<Participant>("/api/participants", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    remove: (id: number) =>
      request<void>(`/api/participants/${id}`, { method: "DELETE" }),
    refresh: (id: number) =>
      request<Participant>(`/api/participants/${id}/refresh`, { method: "POST" }),
    analyze: (id: number) =>
      request<Analysis>(`/api/participants/${id}/analyze`, { method: "POST" }),
    analysis: (id: number) =>
      request<Analysis>(`/api/participants/${id}/analysis`),
  },
  runs: {
    list: () => request<Run[]>("/api/runs"),
    create: (body: Record<string, unknown>) =>
      request<Run>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
    get: (id: number) => request<Run>(`/api/runs/${id}`),
    start: (id: number) =>
      request<Run>(`/api/runs/${id}/start`, { method: "POST" }),
    resume: (id: number) =>
      request<Run>(`/api/runs/${id}/resume`, { method: "POST" }),
    cancel: (id: number) =>
      request<Run>(`/api/runs/${id}/cancel`, { method: "POST" }),
    sessions: (id: number) =>
      request<DateSession[]>(`/api/runs/${id}/sessions`),
  },
  dates: {
    get: (id: number) => request<DateSession>(`/api/dates/${id}`),
    transcript: (id: number) =>
      request<{ session: DateSession; messages: DateMessage[] }>(
        `/api/dates/${id}/transcript`,
      ),
  },
  rankings: {
    forParticipant: (participantId: number, runId?: number) =>
      request<{
        participant_id: number;
        participant_name: string;
        run_id: number;
        rankings: Ranking[];
      }>(
        `/api/rankings/${participantId}${runId ? `?run_id=${runId}` : ""}`,
      ),
  },
  demo: {
    get: () => request<DemoPayload>("/api/demo"),
    seed: () => request<Run>("/api/demo/seed", { method: "POST" }),
  },
};
