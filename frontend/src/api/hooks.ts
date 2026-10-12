import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { Participant } from "../types";

export interface People {
  items: Participant[];
  /** True when no real people exist yet and the synthetic sample is shown instead. */
  isSample: boolean;
}

/** The people to show: real ones when any exist, otherwise the synthetic sample. */
export function usePeople() {
  return useQuery<People>({
    queryKey: ["people"],
    queryFn: async () => {
      const real = await api.participants.list(1, 200, false);
      if (real.total > 0) return { items: real.items, isSample: false };
      const sample = await api.participants.list(1, 200, true);
      return { items: sample.items, isSample: true };
    },
  });
}

export const RUN_ACTIVE = new Set(["pending", "queued", "running", "cancelling"]);

/** A run, polled while its dates are still in progress. */
export function useRun(runId: number | undefined) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.runs.get(runId!),
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data && RUN_ACTIVE.has(q.state.data.status) ? 1200 : false),
  });
}
