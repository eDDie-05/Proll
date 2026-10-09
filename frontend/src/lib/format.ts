const moneyFmt = new Intl.NumberFormat("en-TZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = new Intl.NumberFormat("en-TZ");

export function money(value: string | number | null | undefined, currency = "TZS"): string {
  if (value === null || value === undefined || value === "") return "-";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  const s = moneyFmt.format(Math.abs(n));
  return `${currency ? currency + " " : ""}${n < 0 ? "(" + s + ")" : s}`;
}

export function num(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  return intFmt.format(Number(value));
}

export function date(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value.length === 10 ? value + "T00:00:00" : value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function compact(value: string | number): string {
  const n = Number(value);
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}

export const humanize = (s: string) =>
  s ? s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : "";
