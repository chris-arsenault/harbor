const DASH = "—";

export function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function group(value: number, digits: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtNum(value: unknown, digits = 2): string {
  const parsed = toNumber(value);
  return parsed === null ? DASH : group(parsed, digits);
}

export function fmtInt(value: unknown): string {
  const parsed = toNumber(value);
  return parsed === null ? DASH : Math.round(parsed).toLocaleString("en-US");
}

export function fmtSigned(value: unknown, digits = 2): string {
  const parsed = toNumber(value);
  if (parsed === null) {
    return DASH;
  }
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${group(parsed, digits)}`;
}

export function fmtPrice(value: unknown, digits = 5): string {
  const parsed = toNumber(value);
  return parsed === null ? DASH : parsed.toFixed(digits);
}

export function fmtPct(value: unknown, digits = 1, alreadyPercent = false): string {
  const parsed = toNumber(value);
  if (parsed === null) {
    return DASH;
  }
  const scaled = alreadyPercent ? parsed : parsed * 100;
  return `${group(scaled, digits)}%`;
}

export function fmtR(value: unknown): string {
  const parsed = toNumber(value);
  return parsed === null ? DASH : `${fmtSigned(parsed, 2)}R`;
}

export function signClass(value: unknown): "pos" | "neg" | "" {
  const parsed = toNumber(value);
  if (parsed === null || parsed === 0) {
    return "";
  }
  return parsed > 0 ? "pos" : "neg";
}

export function valueTone(value: unknown): "up" | "down" | undefined {
  const cls = signClass(value);
  if (cls === "pos") {
    return "up";
  }
  return cls === "neg" ? "down" : undefined;
}

export function fmtClock(ts: string | null | undefined): string {
  if (!ts) {
    return DASH;
  }
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return ts;
  }
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  });
}

export function fmtDateTime(ts: string | null | undefined): string {
  if (!ts) {
    return DASH;
  }
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return ts;
  }
  return date.toLocaleString("en-GB", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export function fmtDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : DASH;
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

export const NO_VALUE = DASH;
