/**
 * useAgentHistory — Sprint 9 Phase 1.4
 *
 * Persists the most recent N agent runs in IndexedDB so users can replay
 * past tool sequences without hitting the backend again. Falls back to
 * localStorage if IndexedDB is unavailable.
 */

import { useCallback, useEffect, useState } from "react";
import type { AgentStepEvent } from "./useAgentStream";

export interface AgentRunRecord {
  id: string; // crypto.randomUUID()
  scope: string; // e.g. "orchestrator" | "valuate" | "setup"
  projectId?: number;
  instruction: string;
  steps: AgentStepEvent[];
  finalAnswer: string;
  startedAt: number;
  durationMs: number;
  status: "done" | "error" | "cancelled";
  error?: string;
}

const DB_NAME = "agent_runs";
const STORE = "runs";
const DB_VERSION = 1;
const MAX_RUNS = 20;

let dbPromise: Promise<IDBDatabase> | null = null;

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB not available"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("startedAt", "startedAt");
        store.createIndex("scope", "scope");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function dbGetAll(scope?: string): Promise<AgentRunRecord[]> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const store = tx.objectStore(STORE);
      const req = store.getAll();
      req.onsuccess = () => {
        const all = (req.result as AgentRunRecord[]) ?? [];
        const filtered = scope ? all.filter((r) => r.scope === scope) : all;
        filtered.sort((a, b) => b.startedAt - a.startedAt);
        resolve(filtered);
      };
      req.onerror = () => reject(req.error);
    });
  } catch {
    // localStorage fallback
    try {
      const raw = localStorage.getItem(DB_NAME);
      const all = raw ? (JSON.parse(raw) as AgentRunRecord[]) : [];
      return scope ? all.filter((r) => r.scope === scope) : all;
    } catch {
      return [];
    }
  }
}

async function dbPut(record: AgentRunRecord): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(record);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    // Trim to MAX_RUNS
    const all = await dbGetAll();
    if (all.length > MAX_RUNS) {
      const toDelete = all.slice(MAX_RUNS);
      const db2 = await openDB();
      const tx = db2.transaction(STORE, "readwrite");
      const store = tx.objectStore(STORE);
      for (const r of toDelete) store.delete(r.id);
    }
  } catch {
    try {
      const raw = localStorage.getItem(DB_NAME);
      const all = raw ? (JSON.parse(raw) as AgentRunRecord[]) : [];
      all.unshift(record);
      localStorage.setItem(DB_NAME, JSON.stringify(all.slice(0, MAX_RUNS)));
    } catch {
      /* noop */
    }
  }
}

async function dbDelete(id: string): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    try {
      const raw = localStorage.getItem(DB_NAME);
      const all = raw ? (JSON.parse(raw) as AgentRunRecord[]) : [];
      localStorage.setItem(
        DB_NAME,
        JSON.stringify(all.filter((r) => r.id !== id)),
      );
    } catch {
      /* noop */
    }
  }
}

export function useAgentHistory(scope?: string) {
  const [records, setRecords] = useState<AgentRunRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRecords(await dbGetAll(scope));
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = useCallback(
    async (record: Omit<AgentRunRecord, "id">): Promise<string> => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `run_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      const full: AgentRunRecord = { ...record, id };
      await dbPut(full);
      await refresh();
      return id;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await dbDelete(id);
      await refresh();
    },
    [refresh],
  );

  return { records, loading, save, remove, refresh };
}
