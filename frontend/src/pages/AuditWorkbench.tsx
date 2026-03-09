import { useEffect, useState } from "react";
import { Select, DatePicker, Input, Tag, Spin, Empty, message } from "antd";
import dayjs from "dayjs";
import PageBreadcrumb from "../components/PageBreadcrumb";
import { api } from "../api";
import type { AuditLog, Project } from "../api";

const { RangePicker } = DatePicker;

/* ── Helpers ── */

function tryParseJSON(s: string | null): unknown | null {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return s; }
}

function renderJsonDiff(before: unknown, after: unknown) {
  const bStr = before ? JSON.stringify(before, null, 2) : "—";
  const aStr = after ? JSON.stringify(after, null, 2) : "—";
  return (
    <div className="audit-diff-grid">
      <div className="audit-diff-col">
        <span className="audit-diff-label">变更前</span>
        <pre className="audit-diff-pre before">{bStr}</pre>
      </div>
      <div className="audit-diff-col">
        <span className="audit-diff-label">变更后</span>
        <pre className="audit-diff-pre after">{aStr}</pre>
      </div>
    </div>
  );
}

const ACTION_COLORS: Record<string, string> = {
  create: "green",
  update: "blue",
  delete: "red",
  import: "purple",
  calculate: "orange",
  bind: "cyan",
  unbind: "magenta",
};

/* ── Component ── */

