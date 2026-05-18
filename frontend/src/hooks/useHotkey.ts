/**
 * useHotkey — Sprint 9 Phase 1.4
 *
 * Tiny keyboard-shortcut hook. Bind once, fires on `keydown`. Skips when
 * focus is in an input/textarea/contenteditable unless `allowInInput=true`.
 *
 * Usage:
 *   useHotkey("mod+k", () => openCommandCenter());
 *   useHotkey("escape", cancel);
 *   useHotkey("mod+enter", submit, { allowInInput: true });
 */

import { useEffect } from "react";

interface Options {
  allowInInput?: boolean;
  enabled?: boolean;
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return false;
}

function matches(e: KeyboardEvent, combo: string): boolean {
  const parts = combo.toLowerCase().split("+").map((p) => p.trim());
  const key = parts[parts.length - 1];
  const mods = parts.slice(0, -1);

  const wantMod = mods.includes("mod") || mods.includes("cmd") || mods.includes("ctrl");
  const wantShift = mods.includes("shift");
  const wantAlt = mods.includes("alt") || mods.includes("option");

  const hasMod = e.metaKey || e.ctrlKey;
  if (wantMod !== hasMod) return false;
  if (wantShift !== e.shiftKey) return false;
  if (wantAlt !== e.altKey) return false;

  const pressed = e.key.toLowerCase();
  if (key === "escape" || key === "esc") return pressed === "escape";
  if (key === "enter") return pressed === "enter";
  if (key === "space") return pressed === " " || pressed === "spacebar";
  return pressed === key;
}

export function useHotkey(
  combo: string,
  handler: (e: KeyboardEvent) => void,
  opts: Options = {},
): void {
  const { allowInInput = false, enabled = true } = opts;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (!matches(e, combo)) return;
      if (!allowInInput && isTypingTarget(e.target)) return;
      e.preventDefault();
      handler(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [combo, handler, allowInInput, enabled]);
}
