/**
 * useAgentStream — Sprint 9 Phase 1.1
 *
 * Unified SSE control hook for all Agent streaming endpoints.
 *
 * Features:
 *   - AbortController-based cancellation (Esc / cancel button)
 *   - Auto-retry with exponential back-off on transient failures
 *   - Friendly error mapping (network / timeout / 4xx / 5xx → human text)
 *   - Token-level streaming for `thinking` events (merges deltas)
 *   - Tool-call timeline events with start/end timestamps for visualization
 *
 * Usage:
 *   const { run, cancel, state, steps, finalAnswer, error } = useAgentStream();
 *   run({
 *     url: "/api/projects/1/orchestrate/stream",
 *     body: { instruction: "..." },
 *     onDone: (answer) => { ... },
 *   });
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface AgentStepEvent {
  type: "thinking" | "tool_call" | "tool_result" | "answer" | "done" | "error";
  content?: string;
  tool_name?: string;
  tool_args?: Record<string, unknown> | string;
  tool_result?: string;
  /** done-only */
  answer?: string;
  bindings_changed?: boolean;
  error?: string | null;
  auto_saved_memories?: string[];
  /** Sprint 9: client-injected for timeline */
  _ts_start?: number;
  _ts_end?: number;
  _id?: string;
}

export type StreamState =
  | "idle"
  | "running"
  | "retrying"
  | "done"
  | "error"
  | "cancelled";

export interface RunOptions {
  url: string;
  body?: unknown;
  /** Override per-request retry count. Default: 2 */
  maxRetries?: number;
  /** Called on every step event (after merge). */
  onStep?: (step: AgentStepEvent) => void;
  /** Called on terminal "done" event. */
  onDone?: (answer: string, raw: AgentStepEvent) => void;
  /** Called on unrecoverable error (after retries exhausted). */
  onError?: (message: string) => void;
}

const DEFAULT_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://localhost:8000/api";

