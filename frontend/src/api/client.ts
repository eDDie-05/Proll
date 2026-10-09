import axios, { AxiosError, type AxiosRequestConfig } from "axios";

/**
 * Access token is kept in memory only. The refresh token lives in an httpOnly cookie set by the API,
 * so it is never readable from JavaScript.
 */
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export const setAccessToken = (t: string | null) => {
  accessToken = t;
};
export const setSessionExpiredHandler = (fn: () => void) => {
  onSessionExpired = fn;
};

export const api = axios.create({ baseURL: "/api", withCredentials: true });

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

export async function refreshAccess(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post("/api/auth/refresh/", null, { withCredentials: true })
      .then((r) => {
        setAccessToken(r.data.access);
        return r.data.access as string;
      })
      .catch(() => {
        setAccessToken(null);
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    const url = original?.url || "";
    if (error.response?.status === 401 && !original._retry && !url.startsWith("/auth/")) {
      original._retry = true;
      const token = await refreshAccess();
      if (token) return api(original);
      onSessionExpired?.();
    }
    return Promise.reject(error);
  },
);

/** Turn a DRF error payload into a readable message. */
export function errorMessage(err: unknown): string {
  const e = err as AxiosError<any>;
  const data = e?.response?.data;
  if (!data) return e?.message || "Something went wrong.";
  if (typeof data === "string") return data.slice(0, 300);
  if (data.detail) return Array.isArray(data.detail) ? data.detail.join(" ") : String(data.detail);
  if (Array.isArray(data)) return data.join(" ");
  if (data instanceof Blob) return "Request failed.";
  return Object.entries(data)
    .map(([k, v]) => `${k === "non_field_errors" ? "" : k + ": "}${Array.isArray(v) ? v.join(" ") : typeof v === "object" ? JSON.stringify(v) : v}`)
    .join(" | ");
}

/** Field errors keyed by field name, for inline form messages. */
export function fieldErrors(err: unknown): Record<string, string> {
  const data = (err as AxiosError<any>)?.response?.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(data)) out[k] = Array.isArray(v) ? v.join(" ") : String(v);
  return out;
}

/** Download a file (PDF/CSV/XLSX) through the authenticated client. */
export async function download(url: string, fallbackName = "download") {
  const r = await api.get(url, { responseType: "blob" });
  const dispo = (r.headers["content-disposition"] as string) || "";
  const match = /filename="?([^"]+)"?/.exec(dispo);
  const name = match ? match[1] : fallbackName;
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

/** Open a PDF in a new tab for preview/printing. */
export async function openPdf(url: string) {
  const r = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
  window.open(href, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
