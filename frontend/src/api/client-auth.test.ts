import { afterEach, expect, test, vi } from "vitest";

import { fetchStatus } from "./client";

const auth = vi.hoisted(() => ({
  expireAuthSession: vi.fn(),
  getAccessToken: vi.fn(() => Promise.resolve("auth-token")),
  refreshAccessToken: vi.fn(() => Promise.resolve(null as string | null)),
}));

vi.mock("../auth/cognito", () => ({
  expireAuthSession: auth.expireAuthSession,
  getAccessToken: auth.getAccessToken,
  refreshAccessToken: auth.refreshAccessToken,
}));

afterEach(() => {
  vi.restoreAllMocks();
  auth.expireAuthSession.mockClear();
  auth.getAccessToken.mockClear();
  auth.getAccessToken.mockResolvedValue("auth-token");
  auth.refreshAccessToken.mockClear();
  auth.refreshAccessToken.mockResolvedValue(null);
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

test("api requests refresh and retry once when the backend rejects the token", async () => {
  auth.getAccessToken.mockResolvedValueOnce("old-token");
  auth.refreshAccessToken.mockResolvedValueOnce("fresh-token");
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "unauthorized" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      })
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ bot_state: "WAIT_SWEEP" }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      })
    );

  await expect(fetchStatus()).resolves.toEqual({ bot_state: "WAIT_SWEEP" });

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/status", {
    headers: { Accept: "application/json", Authorization: "Bearer old-token" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/status", {
    headers: { Accept: "application/json", Authorization: "Bearer fresh-token" },
  });
  expect(auth.expireAuthSession).not.toHaveBeenCalled();
});

test("api requests expire the auth session when refresh cannot recover the token", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "unauthorized" }), {
      headers: { "Content-Type": "application/json" },
      status: 401,
    })
  );

  await expect(fetchStatus()).rejects.toThrow("GET /api/status failed with 401: unauthorized");

  expect(auth.refreshAccessToken).toHaveBeenCalledTimes(1);
  expect(auth.expireAuthSession).toHaveBeenCalledTimes(1);
});

test("api requests expire the auth session when the refreshed token is rejected", async () => {
  auth.refreshAccessToken.mockResolvedValueOnce("fresh-token");
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "expired" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      })
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "still unauthorized" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      })
    );

  await expect(fetchStatus()).rejects.toThrow(
    "GET /api/status failed with 401: still unauthorized"
  );

  expect(auth.refreshAccessToken).toHaveBeenCalledTimes(1);
  expect(auth.expireAuthSession).toHaveBeenCalledTimes(1);
});
