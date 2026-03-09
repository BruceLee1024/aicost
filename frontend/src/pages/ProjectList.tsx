import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Form, Input, Modal, Select, Spin, message } from "antd";
import type { Project } from "../api";
import { api } from "../api";

type ProjectStage = "all" | "ongoing" | "completed" | "auditing";

type StatusKey = "completed" | "processing" | "draft" | "action";
type AuditKey = "verified" | "in_review" | "pending";

interface ProjectRow {
  project: Project;
  type: string;
  budget: number;
  progress: number;
  accuracy: number;
  boqStatus: { key: StatusKey; label: string };
  auditStatus: { key: AuditKey; label: string };
  stage: Exclude<ProjectStage, "all">;
  needsAttention: boolean;
}

const TYPE_OPTIONS = ["住宅", "商业", "工业", "公共建筑", "市政"];
const currency = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 });

function deriveProjectRow(project: Project): ProjectRow {
  const type = TYPE_OPTIONS[project.id % TYPE_OPTIONS.length];
  const progress = project.id % 5 === 0 ? 100 : 38 + ((project.id * 17) % 58);
  const accuracy = 92 + (((project.id * 13) % 76) / 10);
  const budget = 2_500_000 + ((project.id * 7919) % 40) * 750_000 + ((project.id * 389) % 200) * 10_000;

  let boqStatus: ProjectRow["boqStatus"];
  if (progress >= 96) boqStatus = { key: "completed", label: "已完成" };
  else if (progress >= 75) boqStatus = { key: "processing", label: "处理中" };
  else if (progress >= 55) boqStatus = { key: "draft", label: "草稿中" };
  else boqStatus = { key: "action", label: "需处理" };

  let auditStatus: ProjectRow["auditStatus"];
  if (progress >= 96) auditStatus = { key: "verified", label: "已核验" };
  else if (progress >= 70) auditStatus = { key: "in_review", label: "审核中" };
  else auditStatus = { key: "pending", label: "待提交" };

  let stage: ProjectRow["stage"];
  if (progress >= 96 && boqStatus.key === "completed" && auditStatus.key === "verified") stage = "completed";
  else if (auditStatus.key === "in_review") stage = "auditing";
  else stage = "ongoing";

  return {
    project,
    type,
    budget,
    progress,
    accuracy,
    boqStatus,
    auditStatus,
    stage,
    needsAttention: boqStatus.key === "action" || (auditStatus.key === "pending" && progress < 60),
  };
}