export default function AuditWorkbench() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actorFilter, setActorFilter] = useState("");
  const [actionFilter, setActionFilter] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedProject) { setLogs([]); return; }
    setLoading(true);
    api.listAuditLogs(selectedProject)
      .then(setLogs)
      .catch(() => message.error("加载审计日志失败"))
      .finally(() => setLoading(false));
  }, [selectedProject]);

  /* Filtered logs */
  const filtered = logs.filter((log) => {
    if (actorFilter && !log.actor.toLowerCase().includes(actorFilter.toLowerCase())) return false;
    if (actionFilter && log.action !== actionFilter) return false;
    if (dateRange && dateRange[0] && dateRange[1]) {
      const ts = dayjs(log.timestamp);
      if (ts.isBefore(dateRange[0], "day") || ts.isAfter(dateRange[1], "day")) return false;
    }
    return true;
  });

  const uniqueActors = [...new Set(logs.map((l) => l.actor))];
  const uniqueActions = [...new Set(logs.map((l) => l.action))];

  /* AI summary */
  const requestAISummary = async () => {
    if (!selectedProject) return;
    setAiLoading(true);
    setAiSummary(null);
    try {
      const resp = await api.aiAnalyze(selectedProject, "audit", {
        total_logs: filtered.length,
        actions: uniqueActions,
        actors: uniqueActors,
        recent_logs: filtered.slice(0, 20).map((l) => ({
          actor: l.actor,
          action: l.action,
          resource_type: l.resource_type,
          timestamp: l.timestamp,
        })),
      });
      setAiSummary(resp.insight || "无分析结果");
    } catch {
      setAiSummary("AI 分析失败");
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: 24 }}>
      <PageBreadcrumb items={[
        { label: "控制台", path: "/dashboard" },
        { label: "审计管理" },
      ]} />

      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>审计工作台</h2>
        <button
          className="dr-btn-outline"
          onClick={requestAISummary}
          disabled={aiLoading || !selectedProject}
          style={{ fontSize: 13 }}
        >
          {aiLoading ? <Spin size="small" /> : <span className="material-symbols-outlined" style={{ fontSize: 16, marginRight: 4 }}>smart_toy</span>}
          AI 审计摘要
        </button>
      </header>

      {/* Filters */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <Select
          placeholder="选择项目"
          style={{ width: 220 }}
          value={selectedProject}
          onChange={setSelectedProject}
          options={projects.map((p) => ({ label: p.name, value: p.id }))}
          allowClear
        />
        <Input
          placeholder="操作人筛选"
          style={{ width: 160 }}
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          allowClear
        />
        <Select
          placeholder="操作类型"
          style={{ width: 140 }}
          value={actionFilter}
          onChange={setActionFilter}
          options={uniqueActions.map((a) => ({ label: a, value: a }))}
          allowClear
        />
        <RangePicker
          value={dateRange as any}
          onChange={(v) => setDateRange(v as any)}
          style={{ width: 240 }}
        />
        <span style={{ color: "var(--text-muted)", fontSize: 13, lineHeight: "32px" }}>
          {filtered.length} / {logs.length} 条记录
        </span>
      </div>

      {/* AI Summary Card */}
      {aiSummary && (
        <div style={{
          background: "rgba(20,86,184,0.08)",
          border: "1px solid rgba(20,86,184,0.2)",
          borderRadius: 8,
          padding: "12px 16px",
          marginBottom: 16,
          fontSize: 13,
          color: "var(--text-secondary)",
          whiteSpace: "pre-wrap",
        }}>
          <strong style={{ color: "var(--primary)" }}>AI 审计摘要</strong>
          <div style={{ marginTop: 6 }}>{aiSummary}</div>
        </div>
      )}

      {/* Log List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 48 }}><Spin /></div>
      ) : !selectedProject ? (
        <Empty description="请选择项目" />
      ) : filtered.length === 0 ? (
        <Empty description="无审计记录" />
      ) : (
        <div className="audit-log-list">
          {filtered.map((log) => {
            const expanded = expandedId === log.id;
            return (
              <div
                key={log.id}
                className={`audit-log-item ${expanded ? "expanded" : ""}`}
                onClick={() => setExpandedId(expanded ? null : log.id)}
              >
                <div className="audit-log-row">
                  <Tag color={ACTION_COLORS[log.action] || "default"} style={{ fontSize: 11 }}>{log.action}</Tag>
                  <span className="audit-log-resource">{log.resource_type}{log.resource_id ? ` #${log.resource_id}` : ""}</span>
                  <span className="audit-log-actor">{log.actor}</span>
                  <span className="audit-log-time">{dayjs(log.timestamp).format("YYYY-MM-DD HH:mm:ss")}</span>
                  <span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--text-muted)" }}>
                    {expanded ? "expand_less" : "expand_more"}
                  </span>
                </div>
                {expanded && (
                  <div className="audit-log-detail" onClick={(e) => e.stopPropagation()}>
                    {renderJsonDiff(tryParseJSON(log.before_json), tryParseJSON(log.after_json))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        .audit-log-list { display: flex; flex-direction: column; gap: 2px; }
        .audit-log-item {
          background: var(--bg-elevated, #1c2537);
          border-radius: 6px;
          cursor: pointer;
          transition: background 0.15s;
        }
        .audit-log-item:hover { background: rgba(30,41,59,0.8); }
        .audit-log-item.expanded { background: rgba(30,41,59,0.9); }
        .audit-log-row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          font-size: 13px;
        }
        .audit-log-resource { flex: 1; color: var(--text-primary, #e2e8f0); font-weight: 500; }
        .audit-log-actor { color: var(--text-muted, #94a3b8); min-width: 80px; }
        .audit-log-time { color: var(--text-muted, #94a3b8); font-size: 12px; min-width: 140px; text-align: right; }
        .audit-log-detail { padding: 0 14px 14px; }
        .audit-diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .audit-diff-col { display: flex; flex-direction: column; }
        .audit-diff-label { font-size: 11px; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
        .audit-diff-pre {
          font-size: 11px;
          background: rgba(0,0,0,0.3);
          border-radius: 4px;
          padding: 8px;
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-all;
          max-height: 240px;
          overflow-y: auto;
          margin: 0;
        }
        .audit-diff-pre.before { color: #f87171; border-left: 2px solid #f87171; }
        .audit-diff-pre.after { color: #4ade80; border-left: 2px solid #4ade80; }
      `}</style>
    </div>
  );
}
