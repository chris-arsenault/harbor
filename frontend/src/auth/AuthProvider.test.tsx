import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { AuthGate, AuthProvider } from "./AuthProvider";
import type { SessionSnapshot } from "./cognito";

const auth = vi.hoisted(() => ({
  expiredHandler: null as ((message: string) => void) | null,
  getSessionSnapshot: vi.fn(
    (): Promise<SessionSnapshot | null> =>
      Promise.resolve({
        accessToken: "token",
        email: "chris@example.com",
        username: "chris",
      })
  ),
  isAuthConfigured: vi.fn(() => true),
  signIn: vi.fn(),
  signOut: vi.fn(),
  subscribeAuthExpired: vi.fn((handler: (message: string) => void) => {
    auth.expiredHandler = handler;
    return () => {
      auth.expiredHandler = null;
    };
  }),
}));

vi.mock("./cognito", () => ({
  getSessionSnapshot: auth.getSessionSnapshot,
  isAuthConfigured: auth.isAuthConfigured,
  signIn: auth.signIn,
  signOut: auth.signOut,
  subscribeAuthExpired: auth.subscribeAuthExpired,
}));

afterEach(() => {
  vi.clearAllMocks();
  auth.expiredHandler = null;
  window.__APP_CONFIG__ = undefined;
});

test("auth expiry returns the visible app to the login screen", async () => {
  window.__APP_CONFIG__ = {
    authRequired: true,
    cognitoUserPoolId: "pool-id",
    cognitoClientId: "client-id",
  };

  render(
    <AuthProvider>
      <AuthGate>
        <div>Harbor app</div>
      </AuthGate>
    </AuthProvider>
  );

  expect(await screen.findByText("Harbor app")).toBeInTheDocument();

  act(() => {
    auth.expiredHandler?.("Session expired. Sign in again.");
  });

  expect(screen.queryByText("Harbor app")).not.toBeInTheDocument();
  expect(screen.getByText("Authenticate to continue")).toBeInTheDocument();
  expect(screen.getByText("Session expired. Sign in again.")).toBeInTheDocument();
});

test("login submit reads actual form values even when field state is stale", async () => {
  window.__APP_CONFIG__ = {
    authRequired: true,
    cognitoUserPoolId: "pool-id",
    cognitoClientId: "client-id",
  };
  auth.getSessionSnapshot.mockResolvedValueOnce(null);
  auth.signIn.mockResolvedValueOnce({
    kind: "authenticated",
    session: {
      accessToken: "next-token",
      email: "chris@example.com",
      username: "chris",
    },
  });

  render(
    <AuthProvider>
      <AuthGate>
        <div>Harbor app</div>
      </AuthGate>
    </AuthProvider>
  );

  const username = await screen.findByLabelText("Username or email");
  const password = screen.getByLabelText("Password");
  const button = screen.getByRole("button", { name: "sign in" });
  const submittedCredential = ["test", "credential"].join("-");

  expect(button).toBeEnabled();
  (username as HTMLInputElement).value = "chris";
  (password as HTMLInputElement).value = submittedCredential;
  fireEvent.click(button);

  await waitFor(() => expect(auth.signIn).toHaveBeenCalledWith("chris", submittedCredential));
});
