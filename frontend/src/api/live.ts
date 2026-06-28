import type {
  LabStatusEnvelope,
  VariantEquityEnvelope,
  VariantTrade,
  WebSocketEnvelope,
} from "./types";
import { getAccessToken } from "../auth/cognito";

export type LabEnvelope =
  | WebSocketEnvelope<VariantTrade>
  | WebSocketEnvelope<VariantEquityEnvelope>
  | WebSocketEnvelope<LabStatusEnvelope>;

export interface LiveConnection {
  close: () => void;
}

export interface LiveConnectionOptions {
  url: string;
  WebSocketImpl?: WebSocketConstructor;
  onEnvelope: (envelope: WebSocketEnvelope) => void;
  onHeartbeat?: (sentAt: string) => void;
  onError?: (event: Event) => void;
}

export type WebSocketConstructor = new (url: string) => LiveSocket;

interface LiveSocket {
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  close: () => void;
}

export function liveWebSocketUrl(location: Pick<Location | URL, "protocol" | "host">) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/ws`;
}

export function createLiveConnection(options: LiveConnectionOptions): LiveConnection {
  const WebSocketImpl = options.WebSocketImpl ?? WebSocket;
  let socket: LiveSocket | null = null;
  let closed = false;
  void openSocket();

  return {
    close: () => {
      closed = true;
      socket?.close();
    },
  };

  async function openSocket() {
    const token = await getAccessToken();
    if (closed) return;
    socket = new WebSocketImpl(webSocketUrlWithToken(options.url, token));
    socket.onmessage = (event: MessageEvent<string>) => {
      const envelope = parseEnvelope(event.data);
      options.onEnvelope(envelope);
      options.onHeartbeat?.(envelope.sent_at);
    };
    socket.onerror = (event: Event) => options.onError?.(event);
  }
}

export function webSocketUrlWithToken(url: string, token: string | null): string {
  if (!token) return url;
  const parsed = new URL(url);
  parsed.searchParams.set("access_token", token);
  return parsed.toString();
}

export function parseEnvelope(raw: string): WebSocketEnvelope {
  const value = JSON.parse(raw) as unknown;
  if (!isRecord(value)) {
    throw new Error("invalid websocket envelope");
  }
  const type = value.type;
  const sentAt = value.sent_at;
  const payload = value.payload;
  if (typeof type !== "string" || typeof sentAt !== "string" || !isRecord(payload)) {
    throw new Error("invalid websocket envelope");
  }
  return {
    type,
    sent_at: sentAt,
    payload,
  };
}

export function isLabEnvelope(envelope: WebSocketEnvelope<unknown>): envelope is LabEnvelope {
  return (
    envelope.type === "variant_trade" ||
    envelope.type === "variant_equity" ||
    envelope.type === "lab_status"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
