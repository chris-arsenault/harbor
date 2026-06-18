import { afterEach, expect, test, vi } from "vitest";

import {
  createPaperVariant,
  fetchLabStudy,
  fetchVariants,
  retirePaperVariant,
  startOptimization,
} from "./client";
import { isLabEnvelope, parseEnvelope } from "./live";

afterEach(() => {
  vi.restoreAllMocks();
});

test("Lab clients call optimizer and variant endpoints with backend payloads", async () => {
  const fetchMock = mockJsonFetch({
    study_id: 42,
    status: "completed",
    variants: [{ id: 7, status: "paper" }],
  });

  await startOptimization({ fixture: "clean_signal_day.json" });
  await fetchLabStudy(42);
  await fetchVariants();
  await createPaperVariant({ trial_id: 2, label: "paper-trial-1" });
  await retirePaperVariant(7);

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/optimize", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ fixture: "clean_signal_day.json" }),
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/optimize/42", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/variants", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/variants", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ trial_id: 2, label: "paper-trial-1" }),
  });
  expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/variants/7/retire", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
});

test("Lab websocket envelopes are recognized without changing dashboard parsing", () => {
  const trade = parseEnvelope(
    JSON.stringify({
      type: "variant_trade",
      sent_at: "2026-01-15T14:32:00Z",
      payload: { variant_id: 7, pnl: "60.00000000" },
    })
  );
  const status = parseEnvelope(
    JSON.stringify({
      type: "status",
      sent_at: "2026-01-15T14:32:00Z",
      payload: { bot_state: "WAIT_SWEEP" },
    })
  );

  expect(isLabEnvelope(trade)).toBe(true);
  expect(isLabEnvelope(status)).toBe(false);
  expect(status.type).toBe("status");
});

function mockJsonFetch(payload: unknown) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
    );
}
