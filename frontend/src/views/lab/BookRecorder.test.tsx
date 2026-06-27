import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookRecorder } from "./BookRecorder";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("renders recorder state and book coverage", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/books/status")) {
      return Promise.resolve(new Response(JSON.stringify(bookStatus), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<BookRecorder />);

  expect(screen.getByText("Book recorder")).toBeInTheDocument();
  expect(await screen.findByText("EUR_USD")).toBeInTheDocument();
  expect(screen.getByText("running")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText("11")).toBeInTheDocument();
  expect(screen.getByText("1.09000")).toBeInTheDocument();
  expect(
    screen.getByText(
      "Book data is forward-recorded only; history begins when the recorder is enabled."
    )
  ).toBeInTheDocument();
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function requestUrl(input: string | URL | Request): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.toString() : input.url;
}

const bookStatus = {
  recorder: {
    running: true,
    state: "running",
    last_started_at: "2026-01-15T15:00:00+00:00",
    last_stopped_at: null,
    last_error: null,
  },
  coverage: [
    {
      book_type: "order",
      instrument: "EUR_USD",
      snapshot_count: 12,
      from: "2026-01-15T14:20:00+00:00",
      to: "2026-01-15T14:40:00+00:00",
      latest_mid_price: "1.09000",
    },
    {
      book_type: "position",
      instrument: "EUR_USD",
      snapshot_count: 11,
      from: "2026-01-15T14:20:00+00:00",
      to: "2026-01-15T14:40:00+00:00",
      latest_mid_price: "1.09010",
    },
  ],
  latest: {
    EUR_USD: {
      order: {
        snapshot_time: "2026-01-15T14:40:00+00:00",
        bucket_count: 401,
        mid_price: "1.09000",
        recorded_ts: "2026-01-15T14:41:00+00:00",
      },
      position: {
        snapshot_time: "2026-01-15T14:40:00+00:00",
        bucket_count: 401,
        mid_price: "1.09010",
        recorded_ts: "2026-01-15T14:41:00+00:00",
      },
    },
  },
};
