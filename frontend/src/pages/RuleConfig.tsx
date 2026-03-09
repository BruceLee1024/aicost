import { useState } from "react";
import { message, Switch } from "antd";
import PageBreadcrumb from "../components/PageBreadcrumb";

type SeverityKey = "critical" | "warning" | "notice";
type RuleTab = "material" | "labor" | "compliance" | "custom" | "audit";

interface Rule {
  id: string;
  name: string;
  description: string;
  threshold: string;
  enabled: boolean;
  severity: SeverityKey;
  category: RuleTab;
  logic: string;
  linkedStandards: string[];
  lastEdited: string;
}

const INITIAL_RULES: Rule[] = [
  {
    id: "MAT-001", name: "材料价格偏差检测", description: "对比30天区域市场均价，检测异常报价",
    threshold: "> 10.0%", enabled: true, severity: "critical", category: "material",
    logic: 'IF (input.price > market_avg * 1.1)\n  THEN trigger_alert(\n    severity: "CRITICAL",\n    msg: "超出市场均价10%以上"\n  );',
    linkedStandards: ["GB50500-2013 第四章", "地方信息价标准"], lastEdited: "2025-03-05",
  },
  {
    id: "MAT-002", name: "钢筋价格指数校验", description: "钢协指数对标验证，检测报价合理性",
    threshold: "> 5.5%", enabled: true, severity: "warning", category: "material",
    logic: 'IF (abs(input.price - steel_index) / steel_index > 0.055)\n  THEN trigger_alert(\n    severity: "WARNING",\n    msg: "偏离钢协指数5.5%以上"\n  );',
    linkedStandards: ["钢铁协会价格指数 v2"], lastEdited: "2025-02-18",
  },
  {
    id: "LAB-014", name: "模板人工附加费", description: "检测人工与材料异常比值",
    threshold: "> 1.2x 比值", enabled: false, severity: "notice", category: "labor",
    logic: 'IF (labor_cost / material_cost > 1.2)\n  THEN trigger_alert(\n    severity: "NOTICE",\n    msg: "人材比超出阈值"\n  );',
    linkedStandards: ["劳动定额标准 v4.1"], lastEdited: "2025-01-10",
  },
  {
    id: "STD-092", name: "GB50500 编码合规", description: "严格匹配2013版清单项目编码规范",
    threshold: "精确匹配", enabled: true, severity: "critical", category: "compliance",
    logic: 'IF (!matchGBCode(input.boq_code, "GB50500-2013"))\n  THEN trigger_alert(\n    severity: "CRITICAL",\n    msg: "编码不符合GB50500-2013规范"\n  );',
    linkedStandards: ["GB50500-2013", "GB/T50500-2024"], lastEdited: "2025-03-01",
  },
  {
    id: "MAT-045", name: "外加剂掺量审核", description: "AI 检查化学外加剂掺量一致性",
    threshold: "±5% 设计值", enabled: true, severity: "warning", category: "material",
    logic: 'IF (abs(input.dosage - design.dosage) / design.dosage > 0.05)\n  THEN trigger_alert(\n    severity: "WARNING",\n    msg: "掺量偏离设计值5%以上"\n  );',
    linkedStandards: ["GB50500-2013 第四章", "CECS混凝土标准"], lastEdited: "2025-02-25",
  },
  {
    id: "CUS-001", name: "综合单价上限", description: "自定义单价上限预警规则",
    threshold: "> ¥5,000/m³", enabled: true, severity: "warning", category: "custom",
    logic: 'IF (unit_price > 5000 && unit == "m³")\n  THEN trigger_alert(\n    severity: "WARNING",\n    msg: "综合单价超出自定义上限"\n  );',
    linkedStandards: [], lastEdited: "2025-03-04",
  },
  {
    id: "AUD-010", name: "签证变更金额阈值", description: "超过预算5%的签证变更需人工复核",
    threshold: "> 5% 合同价", enabled: true, severity: "critical", category: "audit",
    logic: 'IF (change_amount / contract_total > 0.05)\n  THEN require_review(\n    level: "SENIOR_AUDIT",\n    msg: "签证变更超合同价5%"\n  );',
    linkedStandards: ["审计条例第24条"], lastEdited: "2025-03-02",
  },
];

const TAB_CONFIG: { key: RuleTab; label: string }[] = [
  { key: "material", label: "材料价格库" },
  { key: "labor", label: "人工基准" },
  { key: "compliance", label: "合规标准" },
  { key: "custom", label: "自定义逻辑" },
  { key: "audit", label: "审计模板" },
];

