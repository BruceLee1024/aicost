import { useEffect, useState } from "react";
import {
  Card, Col, Row, Statistic, Timeline, Input, Tag, message,
} from "antd";
import {
  CommentOutlined, SendOutlined,
  ClockCircleOutlined, UserOutlined,
} from "@ant-design/icons";
import type { AuditLog, CommentItem, DashboardSummary } from "../api";
import { api } from "../api";

interface Props { projectId: number }

const formatTime = (iso: string) => {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" }) +
      " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
};

export default function DashboardTab({ projectId }: Props) {
  const [boqCount, setBoqCount] = useState(0);
  const [unboundCount, setUnboundCount] = useState(0);
  const [dirtyCount, setDirtyCount] = useState(0);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [commentText, setCommentText] = useState("");
  const [commentAuthor, setCommentAuthor] = useState(() => localStorage.getItem("userName") || "用户");
  const [aiInsight, setAiInsight] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    api.getDashboardSummary(projectId).then((s) => {
      setSummary(s);
      setBoqCount(s.boq_count);
      setUnboundCount(s.unbound_count);
      setDirtyCount(s.dirty_count);
      // Fetch AI insight with dashboard data
      setAiLoading(true);
      api.aiAnalyze(projectId, "dashboard", {
        boq_count: s.boq_count,
        unbound_count: s.unbound_count,
        dirty_count: s.dirty_count,
        validation_total: s.validation_total,
        validation_errors: s.validation_errors,
        validation_warnings: s.validation_warnings,
      }).then((res) => {
        setAiInsight(res.insight);
      }).catch(() => {}).finally(() => setAiLoading(false));
    }).catch(() => {});
    api.listAuditLogs(projectId).then((r) => setLogs(r.slice(0, 8))).catch(() => {});
    api.listComments(projectId).then(setComments).catch(() => {});
  }, [projectId]);

  const handleComment = async () => {
    if (!commentText.trim()) return;
    try {
      await api.addComment(projectId, commentAuthor, commentText.trim());
      setCommentText("");
      setComments(await api.listComments(projectId));
      message.success("评论已发送");
    } catch { message.error("发送失败"); }
  };

  const updateAuthor = (name: string) => {
    setCommentAuthor(name);
    localStorage.setItem("userName", name);
  };

  const actionLabels: Record<string, string> = {
    create_boq_item: "创建清单项",
    update_boq_item: "更新清单项",
    delete_boq_item: "删除清单项",
    bind_rule_package: "绑定规则包",
  };

  return (
    <div>
      {/* AI Insight Card */}
      <div className="ai-insight-card">
        <div className="ai-insight-card-header">
          <div className="ai-insight-card-icon">
            <span className="material-symbols-outlined">psychology</span>
          </div>
          <span className="ai-insight-card-title">AI 项目洞察</span>
        </div>
        <div className="ai-insight-card-body">
          {aiLoading ? (
            <div>
              <div className="ai-insight-shimmer" />
              <div className="ai-insight-shimmer" />
              <div className="ai-insight-shimmer" />
            </div>
          ) : aiInsight ? (
            aiInsight
          ) : (
            <span style={{ color: "var(--text-muted)" }}>
              {boqCount === 0
                ? "项目尚无清单数据，请先导入或创建清单项。"
                : `项目包含 ${boqCount} 个清单项，${unboundCount} 个未绑定，${dirtyCount} 个待重算。配置 AI API Key 后可获取智能分析。`}
            </span>
          )}
        </div>
      </div>

      {/* Stat Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <div className="stat-card">
            <div className="stat-card-icon blue"><span className="material-symbols-outlined">description</span></div>
            <Statistic title="清单项总数" value={boqCount} />
          </div>
        </Col>
        <Col span={6}>
          <div className="stat-card">
            <div className="stat-card-icon red"><span className="material-symbols-outlined">link_off</span></div>
            <Statistic
              title="未绑定定额" value={unboundCount}
              styles={unboundCount > 0 ? { content: { color: "#ef4444" } } : undefined}
            />
          </div>
        </Col>
        <Col span={6}>
          <div className="stat-card">
            <div className="stat-card-icon orange"><span className="material-symbols-outlined">sync</span></div>
            <Statistic
              title="待重算" value={dirtyCount}
              styles={dirtyCount > 0 ? { content: { color: "#f59e0b" } } : undefined}
            />
          </div>
        </Col>
        <Col span={6}>
          <div className="stat-card">
            <div className="stat-card-icon purple"><span className="material-symbols-outlined">warning</span></div>
            <Statistic
              title="校验问题" value={summary?.validation_total ?? 0}
              styles={(summary?.validation_errors ?? 0) > 0 ? { content: { color: "#ef4444" } } : undefined}
            />
          </div>
        </Col>
      </Row>

      {/* Activity & Comments */}
      <Row gutter={20}>
        <Col span={12}>
          <Card
            title={
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <ClockCircleOutlined style={{ color: "var(--primary)" }} /> 最近操作记录
              </span>
            }
            size="small"
          >
            {logs.length === 0 ? (
              <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: 32 }}>暂无记录</div>
            ) : (
              <Timeline
                items={logs.map((l) => ({
                  content: (
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Tag color="blue" style={{ margin: 0 }}>{actionLabels[l.action] ?? l.action}</Tag>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{formatTime(l.timestamp)}</span>
                    </div>
                  ),
                }))}
              />
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title={
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <CommentOutlined style={{ color: "#8b5cf6" }} /> 项目评论
              </span>
            }
            size="small"
          >
            <div style={{ maxHeight: 300, overflowY: "auto", marginBottom: 12 }}>
              {comments.length === 0 ? (
                <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: 24 }}>暂无评论</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {comments.map((c) => (
                    <div key={c.id} style={{ display: "flex", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                        background: "var(--primary)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        color: "#fff", fontSize: 14,
                      }}>
                        <UserOutlined />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{c.author}</div>
                        <div style={{ color: "var(--text-secondary)", marginTop: 2 }}>{c.content}</div>
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{formatTime(c.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: "var(--text-secondary)", flexShrink: 0 }}>昵称：</span>
              <Input
                size="small"
                value={commentAuthor}
                onChange={(e) => updateAuthor(e.target.value)}
                style={{ width: 100 }}
              />
            </div>
            <Input.Search
              placeholder="输入评论..."
              enterButton={<SendOutlined />}
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              onSearch={handleComment}
              style={{ borderRadius: 12 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
