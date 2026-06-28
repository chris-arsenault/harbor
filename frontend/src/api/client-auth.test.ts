import { afterEach, expect, test, vi } from "vitest";

import { fetchStatus } from "./client";

vi.mock("../auth/cognito", () => ({
  getAccessToken: () => Promise.resolve("auth-token"),
}));

afterEach(() => {
  vi.restoreAllMocks();
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