/** Map low-level errors into friendly Chinese messages. */
function friendlyError(raw: unknown): string {
  const msg = raw instanceof Error ? raw.message : String(raw);
  if (/abort|cancel/i.test(msg)) return "已取消";
  if (/Failed to fetch|NetworkError/i.test(msg)) return "网络连接失败，请检查后端服务";
  if (/timeout/i.test(msg)) return "请求超时，模型响应过慢";
  if (/\b401\b/.test(msg)) return "未授权，请检查 API Key 配置";
  if (/\b403\b/.test(msg)) return "访问被拒绝";
  if (/\b404\b/.test(msg)) return "接口不存在，请检查路径";
  if (/\b429\b/.test(msg)) return "请求过于频繁，请稍后重试";
  if (/\b5\d\d\b/.test(msg)) return "服务器错误，请重试或查看后端日志";
  return msg || "未知错误";
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    if (signal) {
      const onAbort = () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      };
      if (signal.aborted) return onAbort();
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

export interface UseAgentStream {
  state: StreamState;
  steps: AgentStepEvent[];
  finalAnswer: string;
  error: string;
  retryCount: number;
  elapsed: number; // seconds
  toolCallCount: number;
  run: (opts: RunOptions) => Promise<void>;
  cancel: () => void;
  reset: () => void;
}

export function useAgentStream(): UseAgentStream {
  const [state, setState] = useState<StreamState>("idle");
  const [steps, setSteps] = useState<AgentStepEvent[]>([]);
  const [finalAnswer, setFinalAnswer] = useState("");
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);
  // Track currently-pending tool_call events keyed by name+args so tool_result
  // can pair up and fill _ts_end (Phase 1.2 timeline).
  const pendingToolRef = useRef<Map<string, AgentStepEvent>>(new Map());

  // ── Elapsed clock ────────────────────────────────────────────────
  useEffect(() => {
    if (state === "running" || state === "retrying") {
      startedAtRef.current = Date.now();
      setElapsed(0);
      elapsedTimerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 250);
    } else if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
    return () => {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    };
  }, [state]);

  const reset = useCallback(() => {
    setState("idle");
    setSteps([]);
    setFinalAnswer("");
    setError("");
    setRetryCount(0);
    setElapsed(0);
    pendingToolRef.current.clear();
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState("cancelled");
  }, []);

  // Unmount cleanup
  useEffect(() => () => abortRef.current?.abort(), []);

  /**
   * Push a step event into state, merging consecutive `thinking` deltas
   * and pairing `tool_result` with its preceding `tool_call` for timing.
   */
  const pushStep = useCallback((evt: AgentStepEvent) => {
    setSteps((prev) => {
      // Merge consecutive thinking tokens into one entry.
      if (evt.type === "thinking") {
        const last = prev[prev.length - 1];
        if (last && last.type === "thinking") {
          const merged = {
            ...last,
            content: (last.content || "") + (evt.content || ""),
          };
          return [...prev.slice(0, -1), merged];
        }
        return [...prev, { ...evt, _ts_start: Date.now() }];
      }

      if (evt.type === "tool_call") {
        const id = `${evt.tool_name}:${prev.length}`;
        const stamped = { ...evt, _ts_start: Date.now(), _id: id };
        pendingToolRef.current.set(evt.tool_name || "", stamped);
        return [...prev, stamped];
      }

      if (evt.type === "tool_result") {
        const start = pendingToolRef.current.get(evt.tool_name || "");
        if (start) pendingToolRef.current.delete(evt.tool_name || "");
        return [
          ...prev,
          {
            ...evt,
            _ts_start: start?._ts_start,
            _ts_end: Date.now(),
            _id: start?._id,
          },
        ];
      }

      return [...prev, { ...evt, _ts_start: Date.now() }];
    });
  }, []);

  const drainStream = useCallback(
    async (
      resp: Response,
      opts: RunOptions,
      controller: AbortController,
    ): Promise<void> => {
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("Response has no body");
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (controller.signal.aborted) {
          try {
            await reader.cancel();
          } catch {
            /* noop */
          }
          throw new DOMException("Aborted", "AbortError");
        }
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          let evt: AgentStepEvent;
          try {
            evt = JSON.parse(payload);
          } catch {
            continue;
          }
          if (evt.type === "done") {
            setFinalAnswer(evt.answer || "");
            if (evt.error) setError(evt.error);
            setState("done");
            opts.onDone?.(evt.answer || "", evt);
            opts.onStep?.(evt);
            return;
          }
          if (evt.type === "error") {
            throw new Error(evt.error || evt.content || "stream error");
          }
          pushStep(evt);
          opts.onStep?.(evt);
        }
      }
    },
    [pushStep],
  );

  const run = useCallback(
    async (opts: RunOptions) => {
      // Reset state for a fresh run
      setSteps([]);
      setFinalAnswer("");
      setError("");
      setRetryCount(0);
      pendingToolRef.current.clear();
      setState("running");

      const maxRetries = opts.maxRetries ?? 2;
      const fullUrl = opts.url.startsWith("http")
        ? opts.url
        : `${DEFAULT_BASE}${opts.url}`;

      let attempt = 0;
      while (true) {
        const controller = new AbortController();
        abortRef.current = controller;
        try {
          const resp = await fetch(fullUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(opts.body ?? {}),
            signal: controller.signal,
          });
          if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
          }
          await drainStream(resp, opts, controller);
          return;
        } catch (err) {
          // User-initiated cancel — never retry
          if ((err as DOMException)?.name === "AbortError") {
            setState("cancelled");
            return;
          }
          attempt += 1;
          const friendly = friendlyError(err);
          if (attempt > maxRetries) {
            setError(friendly);
            setState("error");
            opts.onError?.(friendly);
            return;
          }
          // Exponential back-off: 800ms, 1600ms ...
          setRetryCount(attempt);
          setState("retrying");
          try {
            await sleep(800 * Math.pow(2, attempt - 1), controller.signal);
          } catch {
            setState("cancelled");
            return;
          }
          setState("running");
        }
      }
    },
    [drainStream],
  );

  // Compute tool call count cheaply
  const toolCallCount = steps.filter((s) => s.type === "tool_call").length;

  return {
    state,
    steps,
    finalAnswer,
    error,
    retryCount,
    elapsed,
    toolCallCount,
    run,
    cancel,
    reset,
  };
}
