import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Badge, message, Tooltip } from "antd";
import type { BoqItem, CalcSummary, Project } from "../api";
import { api } from "../api";
import AiPanel from "../components/AiPanel";
import ValuationWizard from "../components/ValuationWizard";
import DashboardTab from "../components/DashboardTab";
import BoqTab from "../components/BoqTab";
import BindingTab from "../components/BindingTab";
import CalcTab from "../components/CalcTab";
import ValidationTab from "../components/ValidationTab";
import SnapshotTab from "../components/SnapshotTab";
import SettingsTab from "../components/SettingsTab";
import ReportView from "../components/ReportView";
import ProjectSetupWizard from "../components/ProjectSetupWizard";
import OtherItemsTab from "../components/OtherItemsTab";

type View = "dashboard" | "boq" | "binding" | "calc" | "validation" | "snapshot" | "report" | "setup" | "settings" | "other";

interface NavItem {
  key: View;
  icon: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { key: "dashboard", icon: "dashboard", label: "仪表盘" },
  { key: "boq", icon: "account_tree", label: "清单树" },
  { key: "binding", icon: "link", label: "定额绑定" },
  { key: "calc", icon: "calculate", label: "计算溯源" },
  { key: "validation", icon: "verified", label: "校验" },
  { key: "snapshot", icon: "photo_camera", label: "快照对比" },
  { key: "report", icon: "summarize", label: "计价报告" },
  { key: "setup", icon: "rocket_launch", label: "智能开项" },
  { key: "other", icon: "receipt_long", label: "其他项目费" },
  { key: "settings", icon: "settings", label: "设置" },
];

