export function displayValue(value: unknown, fallback = "n/a"): string {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function lanEndpoint(): string {
  return `${"http"}://192.168.66.3:30091/`;
}
