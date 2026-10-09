import { useQuery } from "@tanstack/react-query";
import { api, type Paginated } from "../api/client";

/** Fetch a (possibly paginated) list endpoint. */
export function useList<T>(endpoint: string, params: Record<string, any> = {}, enabled = true) {
  return useQuery({
    queryKey: [endpoint, params],
    enabled,
    queryFn: async () => {
      const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
      const r = await api.get<Paginated<T> | T[]>(endpoint, { params: clean });
      const d = r.data;
      return Array.isArray(d) ? { count: d.length, results: d, next: null, previous: null } : d;
    },
  });
}

/** Options for <select> from a lookup endpoint. */
export function useOptions(endpoint: string, label: (row: any) => string, enabled = true, params: Record<string, any> = {}) {
  const q = useList<any>(endpoint, { page_size: 500, ...params }, enabled);
  return (q.data?.results || []).map((r: any) => ({ value: r.id, label: label(r) }));
}

export const employeeLabel = (e: any) => `${e.employee_number} — ${e.full_name ?? `${e.first_name} ${e.last_name}`}`;
