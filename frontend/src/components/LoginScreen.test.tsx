import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginScreen } from "./LoginScreen";

describe("LoginScreen", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("authenticates with backend-only reviewer credentials", async () => {
    const identity = {
      id: "credentials:test",
      email: "reviewer@local.account",
      name: "reviewer",
      logout_url: null,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(identity), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const authenticated = vi.fn();
    render(<LoginScreen onAuthenticated={authenticated} />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Correct-Password9!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(authenticated).toHaveBeenCalledWith(identity));
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.credentials).toBe("include");
    expect(JSON.parse(String(request.body))).toEqual({
      username: "reviewer",
      password: "Correct-Password9!",
    });
  });

  it("shows a generic invalid-credentials error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid username or password." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Wrong-Password9!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      await screen.findByText("Invalid username or password."),
    ).toBeInTheDocument();
  });

  it("toggles password visibility without changing its value", () => {
    render(<LoginScreen onAuthenticated={vi.fn()} />);
    const password = screen.getByLabelText("Password");
    fireEvent.change(password, { target: { value: "Correct-Password9!" } });

    expect(password).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(password).toHaveValue("Correct-Password9!");

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(password).toHaveAttribute("type", "password");
  });

  it("shows password requirements and enables submit only when they pass", () => {
    render(<LoginScreen onAuthenticated={vi.fn()} />);
    const password = screen.getByLabelText("Password");
    const submit = screen.getByRole("button", { name: "Continue" });

    expect(screen.getByText("Must contain")).toBeInTheDocument();
    expect(screen.getByText("12–128 characters")).toBeInTheDocument();
    expect(screen.getByText("One uppercase letter")).toBeInTheDocument();
    expect(screen.getByText("One lowercase letter")).toBeInTheDocument();
    expect(screen.getByText("One number")).toBeInTheDocument();
    expect(screen.getByText("One symbol")).toBeInTheDocument();
    expect(screen.getByText("No spaces")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(password, { target: { value: "weak" } });
    expect(submit).toBeDisabled();

    fireEvent.change(password, { target: { value: "Correct-Password9!" } });
    expect(submit).toBeEnabled();
  });
});
