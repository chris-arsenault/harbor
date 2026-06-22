import { useEffect, useRef, useState, type ReactNode } from "react";

import { toNumber } from "./format";

/**
 * Renders display content and briefly flashes green/red when its underlying
 * numeric value moves up or down — the "ticking tape" feel of a trading desk.
 */
export function LiveValue({
  value,
  className,
  children,
}: {
  readonly value: unknown;
  readonly className?: string;
  readonly children: ReactNode;
}) {
  const previous = useRef<number | null>(toNumber(value));
  const [flash, setFlash] = useState("");

  useEffect(() => {
    const before = previous.current;
    const after = toNumber(value);
    previous.current = after;
    if (before === null || after === null || after === before) {
      return;
    }
    setFlash(after > before ? "flash-up" : "flash-down");
    const timer = setTimeout(() => setFlash(""), 650);
    return () => clearTimeout(timer);
  }, [value]);

  return <span className={[className, flash].filter(Boolean).join(" ")}>{children}</span>;
}
