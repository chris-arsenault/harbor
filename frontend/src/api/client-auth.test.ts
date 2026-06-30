import { afterEach, expect, test, vi } from "vitest";

import { fetchStatus } from "./client";

const auth = vi.hoisted(() => ({
  expireAuthSession: vi.fn(),
  getAccessToken: vi.fn(() => Promise.resolve("auth-token")),
}));

vi.mock("../auth/cognito", () => ({
  expireAuthSession: auth.expireAuthSession,
  getAccessToken: auth.getAccessToken,
}));

afterEach(() => {
  vi.restoreAllMocks();
  auth.expireAuthSession.mockClear();
  auth.getAccessToken.mockClear();
  auth.getAccessToken.mockResolvedValue("auth-token");
});

test("api requests include the current access token", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify({ bot_state: "WAIT_SWEEP" }), { status: 200 }));

  await fetchStatus();

  expect(fetchMock).toHaveBeenCalledWith("/api/status", {
    headers: { Accept: "application/json", Authorization: "Bearer auth-token" },
  });
});

test("api requests expire the auth session when the backend rejects the token", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "unauthorized" }), {
      headers: { "Content-Type": "application/json" },
      status: 401,
    })
  );

  await expect(fetchStatus()).rejects.toThrow("GET /api/status failed with 401: unauthorized");

  expect(auth.expireAuthSession).toHaveBeenCalledTimes(1);
});
