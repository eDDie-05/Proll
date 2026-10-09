import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

const login = vi.fn();
let failWith: unknown = null;
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    login: async (...args: unknown[]) => {
      login(...args);
      if (failWith) throw failWith;
    },
  }),
}));

import Login from "../pages/auth/Login";
import { renderWithProviders } from "./utils";

describe("Login page", () => {
  beforeEach(() => {
    login.mockReset();
    failWith = null;
  });

  it("validates required fields before calling the API", async () => {
    renderWithProviders(<Login />);
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/enter your username and password/i);
    expect(login).not.toHaveBeenCalled();
  });

  it("submits credentials", async () => {
    renderWithProviders(<Login />);
    await userEvent.type(screen.getByLabelText(/username/i), "payroll");
    await userEvent.type(screen.getByLabelText(/password/i), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("payroll", "secret-pass"));
  });

  it("shows the server error", async () => {
    failWith = { response: { data: { detail: "Invalid credentials or inactive account." } } };
    renderWithProviders(<Login />);
    await userEvent.type(screen.getByLabelText(/username/i), "x");
    await userEvent.type(screen.getByLabelText(/password/i), "y");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid credentials/i);
  });
});