export default function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [stageFilter, setStageFilter] = useState<ProjectStage>("all");
  const [page, setPage] = useState(1);
  const [searchText, setSearchText] = useState("");
  const [form] = Form.useForm();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (location.state?.openCreate) {
      setOpen(true);
      window.history.replaceState({}, "");
    }
  }, [location.state]);

  const load = async () => {
    setLoading(true);
    try {
      setProjects(await api.listProjects());
    } catch {
      message.error("加载项目失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const searchQuery = searchParams.get("q")?.toLowerCase() ?? "";
  const pageSize = 10;

  const rows = useMemo(() => projects.map((p) => deriveProjectRow(p)), [projects]);

  const filteredRows = useMemo(() => {
    const q = searchText.toLowerCase() || searchQuery;
    return rows.filter((row) => {
      if (stageFilter !== "all" && row.stage !== stageFilter) return false;
      if (!q) return true;
      const keywords = [row.project.name, row.project.region, row.project.id.toString(), row.type]
        .join(" ")
        .toLowerCase();
      return keywords.includes(q);
    }).sort((a, b) => a.project.id - b.project.id);
  }, [rows, searchQuery, searchText, stageFilter]);

  const stageCounts = useMemo(() => {
    const ongoing = rows.filter((r) => r.stage === "ongoing").length;
    const completed = rows.filter((r) => r.stage === "completed").length;
    const auditing = rows.filter((r) => r.stage === "auditing").length;
    return { all: rows.length, ongoing, completed, auditing };
  }, [rows]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * pageSize;
  const pageRows = filteredRows.slice(pageStart, pageStart + pageSize);

  useEffect(() => { setPage(1); }, [searchQuery, searchText, stageFilter]);
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const summary = useMemo(() => {
    const totalBudget = rows.reduce((sum, row) => sum + row.budget, 0);
    const avgAccuracy = rows.length ? rows.reduce((sum, row) => sum + row.accuracy, 0) / rows.length : 0;
    const attention = rows.filter((row) => row.needsAttention).length;
    return { totalBudget, avgAccuracy, attention };
  }, [rows]);

  const onCreate = async () => {
    try {
      const values = await form.validateFields();
      await api.createProject(values);
      message.success("项目已创建");
      setOpen(false);
      form.resetFields();
      load();
    } catch {
      message.error("创建失败");
    }
  };

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && searchText.trim()) {
      navigate(`/projects?q=${encodeURIComponent(searchText.trim())}`);
    }
  };

  return (
    <div className="pmc-root">
      {/* ── Page Header ── */}
      <header className="pmc-header">
        <div className="pmc-header-left">
          <h2 className="pmc-header-title">项目管理中心</h2>
          <span className="pmc-live">LIVE</span>
        </div>
        <div className="pmc-header-right">
          <div className="pmc-search">
            <span className="material-symbols-outlined">search</span>
            <input
              placeholder="搜索项目编号或名称..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={handleSearch}
            />
          </div>
          <button className="pmc-notify-btn">
            <span className="material-symbols-outlined">notifications</span>
            <span className="pmc-notify-dot" />
          </button>
          <button className="pmc-create-btn" onClick={() => setOpen(true)}>
            <span className="material-symbols-outlined">add</span>
            新建项目
          </button>
        </div>
      </header>

      {/* ── Summary Cards ── */}
      <div className="pmc-summary-grid">
        {[
          {
            icon: "assignment", iconClass: "blue",
            label: "项目总数", value: rows.length.toString(),
            trend: "+5%", trendUp: true,
          },
          {
            icon: "payments", iconClass: "emerald",
            label: "总预算规模", value: currency.format(summary.totalBudget),
            trend: `+${Math.max(1, stageCounts.completed)} 单`, trendUp: true,
          },
          {
            icon: "psychology", iconClass: "amber",
            label: "平均 AI 准确率", value: `${summary.avgAccuracy.toFixed(1)}%`,
            trend: `+0.2%`, trendUp: true,
          },
          {
            icon: "warning", iconClass: "rose",
            label: "需关注项目", value: summary.attention.toString(),
            trend: summary.attention > 0 ? `${summary.attention} 项` : "0 项",
            trendUp: summary.attention === 0,
          },
        ].map((card) => (
          <div key={card.label} className="pmc-summary-card">
            <div className="pmc-summary-head">
              <span className={`pmc-summary-icon ${card.iconClass}`}>
                <span className="material-symbols-outlined">{card.icon}</span>
              </span>
              <span className={`pmc-chip ${card.trendUp ? "pmc-chip-up" : "pmc-chip-down"}`}>
                {card.trend}
                <span className="material-symbols-outlined">{card.trendUp ? "trending_up" : "trending_down"}</span>
              </span>
            </div>
            <p className="pmc-summary-label">{card.label}</p>
            <h3 className="pmc-summary-value">{card.value}</h3>
          </div>
        ))}
      </div>

      {/* ── Projects Panel ── */}
      <section className="pmc-panel">
        <div className="pmc-panel-head">
          <div className="pmc-tabs">
            {[
              { key: "all" as ProjectStage, label: "全部项目" },
              { key: "ongoing" as ProjectStage, label: "进行中" },
              { key: "completed" as ProjectStage, label: "已完成" },
              { key: "auditing" as ProjectStage, label: "审核中" },
            ].map((tab) => (
              <button
                key={tab.key}
                className={`pmc-tab ${stageFilter === tab.key ? "active" : ""}`}
                onClick={() => setStageFilter(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="pmc-panel-actions">
            <button className="pmc-action-btn">
              <span className="material-symbols-outlined">filter_list</span>
              筛选
            </button>
            <button className="pmc-action-btn">
              <span className="material-symbols-outlined">download</span>
              导出
            </button>
          </div>
        </div>

        {/* ── Table ── */}
        <div className="pmc-table-wrap">
          {loading ? (
            <div className="pmc-loading">
              <Spin size="large" />
              <p>加载项目中...</p>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="pmc-empty">
              <span className="material-symbols-outlined">inventory_2</span>
              <p>当前筛选下暂无项目数据</p>
              <button className="pmc-create-btn" onClick={() => setOpen(true)}>
                <span className="material-symbols-outlined">add</span>
                新建项目
              </button>
            </div>
          ) : (
            <table className="pmc-table">
              <thead>
                <tr>
                  <th>项目名称</th>
                  <th>类型</th>
                  <th>预算</th>
                  <th>AI 进度</th>
                  <th>清单状态</th>
                  <th>审核状态</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row) => (
                  <tr key={row.project.id}>
                    <td>
                      <div className="pmc-project-name-cell">
                        <strong>{row.project.name}</strong>
                        <span>ID: PRJ-{row.project.id.toString().padStart(4, "0")} · {row.project.region}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`pmc-type-badge ${row.type}`}>{row.type}</span>
                    </td>
                    <td>
                      <span className="pmc-budget">{currency.format(row.budget)}</span>
                    </td>
                    <td>
                      <div className="pmc-progress">
                        <div className="pmc-progress-track">
                          <div
                            className={`pmc-progress-fill ${row.progress < 50 ? "low" : ""}`}
                            style={{ width: `${row.progress}%` }}
                          />
                        </div>
                        <span>{row.progress}%</span>
                      </div>
                    </td>
                    <td>
                      <span className={`pmc-status pmc-status-${row.boqStatus.key}`}>
                        <span className="material-symbols-outlined">
                          {row.boqStatus.key === "completed" ? "check_circle" :
                           row.boqStatus.key === "processing" ? "sync" :
                           row.boqStatus.key === "draft" ? "history" : "report"}
                        </span>
                        {row.boqStatus.label}
                      </span>
                    </td>
                    <td>
                      <span className={`pmc-audit pmc-audit-${row.auditStatus.key}`}>{row.auditStatus.label}</span>
                    </td>
                    <td>
                      <Link to={`/projects/${row.project.id}`} className="pmc-link-btn">
                        <span className="material-symbols-outlined">arrow_forward</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ── Pagination ── */}
        {!loading && filteredRows.length > 0 && (
          <div className="pmc-pagination">
            <span className="pmc-pagination-info">
              显示 {pageStart + 1}-{Math.min(pageStart + pageSize, filteredRows.length)} / {filteredRows.length} 个项目
            </span>
            <div className="pmc-pagination-actions">
              <button
                className="pmc-page-btn"
                disabled={currentPage <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <span className="material-symbols-outlined">chevron_left</span>
              </button>
              {Array.from({ length: Math.min(totalPages, 3) }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  className={`pmc-page-btn ${currentPage === n ? "active" : ""}`}
                  onClick={() => setPage(n)}
                >
                  {n}
                </button>
              ))}
              <button
                className="pmc-page-btn"
                disabled={currentPage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                <span className="material-symbols-outlined">chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ── Create Modal ── */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="pmc-modal-icon">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add_business</span>
            </div>
            <span>新建项目</span>
          </div>
        }
        open={open}
        onOk={onCreate}
        onCancel={() => { setOpen(false); form.resetFields(); }}
        okText="创建项目"
        width={440}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 20 }} initialValues={{ standard_type: "GB50500", language: "zh", currency: "CNY" }}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: "请输入项目名称" }]}>
            <Input
              placeholder="例如：某住宅小区地下室工程"
              prefix={<span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--text-muted)" }}>edit</span>}
            />
          </Form.Item>
          <Form.Item name="region" label="所在地区" rules={[{ required: true, message: "请输入地区" }]} extra="用于匹配地区定额及材料价格">
            <Input
              placeholder="如 西安 / 北京 / 上海 / Hong Kong"
              prefix={<span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--text-muted)" }}>location_on</span>}
            />
          </Form.Item>
          <Form.Item name="standard_type" label="计价标准">
            <Select>
              <Select.Option value="GB50500">GB50500 (中国大陆)</Select.Option>
              <Select.Option value="HKSMM4">HKSMM4 (香港)</Select.Option>
            </Select>
          </Form.Item>
          <div style={{ display: "flex", gap: 12 }}>
            <Form.Item name="language" label="语言" style={{ flex: 1 }}>
              <Select>
                <Select.Option value="zh">中文</Select.Option>
                <Select.Option value="en">English</Select.Option>
                <Select.Option value="bilingual">双语 Bilingual</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="currency" label="币种" style={{ flex: 1 }}>
              <Select>
                <Select.Option value="CNY">CNY ¥</Select.Option>
                <Select.Option value="HKD">HKD HK$</Select.Option>
              </Select>
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
