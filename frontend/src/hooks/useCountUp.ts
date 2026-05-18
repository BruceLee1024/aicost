/**
 * useCountUp — animates a numeric label from 0 → target when an
 * IntersectionObserver detects the element is in view.
 *
 * Parses the source label to extract a numeric portion + suffix
 * (e.g. "96%" → number 96, suffix "%"; "200+" → 200, "+";
 *  "50万+" → 50, "万+"; "10x" → 10, "x"). Plain numbers also work.
 *
 * If the input has no numeric prefix, the label passes through unchanged.
 */
import { useEffect, useRef, useState } from "react";

const NUM_PREFIX = /^([\d.]+)/;

export function useCountUp(label: string, durationMs: number = 1200) {
  const ref = useRef<HTMLElement | null>(null);
  const [display, setDisplay] = useState<string>(label);
  const startedRef = useRef(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const match = label.match(NUM_PREFIX);
    if (!match) {
      setDisplay(label);
      return;
    }
    const target = parseFloat(match[1]);
    const suffix = label.slice(match[1].length);
    if (!isFinite(target)) {
      setDisplay(label);
      return;
    }

    // Decide formatter (preserve integer vs. decimal feel from the label).
    const isInt = !match[1].includes(".");
    const fmt = (n: number) =>
      isInt ? Math.round(n).toString() : n.toFixed(1);

    setDisplay(fmt(0) + suffix);

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setDisplay(label);
      return;
    }

    if (typeof IntersectionObserver === "undefined") {
      setDisplay(label);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting || startedRef.current) continue;
          startedRef.current = true;
          const start = performance.now();
          const tick = (now: number) => {
            const t = Math.min(1, (now - start) / durationMs);
            // easeOutCubic
            const eased = 1 - Math.pow(1 - t, 3);
            setDisplay(fmt(target * eased) + suffix);
            if (t < 1) requestAnimationFrame(tick);
            else setDisplay(label);
          };
          requestAnimationFrame(tick);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [label, durationMs]);

  return { ref, display };
}
