import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Spin, message } from "antd";
import type { CalcSummary, DashboardSummary, Project } from "../api";
import { api } from "../api";

interface ProjectStats {
  project: Project;
  dash?: DashboardSummary;
  calc?: CalcSummary;
}

const PROJECT_ICONS = ["apartment", "factory", "stadium", "school", "warehouse", "cottage"];

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [statsMap, setStatsMap] = useState<Map<number, ProjectStats>>(new Map());
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatMsgs, setChatMsgs] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatBodyRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const projs = await api.listProjects();
        setProjects(projs);

        const map = new Map<number, ProjectStats>();
        await Promise.all(
          projs.map(async (p) => {
            const entry: ProjectStats = { project: p };
            try { entry.dash = await api.getDashboardSummary(p.id); } catch { /* ok */ }
            try { entry.calc = await api.getCalcSummary(p.id); } catch { /* ok */ }
            map.set(p.id, entry);
          }),
        );
        setStatsMap(map);
      } catch {
        message.error("加载项目失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    chatBodyRef.current?.scrollTo({ top: chatBodyRef.current.scrollHeight, behavior: "smooth" });
  }, [chatMsgs]);

  const sendChat = async (text?: string) => {
    const msg = (text ?? chatInput).trim();
    if (!msg || chatLoading) return;
    setChatInput("");
    const userMsg = { role: "user" as const, content: msg };
    const history = [...chatMsgs, userMsg];
    setChatMsgs(history);
    setChatLoading(true);
    try {
      const pid = projects[0]?.id;
      if (!pid) {
        setChatMsgs([...history, { role: "assistant", content: "暂无项目数据，请先创建项目。" }]);
        setChatLoading(false);
        return;
      }
      const res = await api.aiChat(
        pid,
        msg,
        chatMsgs.map((m) => ({ role: m.role, content: m.content })),
      );
      if (res.reply) {
        setChatMsgs([...history, { role: "assistant", content: res.reply }]);
      } else {
        setChatMsgs([...history, { role: "assistant", content: "AI 服务未配置。请在「系统设置」中配置 API Key 后即可使用智能助手。" }]);
      }
    } catch {
      setChatMsgs([...history, { role: "assistant", content: "请求失败，请稍后重试。" }]);
    }
    setChatLoading(false);
  };

  const allStats = useMemo(() => Array.from(statsMap.values()), [statsMap]);

  const grandTotal = useMemo(
    () => allStats.reduce((s, st) => s + (st.calc?.grand_total ?? 0), 0),
    [allStats],
  );

  const totalIssues = useMemo(
    () => allStats.reduce((s, st) => s + (st.dash?.validation_total ?? 0), 0),
    [allStats],
  );

  const totalBoq = useMemo(
    () => allStats.reduce((s, st) => s + (st.dash?.boq_count ?? 0), 0),
    [allStats],
  );

  const totalUnbound = useMemo(
    () => allStats.reduce((s, st) => s + (st.dash?.unbound_count ?? 0), 0),
    [allStats],
  );

  const unboundPct = totalBoq > 0 ? ((totalUnbound / totalBoq) * 100).toFixed(1) : "0";

  const topProject = allStats[0];
  const heroName = topProject?.project.name || "—";
  const heroBoqCount = topProject?.dash?.boq_count ?? 0;
  const heroUnbound = topProject?.dash?.unbound_count ?? 0;
  const heroProgress = heroBoqCount > 0 ? Math.round(((heroBoqCount - heroUnbound) / heroBoqCount) * 100) : 0;

  const workflowSteps = useMemo(() => {
    const boundPct = heroBoqCount > 0 ? (heroBoqCount - heroUnbound) / heroBoqCount : 0;
    const hasCalc = !!topProject?.calc && topProject.calc.grand_total > 0;
    const hasValidation = (topProject?.dash?.validation_total ?? -1) >= 0;
    const noErrors = (topProject?.dash?.validation_errors ?? 0) === 0;

    return [
      { icon: "upload_file", label: "图纸上传", done: heroBoqCount > 0 },
      { icon: "scan", label: "AI 识别", done: heroBoqCount > 0 },
      { icon: "list_alt", label: "清单生成", done: heroBoqCount > 0 },
      { icon: "rate_review", label: "单价核对", done: boundPct >= 0.5, current: boundPct > 0 && boundPct < 1 },
      { icon: "done_all", label: "AI 审核完成", done: hasCalc && hasValidation && noErrors },
    ];
  }, [topProject, heroBoqCount, heroUnbound]);

  const analysisRows = useMemo(() => {
    return allStats.slice(0, 5).map((st, i) => {
      const vErrors = st.dash?.validation_errors ?? 0;
      const vWarnings = st.dash?.validation_warnings ?? 0;
      const vTotal = st.dash?.validation_total ?? 0;
      const boq = st.dash?.boq_count ?? 0;
      const unbound = st.dash?.unbound_count ?? 0;
      const bound = boq - unbound;
      const accuracy = boq > 0 ? Math.min(99.9, (bound / boq) * 100) : 0;
      const accColor = accuracy >= 95 ? "green" : accuracy >= 80 ? "blue" : "orange";

      let finding: string;
      let findingCls: string;
      if (vErrors > 0) {
        finding = `${vErrors} 处错误`;
        findingCls = "danger";
      } else if (vWarnings > 0) {
        finding = `${vWarnings} 处警告`;
        findingCls = "warn";
      } else if (vTotal > 0) {
        finding = `${vTotal} 处提示`;
        findingCls = "warn";
      } else if (unbound > 0) {
        finding = `${unbound} 项未绑定`;
        findingCls = "warn";
      } else {
        finding = "暂无明显问题";
        findingCls = "muted";
      }

      return {
        id: st.project.id,
        name: st.project.name,
        icon: PROJECT_ICONS[i % PROJECT_ICONS.length],
        accuracy: +accuracy.toFixed(1),
        accColor,
        finding,
        findingCls,
      };
    });
  }, [allStats]);

  if (loading) {
    return (
      <div className="dash-root">
        <div className="dash-loading"><Spin size="large" /><p>加载仪表盘...</p></div>
      </div>
    );
  }

  const fmtBudget = (v: number) => {
    if (v >= 1_0000_0000) return `¥${(v / 1_0000_0000).toFixed(1)}亿`;
    if (v >= 1_0000) return `¥${(v / 1_0000).toFixed(0)}万`;
    return `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
  };

  return (
    <div className="dash-root">
      <div className="dash-content">

        {/* ── Hero Section ── */}
        <section className="dash-hero-grid">
          {/* AI Status Hero */}
          <div className="dash-hero-card">
            <div className="dash-hero-glow" />
            <div className="dash-hero-inner">
              <div className="dash-hero-badge">
                <span className="material-symbols-outlined dash-hero-badge-icon">auto_awesome</span>
                <span>AI 实时处理引擎</span>
              </div>
              <h2 className="dash-hero-title">AI 自动识别状态</h2>
              <p className="dash-hero-desc">
                当前正在深度解析：<strong>{heroName}</strong>
              </p>
            </div>
            <div className="dash-hero-progress-section">
              <div className="dash-hero-progress-head">
                <span>定额绑定与造价计算进度</span>
                <span>{heroProgress}%</span>
              </div>
              <div className="dash-hero-progress-track">
                <div className="dash-hero-progress-fill" style={{ width: `${heroProgress}%` }} />
              </div>
              <div className="dash-hero-stats">
                <span><span className="material-symbols-outlined">list_alt</span>清单项: {heroBoqCount} 条</span>
                <span><span className="material-symbols-outlined">check_circle</span>已绑定: {heroBoqCount - heroUnbound} 条</span>
              </div>
            </div>
          </div>

          {/* AI Assistant */}
          <div className="dash-ai-chat">
            <div className="dash-ai-chat-head">
              <h3>AI 助手</h3>
              <span className="dash-ai-online">{chatLoading ? "思考中..." : "在线"}</span>
            </div>
            <div className="dash-ai-chat-body" ref={chatBodyRef}>
              {chatMsgs.length === 0 ? (
                <>
                  <div className="dash-ai-msg bot">
                    <p>您好！我是您的造价 AI 助手。已为您检测到 {projects.length} 个项目中共 {totalIssues} 处异常，是否现在查看？</p>
                  </div>
                  <div className="dash-ai-quick-prompts">
                    {["查看异常列表", "项目整体进展如何？", "哪些清单项还未绑定？", "费用构成是否合理？"].map((q) => (
                      <button key={q} className="dash-ai-quick-btn" onClick={() => sendChat(q)}>{q}</button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  {chatMsgs.map((m, i) => (
                    <div key={i} className={`dash-ai-msg ${m.role === "user" ? "user" : "bot"}`}>
                      <p>{m.content}</p>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="dash-ai-msg bot">
                      <p className="dash-ai-typing"><span /><span /><span /></p>
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="dash-ai-chat-input">
              <input
                placeholder="提问 AI..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") sendChat(); }}
                disabled={chatLoading}
              />
              <button onClick={() => sendChat()} disabled={chatLoading || !chatInput.trim()}>
                <span className="material-symbols-outlined">send</span>
              </button>
            </div>
          </div>
        </section>

        {/* ── Statistics Cards ── */}
        <section className="dash-stat-grid">
          <div className="dash-stat-card">
            <div className="dash-stat-top">
              <div className="dash-stat-icon blue"><span className="material-symbols-outlined">payments</span></div>
              <span className="dash-stat-badge green">{grandTotal > 0 ? "已计算" : "待计算"}</span>
            </div>
            <p className="dash-stat-label">项目总估值</p>
            <h4 className="dash-stat-value">{fmtBudget(grandTotal)}</h4>
          </div>
          <div className="dash-stat-card">
            <div className="dash-stat-top">
              <div className="dash-stat-icon purple"><span className="material-symbols-outlined">account_tree</span></div>
              <span className="dash-stat-badge muted">实时</span>
            </div>
            <p className="dash-stat-label">活跃项目数</p>
            <h4 className="dash-stat-value">{projects.length}</h4>
          </div>
          <div className="dash-stat-card">
            <div className="dash-stat-top">
              <div className="dash-stat-icon red"><span className="material-symbols-outlined">error_outline</span></div>
              <span className={`dash-stat-badge ${totalIssues > 0 ? "red" : "green"}`}>
                {totalIssues > 0 ? "需关注" : "正常"}
              </span>
            </div>
            <p className="dash-stat-label">AI 审核异常</p>
            <h4 className="dash-stat-value">{totalIssues}</h4>
          </div>
          <div className="dash-stat-card">
            <div className="dash-stat-top">
              <div className="dash-stat-icon amber"><span className="material-symbols-outlined">lightbulb</span></div>
              <span className={`dash-stat-badge ${totalUnbound > 0 ? "amber" : "green"}`}>
                {totalUnbound > 0 ? "可优化" : "完成"}
              </span>
            </div>
            <p className="dash-stat-label">未绑定定额比例</p>
            <h4 className="dash-stat-value">{unboundPct}%</h4>
          </div>
        </section>

        {/* ── Workflow ── */}
        <section className="dash-workflow-card">
          <h3 className="dash-workflow-title">项目标准作业流程 (Workflow) — {heroName}</h3>
          <div className="dash-workflow-track">
            <div className="dash-workflow-line" />
            <div className="dash-workflow-line-active" />
            {workflowSteps.map((step, i) => (
              <div key={i} className={`dash-workflow-step ${step.done ? "done" : ""} ${step.current ? "current" : ""}`}>
                <div className="dash-workflow-circle">
                  <span className="material-symbols-outlined">{step.icon}</span>
                </div>
                <span className="dash-workflow-label">{step.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── AI Analysis Table ── */}
        <section className="dash-analysis-card">
          <div className="dash-analysis-head">
            <h3>近期 AI 分析记录</h3>
            <button className="dash-link-btn" onClick={() => navigate("/projects")}>
              查看全部 <span className="material-symbols-outlined">chevron_right</span>
            </button>
          </div>
          <div className="dash-analysis-table-wrap">
            <table className="dash-analysis-table">
              <thead>
                <tr>
                  <th>项目名称</th>
                  <th style={{ textAlign: "center" }}>绑定完成度</th>
                  <th>潜在错误发现</th>
                  <th>清单项数</th>
                  <th style={{ textAlign: "right" }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {analysisRows.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>暂无项目数据</td></tr>
                )}
                {analysisRows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className="dash-analysis-name">
                        <div className="dash-analysis-icon">
                          <span className="material-symbols-outlined">{row.icon}</span>
                        </div>
                        <span>{row.name}</span>
                      </div>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <div className="dash-accuracy">
                        <span className={`dash-accuracy-val ${row.accColor}`}>{row.accuracy}%</span>
                        <div className="dash-accuracy-bar">
                          <div className={`dash-accuracy-fill ${row.accColor}`} style={{ width: `${row.accuracy}%` }} />
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`dash-finding ${row.findingCls}`}>{row.finding}</span>
                    </td>
                    <td className="dash-analysis-time">{statsMap.get(row.id)?.dash?.boq_count ?? 0} 条</td>
                    <td style={{ textAlign: "right" }}>
                      <button className="dash-detail-btn" onClick={() => navigate(`/projects/${row.id}`)}>详情</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </div>
  );
}
