import clsx from "clsx";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { EmptyState, PageLoader } from "./ui";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render?: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
  hideOnMobile?: boolean;
}

export function DataTable<T extends { id?: number | string }>({ columns, rows, loading, onRowClick, empty, footer }: {
  columns: Column<T>[];
  rows: T[] | undefined;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  empty?: string;
  footer?: ReactNode;
}) {
  if (loading) return <PageLoader />;
  if (!rows || rows.length === 0) return <EmptyState message={empty} />;
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={clsx("th", c.align === "right" && "text-right", c.hideOnMobile && "hidden md:table-cell")}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((row, i) => (
            <tr
              key={row.id ?? i}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={clsx(onRowClick && "cursor-pointer hover:bg-brand-50")}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={clsx("td", c.align === "right" && "text-right tabular-nums", c.hideOnMobile && "hidden md:table-cell", c.className)}
                >
                  {c.render ? c.render(row) : String((row as any)[c.key] ?? "-")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer}
      </table>
    </div>
  );
}

export function Pagination({ page, count, pageSize = 25, onPage }: { page: number; count: number; pageSize?: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count <= pageSize) return <p className="mt-3 text-xs text-slate-500">{count} record(s)</p>;
  return (
    <div className="no-print mt-3 flex items-center justify-between text-sm text-slate-600">
      <span className="text-xs">
        Page {page} of {pages} · {count} records
      </span>
      <div className="flex gap-1">
        <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button className="btn-secondary btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

/** Debounced search input. */
export function SearchBox({ value, onChange, placeholder = "Search..." }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [local, setLocal] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => local !== value && onChange(local), 300);
    return () => clearTimeout(t);
  }, [local, value, onChange]);
  return (
    <div className="relative w-full sm:w-64">
      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
      <input className="input pl-8" value={local} onChange={(e) => setLocal(e.target.value)} placeholder={placeholder} aria-label="Search" />
    </div>
  );
}
