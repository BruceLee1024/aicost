/**
 * useScrollReveal — toggles `.is-visible` on a ref when it enters the viewport.
 *
 * Pairs with the `.landing-reveal` / `.landing-reveal-stagger` CSS classes.
 * Default behaviour: trigger once and disconnect (good for entrance effects).
 * Pass `{ once: false }` if you want re-trigger on exit.
 */
import { useEffect, useRef } from "react";

interface Options {
  /** Threshold for IntersectionObserver. Default 0.15. */
  threshold?: number;
  /** Root margin for IntersectionObserver. Default "0px 0px -10% 0px". */
  rootMargin?: string;
  /** Disconnect after first reveal. Default true. */
  once?: boolean;
}

export function useScrollReveal<T extends HTMLElement = HTMLElement>(
  options: Options = {},
) {
  const { threshold = 0.15, rootMargin = "0px 0px -10% 0px", once = true } =
    options;
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // SSR / older browsers — gracefully reveal immediately.
    if (typeof IntersectionObserver === "undefined") {
      node.classList.add("is-visible");
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            if (once) io.unobserve(entry.target);
          } else if (!once) {
            entry.target.classList.remove("is-visible");
          }
        }
      },
      { threshold, rootMargin },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [threshold, rootMargin, once]);

  return ref;
}
