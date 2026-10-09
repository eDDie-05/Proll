import type { ReactNode } from "react";

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-800 via-brand-700 to-brand-900 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3 text-white">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gold-500 text-2xl font-black text-brand-900">B</div>
          <div>
            <p className="text-lg font-bold leading-tight">Bravado Company Ltd</p>
            <p className="text-sm text-brand-200">Payroll Management System</p>
          </div>
        </div>
        <div className="rounded-xl bg-white p-6 shadow-xl sm:p-8">
          <h1 className="mb-5 text-xl font-bold text-brand-800">{title}</h1>
          {children}
        </div>
        <p className="mt-4 text-center text-xs text-brand-200">Authorised users only. All activity is logged.</p>
      </div>
    </div>
  );
}