const SEVERITY_CONFIG: Record<SeverityKey, { label: string; cls: string }> = {
  critical: { label: "严重", cls: "rc-sev-critical" },
  warning: { label: "警告", cls: "rc-sev-warning" },
  notice: { label: "提示", cls: "rc-sev-notice" },
};

const KNOWLEDGE_BASE = [
  {
    icon: "menu_book", title: "GB50500-2013",
    desc: "建设工程工程量清单计价规范，核心计价依据。",
    status: "integrated" as const,
  },
  {
    icon: "engineering", title: "劳动定额标准 v4.1",
    desc: "结构构件标准化工时计算依据。",
    status: "integrated" as const,
  },
  {
    icon: "gavel", title: "国际标准 (ISO)",
    desc: "国际造价管理框架与报告标准。",
    status: "disabled" as const,
  },
];

export default function RuleConfig() {
  const [rules, setRules] = useState<Rule[]>(INITIAL_RULES);
  const [activeTab, setActiveTab] = useState<RuleTab>("material");
  const [selectedId, setSelectedId] = useState<string>("MAT-001");

  const filtered = rules.filter((r) => r.category === activeTab);
  const selected = rules.find((r) => r.id === selectedId) ?? rules[0];

  const activeCount = rules.filter((r) => r.enabled).length;
  const convergence = 98.5;
  const auditRate = 84.2;

  const toggleRule = (id: string) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r)),
    );
    message.success("规则状态已更新");
  };

  return (
    <div className="rc-root">
      <div style={{ padding: "24px 32px 0" }}>
        <PageBreadcrumb items={[
          { label: "控制面板", path: "/dashboard" },
          { label: "规则配置" },
        ]} />
      </div>
      {/* Header */}
      <header className="rc-page-header">
        <div>
          <h2 className="rc-page-title">AI 规则配置</h2>
          <p className="rc-page-subtitle">管理自动化造价校验逻辑与国标知识库标准</p>
        </div>
        <div className="rc-page-actions">
          <button className="rc-btn-outline">
            <span className="material-symbols-outlined">upload_file</span>
            导出规则库
          </button>
          <button className="rc-btn-primary">
            <span className="material-symbols-outlined">add</span>
            新建自定义规则
          </button>
        </div>
      </header>

      {/* Status Cards */}
      <div className="rc-status-grid">
        <div className="rc-status-card">
          <p className="rc-status-label">活跃规则</p>
          <div className="rc-status-row">
            <span className="rc-status-value">{activeCount}</span>
            <span className="rc-status-trend up">
              <span className="material-symbols-outlined">arrow_upward</span>5%
            </span>
          </div>
        </div>
        <div className="rc-status-card">
          <p className="rc-status-label">国标版本</p>
          <div className="rc-status-row">
            <span className="rc-status-value">GB50500</span>
            <span className="rc-status-trend muted">v2013</span>
          </div>
        </div>
        <div className="rc-status-card">
          <p className="rc-status-label">价格收敛率</p>
          <div className="rc-status-row">
            <span className="rc-status-value">{convergence}%</span>
            <span className="rc-status-trend up">
              <span className="material-symbols-outlined">check</span>
            </span>
          </div>
        </div>
        <div className="rc-status-card">
          <p className="rc-status-label">审核通过率</p>
          <div className="rc-status-row">
            <span className="rc-status-value">{auditRate}%</span>
            <span className="rc-status-trend muted">AI-Auto</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="rc-tabs">
        {TAB_CONFIG.map((t) => (
          <button
            key={t.key}
            className={`rc-tab ${activeTab === t.key ? "active" : ""}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content: List + Detail */}
      <div className="rc-content">
        {/* Rule List */}
        <div className="rc-list-panel">
          <div className="rc-list-head">
            <h3>
              <span className="material-symbols-outlined">list_alt</span>
              规则清单
            </h3>
            <div className="rc-list-filter">
              <span>共 {filtered.length} 条</span>
            </div>
          </div>
          <div className="rc-table-wrap">
            <table className="rc-table">
              <thead>
                <tr>
                  <th>规则 ID</th>
                  <th>规则名称</th>
                  <th>阈值</th>
                  <th>状态</th>
                  <th>严重度</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="rc-empty-row">
                      <span className="material-symbols-outlined">inbox</span>
                      当前分类暂无规则
                    </td>
                  </tr>
                ) : (
                  filtered.map((r) => (
                    <tr
                      key={r.id}
                      className={`${selectedId === r.id ? "selected" : ""} ${!r.enabled ? "disabled" : ""}`}
                      onClick={() => setSelectedId(r.id)}
                    >
                      <td className="rc-rule-id">{r.id}</td>
                      <td>
                        <div className="rc-rule-name">{r.name}</div>
                        <div className="rc-rule-desc">{r.description}</div>
                      </td>
                      <td className="rc-rule-threshold">{r.threshold}</td>
                      <td>
                        <Switch
                          size="small"
                          checked={r.enabled}
                          onChange={(e) => { e; toggleRule(r.id); }}
                          onClick={(_, e) => e.stopPropagation()}
                        />
                      </td>
                      <td>
                        <span className={`rc-severity ${SEVERITY_CONFIG[r.severity].cls}`}>
                          {SEVERITY_CONFIG[r.severity].label}
                        </span>
                      </td>
                      <td className="rc-rule-actions">
                        <button onClick={(e) => e.stopPropagation()}>
                          <span className="material-symbols-outlined">more_horiz</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="rc-list-footer">
            <span>显示 {filtered.length} / {rules.filter((r) => r.category === activeTab || activeTab === "material").length} 条规则</span>
          </div>
        </div>

        {/* Detail Panel */}
        {selected && (
          <div className="rc-detail-panel">
            <div className="rc-detail-inner">
              <div className="rc-detail-head">
                <div className="rc-detail-head-top">
                  <span className="rc-detail-tag">规则配置</span>
                  <span className={`rc-detail-live ${selected.enabled ? "" : "off"}`}>
                    {selected.enabled ? "启用中" : "已禁用"}
                  </span>
                </div>
                <h3 className="rc-detail-title">{selected.id}: {selected.name}</h3>
                <p className="rc-detail-meta">上次编辑: {selected.lastEdited}</p>
              </div>

              <div className="rc-detail-body">
                {/* Logic */}
                <div className="rc-detail-section">
                  <h4>
                    <span className="material-symbols-outlined">settings_input_component</span>
                    校验逻辑
                  </h4>
                  <pre className="rc-logic-block">{selected.logic}</pre>
                </div>

                {/* Threshold slider */}
                <div className="rc-detail-section">
                  <label className="rc-field-label">偏差阈值</label>
                  <div className="rc-threshold-row">
                    <div className="rc-threshold-display">{selected.threshold}</div>
                  </div>
                </div>

                {/* Severity */}
                <div className="rc-detail-section">
                  <label className="rc-field-label">严重等级</label>
                  <div className="rc-severity-options">
                    {(["critical", "warning", "notice"] as SeverityKey[]).map((s) => (
                      <span
                        key={s}
                        className={`rc-severity ${SEVERITY_CONFIG[s].cls} ${selected.severity === s ? "active" : ""}`}
                      >
                        {SEVERITY_CONFIG[s].label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Linked standards */}
                <div className="rc-detail-section rc-detail-linked">
                  <h4>关联知识库</h4>
                  <div className="rc-linked-tags">
                    {selected.linkedStandards.length === 0 ? (
                      <span className="rc-no-linked">暂无关联</span>
                    ) : (
                      selected.linkedStandards.map((s) => (
                        <span key={s} className="rc-linked-tag">{s}</span>
                      ))
                    )}
                  </div>
                </div>
              </div>

              <div className="rc-detail-footer">
                <button className="rc-btn-primary rc-btn-flex" onClick={() => message.success("规则已保存")}>保存更改</button>
                <button className="rc-btn-outline" onClick={() => message.info("规则测试执行中...")}>测试规则</button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Knowledge Base Footer */}
      <section className="rc-kb-section">
        <div className="rc-kb-head">
          <div className="rc-kb-head-left">
            <div className="rc-kb-icon">
              <span className="material-symbols-outlined">auto_stories</span>
            </div>
            <div>
              <h4>国家建设标准库</h4>
              <p>法规合规参考数据</p>
            </div>
          </div>
          <button className="rc-kb-link">
            查看完整库
            <span className="material-symbols-outlined">open_in_new</span>
          </button>
        </div>
        <div className="rc-kb-grid">
          {KNOWLEDGE_BASE.map((kb) => (
            <div key={kb.title} className={`rc-kb-card ${kb.status === "disabled" ? "dimmed" : ""}`}>
              <span className={`material-symbols-outlined rc-kb-card-icon ${kb.status === "disabled" ? "muted" : ""}`}>
                {kb.icon}
              </span>
              <div>
                <h5>{kb.title}</h5>
                <p>{kb.desc}</p>
                {kb.status === "integrated" ? (
                  <span className="rc-kb-status integrated">
                    <span className="material-symbols-outlined">verified</span>
                    已集成
                  </span>
                ) : (
                  <span className="rc-kb-status disabled">未启用</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
