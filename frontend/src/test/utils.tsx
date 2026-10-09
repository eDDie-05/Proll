import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ToastProvider } from "../components/Toast";

export function renderWithProviders(ui: ReactElement, { route = "/", path = "*" } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
        <ToastProvider>
          <Routes>
            <Route path={path} element={ui} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const me = (permissions: string[]) => ({
  id: 1, username: "tester", email: "t@x", first_name: "Test", last_name: "", role: "X", role_name: "Tester",
  permissions, employee_id: null, must_change_password: false,
});
