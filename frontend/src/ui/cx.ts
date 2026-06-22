export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function byText(a: string, b: string): number {
  return a.localeCompare(b);
}
