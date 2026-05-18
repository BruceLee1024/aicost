import { useEffect, useMemo, useState } from "react";
import {
  Button, Card, Col, Empty, Input, InputNumber, Modal, Progress, Row,
  Space, Spin, Table, Tabs, Tag, Tooltip, Upload, message,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type {
  AnalyzeResult,
  EnterpriseQuotaCandidate,
  EnterpriseQuotaCreate,
  EnterpriseQuotaItem,
  EnterpriseQuotaStats,
  EnterpriseQuotaStatus,
} from "../api";
import { api } from "../api";
import PageBreadcrumb from "../components/PageBreadcrumb";

const STATUS_META: Record<EnterpriseQuotaStatus, { label: string; color: string }> = {
  draft: { label: "草稿", color: "default" },
  in_review: { label: "待审批", color: "gold" },
  approved: { label: "已发布", color: "green" },
  rejected: { label: "已驳回", color: "red" },
  archived: { label: "已归档", color: "default" },
};

const SOURCE_META: Record<string, { label: string; color: string }> = {
  manual: { label: "手工", color: "blue" },
  precipitated: { label: "智能沉淀", color: "purple" },
  imported: { label: "导入", color: "cyan" },
};

const EMPTY_FORM: EnterpriseQuotaCreate = {
  quota_code: "",
  name: "",
  unit: "",
  labor_qty: 0,
  material_qty: 0,
  machine_qty: 0,
  labor_fee: 0,
  material_fee: 0,
  machine_fee: 0,
  base_price: 0,
  work_content: "",
  applicable_scope: "",
  chapter: "",
  profession: "房建",
  region: "",
  version: "v2026.1",
  coefficient_default: 1.0,
  tags: [],
};

function StatusTag({ status }: { status: EnterpriseQuotaStatus }) {
  const meta = STATUS_META[status] || { label: status, color: "default" };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function SourceTag({ source }: { source: string }) {
  const meta = SOURCE_META[source] || { label: source, color: "default" };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

// ── Confidence ring ───────────────────────────────────────────────
function ConfidenceRing({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 75 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#94a3b8";
  return (
    <Progress
      type="circle"
      size={56}
      percent={pct}
      strokeColor={color}
      format={(p) => <span style={{ fontSize: 13, fontWeight: 700, color }}>{p}%</span>}
    />
  );
}

// ── Edit modal ─────────────────────────────────────────────────────
function EditModal({
  open, initial, isCreate, onCancel, onSaved,
}: {
  open: boolean;
  initial: EnterpriseQuotaCreate & { id?: number };
  isCreate: boolean;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setForm(initial); }, [initial, open]);

  const update = <K extends keyof EnterpriseQuotaCreate>(k: K, v: EnterpriseQuotaCreate[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.quota_code?.trim() || !form.name?.trim() || !form.unit?.trim()) {
      message.warning("编码 / 名称 / 单位为必填项");
      return;
    }
    setSaving(true);
    try {
      if (isCreate) {
        await api.createEnterpriseQuota(form);
        message.success("已创建草稿");
      } else if (initial.id) {
        await api.updateEnterpriseQuota(initial.id, form);
        message.success("已保存");
      }
      onSaved();
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      onOk={handleSave}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      title={isCreate ? "新建企业定额" : "编辑企业定额"}
      width={780}
      destroyOnClose
    >
      <Row gutter={[12, 12]}>
        <Col span={8}>
          <label className="eq-form-label">编码 *</label>
          <Input
            value={form.quota_code}
            onChange={(e) => update("quota_code", e.target.value)}
            disabled={!isCreate}
            placeholder="ENT-A01001"
          />
        </Col>
        <Col span={10}>
          <label className="eq-form-label">名称 *</label>
          <Input
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
          />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">单位 *</label>
          <Input
            value={form.unit}
            onChange={(e) => update("unit", e.target.value)}
            placeholder="m³ / m² / 项"
          />
        </Col>

        <Col span={8}>
          <label className="eq-form-label">章节</label>
          <Input value={form.chapter ?? ""} onChange={(e) => update("chapter", e.target.value)} />
        </Col>
        <Col span={5}>
          <label className="eq-form-label">专业</label>
          <Input value={form.profession ?? ""} onChange={(e) => update("profession", e.target.value)} />
        </Col>
        <Col span={5}>
          <label className="eq-form-label">地区</label>
          <Input value={form.region ?? ""} onChange={(e) => update("region", e.target.value)} />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">版本</label>
          <Input value={form.version ?? ""} onChange={(e) => update("version", e.target.value)} />
        </Col>

        <Col span={24}>
          <div className="eq-form-section">含量（每单位消耗）</div>
        </Col>
        <Col span={8}>
          <label className="eq-form-label">人工含量</label>
          <InputNumber
            value={form.labor_qty}
            onChange={(v) => update("labor_qty", v ?? 0)}
            style={{ width: "100%" }}
            step={0.01}
          />
        </Col>
        <Col span={8}>
          <label className="eq-form-label">材料含量</label>
          <InputNumber
            value={form.material_qty}
            onChange={(v) => update("material_qty", v ?? 0)}
            style={{ width: "100%" }}
            step={0.01}
          />
        </Col>
        <Col span={8}>
          <label className="eq-form-label">机械含量</label>
          <InputNumber
            value={form.machine_qty}
            onChange={(v) => update("machine_qty", v ?? 0)}
            style={{ width: "100%" }}
            step={0.01}
          />
        </Col>

        <Col span={24}>
          <div className="eq-form-section">费用 / 基价（元）</div>
        </Col>
        <Col span={6}>
          <label className="eq-form-label">人工费</label>
          <InputNumber value={form.labor_fee} onChange={(v) => update("labor_fee", v ?? 0)} style={{ width: "100%" }} />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">材料费</label>
          <InputNumber value={form.material_fee} onChange={(v) => update("material_fee", v ?? 0)} style={{ width: "100%" }} />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">机械费</label>
          <InputNumber value={form.machine_fee} onChange={(v) => update("machine_fee", v ?? 0)} style={{ width: "100%" }} />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">基价</label>
          <InputNumber value={form.base_price} onChange={(v) => update("base_price", v ?? 0)} style={{ width: "100%" }} />
        </Col>
        <Col span={6}>
          <label className="eq-form-label">默认系数</label>
          <InputNumber
            value={form.coefficient_default}
            onChange={(v) => update("coefficient_default", v ?? 1)}
            step={0.05}
            min={0}
            style={{ width: "100%" }}
          />
        </Col>

        <Col span={24}>
          <label className="eq-form-label">工作内容</label>
          <Input.TextArea
            rows={2}
            value={form.work_content ?? ""}
            onChange={(e) => update("work_content", e.target.value)}
          />
        </Col>
        <Col span={24}>
          <label className="eq-form-label">适用范围</label>
          <Input.TextArea
            rows={2}
            value={form.applicable_scope ?? ""}
            onChange={(e) => update("applicable_scope", e.target.value)}
          />
        </Col>
      </Row>
    </Modal>
  );
}

// ── Review modal (for rejection comment) ───────────────────────────
function ReviewModal({
  open, title, onCancel, onConfirm,
}: {
  open: boolean;
  title: string;
  onCancel: () => void;
  onConfirm: (comment: string) => void;
}) {
  const [comment, setComment] = useState("");
  useEffect(() => { if (open) setComment(""); }, [open]);
  return (
    <Modal
      open={open}
      title={title}
      onCancel={onCancel}
      onOk={() => onConfirm(comment)}
      okText="确认"
      cancelText="取消"
    >
      <Input.TextArea
        rows={4}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="请输入审批意见…"
      />
    </Modal>
  );
}

// ── Main page ──────────────────────────────────────────────────────
export default function EnterpriseQuotaLibrary() {
  const [stats, setStats] = useState<EnterpriseQuotaStats | null>(null);
  const [activeTab, setActiveTab] = useState<string>("approved");
  const [items, setItems] = useState<EnterpriseQuotaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [editInitial, setEditInitial] = useState<EnterpriseQuotaCreate & { id?: number }>(EMPTY_FORM);
  const [editIsCreate, setEditIsCreate] = useState(true);

  const [reviewState, setReviewState] = useState<{ open: boolean; itemId: number | null; mode: "reject" | "approve" }>({
    open: false, itemId: null, mode: "reject",
  });

  // Candidates state
  const [candidates, setCandidates] = useState<EnterpriseQuotaCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const tabStatus: EnterpriseQuotaStatus | null = useMemo(() => {
    switch (activeTab) {
      case "approved": return "approved";
      case "in_review": return "in_review";
      case "draft": return "draft";
      case "rejected": return "rejected";
      default: return null;
    }
  }, [activeTab]);

  const refreshStats = async () => {
    try { setStats(await api.getEnterpriseQuotaStats()); }
    catch (e) { console.error(e); }
  };

  const refreshItems = async () => {
    if (!tabStatus) return;
    setLoading(true);
    try {
      const res = await api.listEnterpriseQuotas({
        status: tabStatus,
        keyword: keyword || undefined,
        limit: 200,
      });
      setItems(res.items);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const refreshCandidates = async () => {
    setCandidatesLoading(true);
    try {
      const res = await api.listEnterpriseQuotaCandidates({ status: "pending", limit: 200 });
      setCandidates(res.items);
    } catch (e) {
      message.error(`加载候选失败: ${(e as Error).message}`);
    } finally {
      setCandidatesLoading(false);
    }
  };

  useEffect(() => { refreshStats(); }, []);
  useEffect(() => {
    if (activeTab === "candidates") refreshCandidates();
    else refreshItems();
  }, [activeTab, keyword]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Actions ──
  const handleCreate = () => {
    setEditInitial(EMPTY_FORM);
    setEditIsCreate(true);
    setEditOpen(true);
  };

  const handleEdit = (it: EnterpriseQuotaItem) => {
    setEditInitial({
      id: it.id,
      quota_code: it.quota_code,
      name: it.name,
      unit: it.unit,
      labor_qty: it.labor_qty,
      material_qty: it.material_qty,
      machine_qty: it.machine_qty,
      labor_fee: it.labor_fee,
      material_fee: it.material_fee,
      machine_fee: it.machine_fee,
      base_price: it.base_price,
      work_content: it.work_content,
      applicable_scope: it.applicable_scope,
      chapter: it.chapter,
      profession: it.profession,
      region: it.region,
      version: it.version,
      coefficient_default: it.coefficient_default,
      tags: it.tags,
    });
    setEditIsCreate(false);
    setEditOpen(true);
  };

  const handleSubmit = async (id: number) => {
    try {
      await api.submitEnterpriseQuota(id);
      message.success("已提交审批");
      refreshItems(); refreshStats();
    } catch (e) { message.error((e as Error).message); }
  };

  const handleApprove = (id: number) => {
    setReviewState({ open: true, itemId: id, mode: "approve" });
  };
  const handleReject = (id: number) => {
    setReviewState({ open: true, itemId: id, mode: "reject" });
  };

  const handleReviewConfirm = async (comment: string) => {
    if (!reviewState.itemId) return;
    try {
      if (reviewState.mode === "approve") {
        await api.approveEnterpriseQuota(reviewState.itemId, "", comment);
        message.success("已发布");
      } else {
        await api.rejectEnterpriseQuota(reviewState.itemId, "", comment);
        message.info("已驳回");
      }
      setReviewState({ open: false, itemId: null, mode: "reject" });
      refreshItems(); refreshStats();
    } catch (e) { message.error((e as Error).message); }
  };

  const handleArchive = async (id: number) => {
    try {
      await api.archiveEnterpriseQuota(id);
      message.success("已归档");
      refreshItems(); refreshStats();
    } catch (e) { message.error((e as Error).message); }
  };

  const handleRestore = async (id: number) => {
    try {
      await api.restoreEnterpriseQuota(id);
      message.success("已恢复到草稿");
      refreshItems(); refreshStats();
    } catch (e) { message.error((e as Error).message); }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: "确认删除？",
      content: "仅草稿状态条目可删除，删除后无法恢复。",
      okType: "danger",
      okText: "删除",
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.deleteEnterpriseQuota(id);
          message.success("已删除");
          refreshItems(); refreshStats();
        } catch (e) { message.error((e as Error).message); }
      },
    });
  };

  const handleImport = async (file: File) => {
    try {
      const res = await api.importEnterpriseQuotaExcel(file);
      message.success(`已导入 ${res.imported} 条（跳过 ${res.skipped}）`);
      if (res.errors?.length) {
        Modal.warning({
          title: "部分行未导入",
          content: <pre style={{ maxHeight: 240, overflow: "auto" }}>{res.errors.join("\n")}</pre>,
          width: 600,
        });
      }
      setActiveTab("draft");
      refreshStats();
    } catch (e) { message.error((e as Error).message); }
    return false; // prevent antd default upload
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res: AnalyzeResult = await api.analyzeEnterpriseQuotaCandidates();
      message.success(
        `分析完成：扫描 ${res.snapshots_scanned} 个快照 / ${res.bindings_scanned} 条绑定，新增 ${res.candidates_created}，更新 ${res.candidates_updated}`,
      );
      refreshCandidates();
      refreshStats();
    } catch (e) { message.error((e as Error).message); }
    finally { setAnalyzing(false); }
  };

  const handlePromote = async (c: EnterpriseQuotaCandidate) => {
    try {
      await api.promoteEnterpriseQuotaCandidate(c.id);
      message.success("已沉淀为企业定额草稿，请到 [草稿] 标签提交审批");
      refreshCandidates();
      refreshStats();
    } catch (e) { message.error((e as Error).message); }
  };

  const handleDismiss = (c: EnterpriseQuotaCandidate) => {
    let reason = "";
    Modal.confirm({
      title: "忽略该候选？",
      content: (
        <Input.TextArea
          placeholder="忽略原因（可选）"
          rows={3}
          onChange={(e) => { reason = e.target.value; }}
        />
      ),
      okText: "忽略",
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.dismissEnterpriseQuotaCandidate(c.id, reason);
          refreshCandidates();
        } catch (e) { message.error((e as Error).message); }
      },
    });
  };

  // ── Table columns ──
  const columns: ColumnsType<EnterpriseQuotaItem> = [
    {
      title: "编码", dataIndex: "quota_code", width: 150,
      render: (v) => <code style={{ color: "#60a5fa" }}>{v}</code>,
    },
    { title: "名称", dataIndex: "name", ellipsis: true },
    { title: "单位", dataIndex: "unit", width: 70 },
    {
      title: "含量(人/材/机)", width: 160,
      render: (_, r) => (
        <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>
          {r.labor_qty.toFixed(2)} / {r.material_qty.toFixed(2)} / {r.machine_qty.toFixed(2)}
        </span>
      ),
    },
    {
      title: "基价", dataIndex: "base_price", width: 100, align: "right",
      render: (v: number) => <strong>{v ? v.toFixed(2) : "—"}</strong>,
    },
    {
      title: "默认系数", dataIndex: "coefficient_default", width: 90, align: "center",
      render: (v: number) => v.toFixed(2),
    },
    { title: "来源", dataIndex: "source_type", width: 100, render: (s) => <SourceTag source={s} /> },
    { title: "版本", dataIndex: "version", width: 90 },
    { title: "引用", dataIndex: "usage_count", width: 60, align: "center" },
    {
      title: "操作", key: "actions", width: 220, fixed: "right",
      render: (_, r) => (
        <Space size={4}>
          {r.status === "draft" && (
            <>
              <Button size="small" type="link" onClick={() => handleEdit(r)}>编辑</Button>
              <Button size="small" type="link" onClick={() => handleSubmit(r.id)}>提交审批</Button>
              <Button size="small" type="link" danger onClick={() => handleDelete(r.id)}>删除</Button>
            </>
          )}
          {r.status === "in_review" && (
            <>
              <Button size="small" type="primary" onClick={() => handleApprove(r.id)}>批准</Button>
              <Button size="small" danger onClick={() => handleReject(r.id)}>驳回</Button>
            </>
          )}
          {r.status === "approved" && (
            <>
              <Tooltip title={r.review_comment || "无意见"}>
                <Tag color="green">已发布</Tag>
              </Tooltip>
              <Button size="small" type="link" onClick={() => handleArchive(r.id)}>归档</Button>
            </>
          )}
          {r.status === "rejected" && (
            <>
              <Tooltip title={r.review_comment || "无意见"}>
                <Tag color="red">已驳回</Tag>
              </Tooltip>
              <Button size="small" type="link" onClick={() => handleRestore(r.id)}>回退草稿</Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  const pendingCount = stats?.by_status?.in_review ?? 0;
  const candidateCount = stats?.pending_candidates ?? 0;

  return (
    <div className="page-container" style={{ padding: 24, maxWidth: 1500 }}>
      <PageBreadcrumb items={[{ label: "企业定额库" }]} />

      {/* Stats cards */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>已发布</span>
              <div className="mini-stat-card-icon emerald">
                <span className="material-symbols-outlined">verified</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26 }}>
              {stats?.by_status?.approved ?? 0}
            </div>
            <div className="mini-stat-card-label">条企业定额</div>
          </div>
        </Col>
        <Col xs={12} md={6}>
          <div className="mini-stat-card" style={pendingCount > 0 ? { borderColor: "rgba(218,165,32,0.4)" } : undefined}>
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>待审批</span>
              <div className="mini-stat-card-icon gold">
                <span className="material-symbols-outlined">hourglass_top</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26, color: pendingCount > 0 ? "#fbbf24" : undefined }}>
              {pendingCount}
            </div>
            <div className="mini-stat-card-label">条等待审核</div>
          </div>
        </Col>
        <Col xs={12} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>智能推荐</span>
              <div className="mini-stat-card-icon purple">
                <span className="material-symbols-outlined">insights</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26 }}>{candidateCount}</div>
            <div className="mini-stat-card-label">个沉淀候选</div>
          </div>
        </Col>
        <Col xs={12} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>近 30 天新增</span>
              <div className="mini-stat-card-icon blue">
                <span className="material-symbols-outlined">trending_up</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26 }}>{stats?.recent_created ?? 0}</div>
            <div className="mini-stat-card-label">条</div>
          </div>
        </Col>
      </Row>

      {/* Toolbar */}
      <Card size="small" className="ql-filter-card" style={{ marginBottom: 12 }}
            bodyStyle={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Input.Search
          placeholder="搜索编码 / 名称…"
          allowClear
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 280 }}
        />
        <div style={{ flex: 1 }} />
        <Button type="primary" icon={<span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: "middle" }}>add</span>} onClick={handleCreate}>
          新建定额
        </Button>
        <Upload accept=".xlsx,.xls" beforeUpload={handleImport} showUploadList={false}>
          <Button icon={<UploadOutlined />}>Excel 导入</Button>
        </Upload>
        <Button onClick={() => window.open(api.downloadEnterpriseQuotaTemplateUrl(), "_blank")}>
          下载模板
        </Button>
      </Card>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: "approved", label: <><StatusTag status="approved" /> ({stats?.by_status?.approved ?? 0})</> },
          {
            key: "in_review",
            label: <><StatusTag status="in_review" /> ({pendingCount})</>,
          },
          { key: "draft", label: <><StatusTag status="draft" /> ({stats?.by_status?.draft ?? 0})</> },
          {
            key: "candidates",
            label: <><Tag color="purple">智能推荐</Tag> ({candidateCount})</>,
          },
          { key: "rejected", label: <><StatusTag status="rejected" /> ({stats?.by_status?.rejected ?? 0})</> },
        ]}
      />

      {activeTab === "candidates" ? (
        <Card bodyStyle={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <Button
              type="primary"
              loading={analyzing}
              onClick={handleAnalyze}
              icon={<span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: "middle" }}>auto_awesome</span>}
            >
              扫描历史项目，生成沉淀候选
            </Button>
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
              扫描所有快照 + BOQ-定额绑定，聚合相似条目生成可发布的企业定额建议
            </span>
          </div>

          {candidatesLoading ? (
            <div style={{ padding: 60, textAlign: "center" }}><Spin /></div>
          ) : candidates.length === 0 ? (
            <Empty description="暂无候选。点击上方按钮触发分析。" />
          ) : (
            <Row gutter={[12, 12]}>
              {candidates.map((c) => (
                <Col key={c.id} xs={24} md={12} xl={8}>
                  <Card
                    size="small"
                    className="eq-candidate-card"
                    title={
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <code style={{ color: "#a78bfa" }}>{c.boq_code_pattern}</code>
                        <Tag color="purple">沉淀候选</Tag>
                      </div>
                    }
                  >
                    <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12 }}>
                      <ConfidenceRing value={c.confidence} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                          {c.name_canonical || "(未命名)"}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          单位: {c.unit || "—"} · 样本 {c.sample_count} · 项目 {c.source_project_ids.length}
                        </div>
                      </div>
                    </div>

                    <div className="eq-candidate-grid">
                      <div><span>人工</span><strong>{c.suggested_labor_qty.toFixed(3)}</strong></div>
                      <div><span>材料</span><strong>{c.suggested_material_qty.toFixed(3)}</strong></div>
                      <div><span>机械</span><strong>{c.suggested_machine_qty.toFixed(3)}</strong></div>
                      <div><span>建议单价</span><strong style={{ color: "#10b981" }}>¥{c.suggested_unit_price.toFixed(2)}</strong></div>
                      <div><span>建议系数</span><strong>{c.suggested_coefficient.toFixed(2)}</strong></div>
                      <div><span>波动</span><strong>{((c.evidence?.dispersion ?? 0) * 100).toFixed(0)}%</strong></div>
                    </div>

                    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                      <Button size="small" type="primary" block onClick={() => handlePromote(c)}>
                        一键沉淀
                      </Button>
                      <Button size="small" block onClick={() => handleDismiss(c)}>
                        忽略
                      </Button>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Card>
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          columns={columns}
          pagination={{ pageSize: 50, showSizeChanger: false }}
          scroll={{ x: 1200 }}
          size="middle"
        />
      )}

      <EditModal
        open={editOpen}
        initial={editInitial}
        isCreate={editIsCreate}
        onCancel={() => setEditOpen(false)}
        onSaved={() => {
          setEditOpen(false);
          refreshItems();
          refreshStats();
        }}
      />

      <ReviewModal
        open={reviewState.open}
        title={reviewState.mode === "approve" ? "批准并发布" : "驳回该条目"}
        onCancel={() => setReviewState({ open: false, itemId: null, mode: "reject" })}
        onConfirm={handleReviewConfirm}
      />
    </div>
  );
}