const VIEW_META: Record<View, { title: string; desc: string }> = {
  dashboard: { title: "项目概览", desc: "查看项目统计与活动记录" },
  boq: { title: "清单管理", desc: "管理本项目工程量与智能组价" },
  binding: { title: "定额绑定", desc: "管理清单与定额的匹配关系" },
  calc: { title: "计算 & 溯源", desc: "执行计价计算并查看明细" },
  validation: { title: "校验", desc: "检查项目数据完整性与正确性" },
  snapshot: { title: "快照 & 差异", desc: "创建快照并对比历史版本" },
  report: { title: "计价报告", desc: "查看费用汇总、分部分项计价表，导出 Excel/PDF" },
  setup: { title: "智能开项", desc: "输入工程描述，AI 自动生成工程量清单" },
  other: { title: "其他项目费", desc: "管理暂列金额、暂估价、计日工、总承包服务费及规费明细" },
  settings: { title: "项目设置", desc: "规则包、材料价格、成员管理" },
};

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const pid = Number(id);
  const [view, setView] = useState<View>("boq");
  const [project, setProject] = useState<Project | null>(null);
  const [boqItems, setBoqItems] = useState<BoqItem[]>([]);
  const [calcResult, setCalcResult] = useState<CalcSummary | null>(null);
  const [boqVersion, setBoqVersion] = useState(0);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [activeDivision, setActiveDivision] = useState<string | undefined>(undefined);

  // Fetch project info
  useEffect(() => {
    api.getProject(pid)
      .then((p) => setProject(p))
      .catch(() => {});
  }, [pid]);

  // Fetch boq items (re-fetch when boqVersion changes)
  useEffect(() => {
    api.listBoqItems(pid).then(setBoqItems).catch(() => {});
  }, [pid, boqVersion]);

  // Auto-load calc results on mount and when boq data changes
  useEffect(() => {
    api.calculate(pid).then(setCalcResult).catch(() => {});
  }, [pid, boqVersion]);

  const refreshBoq = useCallback(() => setBoqVersion((v) => v + 1), []);

  // Group divisions from boq items
  const divisions = [...new Set(boqItems.map((b) => b.division).filter(Boolean))];
  useEffect(() => {
    if (activeDivision && !divisions.includes(activeDivision)) {
      setActiveDivision(undefined);
    }
  }, [activeDivision, divisions]);
  const totalCount = boqItems.length;
  // Progress: rough estimate based on calc availability
  const calcedCount = calcResult ? calcResult.line_results.length : 0;
  const progress = totalCount > 0 ? Math.round((calcedCount / totalCount) * 100) : 0;

  const meta = VIEW_META[view];

  // Header: 一键智能组价 — open wizard
  const handleOpenWizard = () => setWizardOpen(true);

  // Unbound count for badge
  const unboundCount = useMemo(() => {
    if (!calcResult) return boqItems.length;
    const calcedIds = new Set(calcResult.line_results.map((r: any) => r.boq_item_id ?? r.boq_id));
    return boqItems.filter((b) => !calcedIds.has(b.id)).length;
  }, [boqItems, calcResult]);

  // Keyboard shortcut: Ctrl+1~9 to switch views
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      const idx = parseInt(e.key, 10);
      if (idx >= 1 && idx <= NAV_ITEMS.length) {
        e.preventDefault();
        setView(NAV_ITEMS[idx - 1].key);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleWizardComplete = (result: CalcSummary) => {
    setCalcResult(result);
    refreshBoq();
    message.success(`组价完成，合计 ¥${result.grand_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`);
  };

  // Header: 导出报告
  const handleExport = () => {
    const url = api.exportValuationUrl(pid);
    const form = document.createElement("form");
    form.method = "POST";
    form.action = url;
    form.target = "_blank";
    document.body.appendChild(form);
    form.submit();
    form.remove();
  };

  const renderContent = () => {
    switch (view) {
      case "dashboard": return <DashboardTab projectId={pid} />;
      case "boq":
        return (
          <BoqTab
            projectId={pid}
            project={project}
            calcResult={calcResult}
            onDataChanged={refreshBoq}
            activeDivision={activeDivision}
            onActiveDivisionChange={setActiveDivision}
          />
        );
      case "binding": return <BindingTab projectId={pid} />;
      case "calc": return <CalcTab projectId={pid} />;
      case "validation": return <ValidationTab projectId={pid} />;
      case "snapshot": return <SnapshotTab projectId={pid} />;
      case "report": return <ReportView projectId={pid} />;
      case "setup": return <ProjectSetupWizard projectId={pid} onComplete={() => { refreshBoq(); setView("boq"); }} />;
      case "other": return <OtherItemsTab projectId={pid} />;
      case "settings": return <SettingsTab projectId={pid} />;
    }
  };

  return (
    <div className="layout-main">
      {/* Left Sidebar */}
      <aside className="sidebar-left">
        <div className="sidebar-project-info">
          <div className="sidebar-project-header">
            <div className="sidebar-project-icon">
              <span className="material-symbols-outlined">domain</span>
            </div>
            <div style={{ overflow: "hidden" }}>
              <div className="sidebar-project-name">{project?.name ?? `项目 #${pid}`}</div>
              <div className="sidebar-project-type">{project?.region ?? "工程计价"}</div>
            </div>
          </div>
          <div className="sidebar-progress">
            <div className="sidebar-progress-label">
              <span>完成进度</span>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>{progress}%</span>
            </div>
            <div className="sidebar-progress-bar">
              <div
                className="sidebar-progress-bar-fill"
                style={{
                  width: `${progress}%`,
                  background: progress >= 80 ? "#22c55e" : progress >= 50 ? "var(--primary)" : "#f59e0b",
                }}
              />
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-nav-section">视图控制</div>
          {NAV_ITEMS.map((item, idx) => {
            const showBadge = item.key === "binding" && unboundCount > 0;
            return (
              <Tooltip key={item.key} title={`${item.label} (⌘${idx + 1})`} placement="right" mouseEnterDelay={0.5}>
                <button
                  className={`sidebar-nav-item${view === item.key ? " active" : ""}`}
                  onClick={() => {
                    setView(item.key);
                    if (item.key !== "boq") setActiveDivision(undefined);
                  }}
                >
                  <span className="material-symbols-outlined">{item.icon}</span>
                  <span>{item.label}</span>
                  {showBadge && (
                    <Badge count={unboundCount} size="small" offset={[4, -2]} style={{ fontSize: 10 }} />
                  )}
                </button>
              </Tooltip>
            );
          })}

          {divisions.length > 0 && (
            <>
              <div className="sidebar-nav-section">分部工程</div>
              {divisions.map((div, i) => (
                <div
                  key={div}
                  className={`sidebar-tree-item${activeDivision === div ? " active" : ""}`}
                  onClick={() => {
                    setView("boq");
                    setActiveDivision(div);
                  }}
                >
                  <span className="material-symbols-outlined">folder</span>
                  <span>{i + 1}. {div}</span>
                </div>
              ))}
            </>
          )}
        </nav>
      </aside>

      {/* Center Content */}
      <section className="content-center">
        <div className="content-header">
          <div className="content-header-info">
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <h2 style={{ margin: 0 }}>{meta.title}</h2>
              {project?.status && (
                <span className={`pmc-status pmc-status-${project.status}`} style={{ fontSize: 11 }}>
                  {project.status === "draft" ? "草稿" : project.status === "ongoing" ? "进行中" : project.status === "completed" ? "已完成" : "已归档"}
                </span>
              )}
            </div>
            <p>{meta.desc}</p>
          </div>
          <div className="content-header-actions">
            <button className="btn-secondary" onClick={handleExport}>
              <span className="material-symbols-outlined">download</span>
              <span>导出报告</span>
            </button>
            <button className="btn-primary" onClick={handleOpenWizard}>
              <span className="material-symbols-outlined">auto_awesome</span>
              <span>一键智能组价</span>
            </button>
            <button className="btn-secondary" onClick={() => setView("setup")} style={{ marginLeft: 4 }}>
              <span className="material-symbols-outlined">rocket_launch</span>
              <span>全流程</span>
            </button>
          </div>
        </div>
        <div className="content-body">
          {renderContent()}
        </div>
      </section>

      {/* Right AI Panel */}
      <AiPanel projectId={pid} />

      {/* Valuation Wizard */}
      <ValuationWizard
        projectId={pid}
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onComplete={handleWizardComplete}
      />
    </div>
  );
}
