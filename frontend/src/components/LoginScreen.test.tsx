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
      target: { value: "correct-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(authenticated).toHaveBeenCalledWith(identity));
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.credentials).toBe("include");
    expect(JSON.parse(String(request.body))).toEqual({
      username: "reviewer",
      password: "correct-password",
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
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      await screen.findByText("Invalid username or password."),
    ).toBeInTheDocument();
  });
});
