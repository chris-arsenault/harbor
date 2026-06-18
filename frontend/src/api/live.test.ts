import { afterEach, expect, test, vi } from "vitest";

import {
  createLiveConnection,
  liveWebSocketUrl,
  parseEnvelope,
  type WebSocketConstructor,
} from "./live";

afterEach(() => {
  vi.restoreAllMocks();
});

test("liveWebSocketUrl maps the current page origin to /ws", () => {
  const url = liveWebSocketUrl(new URL("https://harbor.lan/dashboard"));

  expect(url).toBe("wss://harbor.lan/ws");
});

test("parseEnvelope validates websocket envelope shape", () => {
  expect(
    parseEnvelope(
      JSON.stringify({
        type: "status",
        sent_at: "2026-01-15T14:32:00Z",
        payload: { bot_state: "WAIT_SWEEP" },
      })
    )
  ).toEqual({
    type: "status",
    sent_at: "2026-01-15T14:32:00Z",
    payload: { bot_state: "WAIT_SWEEP" },
  });

  expect(() => parseEnvelope(JSON.stringify({ payload: {} }))).toThrow(
    "invalid websocket envelope"
  );
});

test("createLiveConnection forwards parsed envelopes and heartbeat notifications", () => {
  const onEnvelope = vi.fn();
  const onHeartbeat = vi.fn();
  const connection = createLiveConnection({
    url: "ws://harbor.test/ws",
    WebSocketImpl: FakeWebSocket,
    onEnvelope,
    onHeartbeat,
  });
  const socket = fakeWebSocketInstances[0];

  socket.emit(
    JSON.stringify({
      type: "candle",
      sent_at: "2026-01-15T14:32:00Z",
      payload: { close: "1.10400000" },
    })
  );
  connection.close();

  expect(onEnvelope).toHaveBeenCalledWith({
    type: "candle",
    sent_at: "2026-01-15T14:32:00Z",
    payload: { close: "1.10400000" },
  });
  expect(onHeartbeat).toHaveBeenCalledWith("2026-01-15T14:32:00Z");
  expect(socket.closed).toBe(true);
});

interface FakeWebSocketInstance {
  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  closed: boolean;
  close: () => void;
  emit: (data: string) => void;
}

const fakeWebSocketInstances: FakeWebSocketInstance[] = [];

const FakeWebSocket = function (this: FakeWebSocketInstance, url: string) {
  this.url = url;
  this.onmessage = null;
  this.onerror = null;
  this.closed = false;
  this.close = () => {
    this.closed = true;
  };
  this.emit = (data) => {
    this.onmessage?.({ data } as MessageEvent<string>);
  };
  fakeWebSocketInstances.push(this);
} as unknown as WebSocketConstructor;
