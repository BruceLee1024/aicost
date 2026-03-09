import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button, Descriptions, Form, Input, InputNumber, Modal, Popconfirm, Progress,
  Select, Spin, Table, Tag, Upload, message,
} from "antd";
import {
  BarChartOutlined, DeleteOutlined, EditOutlined, RobotOutlined, ThunderboltOutlined,
  UploadOutlined, CheckCircleOutlined, SyncOutlined,
} from "@ant-design/icons";
import AgentPanel from "./AgentPanel";
import type {
  AutoValuateResponse,
  BindingWithQuota,
  BoqItem,
  BoqSuggestion,
  CalcProvenance,
  CalcSummary,
  LineCalcResult,
  MatchCandidate,
  Project,
} from "../api";
import { api } from "../api";

interface Props {
  projectId: number;
  project?: Project | null;
  calcResult?: CalcSummary | null;
  onDataChanged?: () => void;
  activeDivision?: string;
  onActiveDivisionChange?: (division?: string) => void;
}

export default function BoqTab({
  projectId,
  project,
  calcResult,
  onDataChanged,
  activeDivision,
  onActiveDivisionChange,
}: Props) {
  const isHK = project?.standard_type === "HKSMM4";
  const currencySymbol = project?.currency === "HKD" ? "HK$" : "¥";
  const navigate = useNavigate();
  const [items, setItems] = useState<BoqItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [editItem, setEditItem] = useState<BoqItem | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [divisionFilter, setDivisionFilter] = useState<string | undefined>();
  useEffect(() => {
    setDivisionFilter(activeDivision);
  }, [activeDivision, projectId]);

  // AI match state
  const [matchOpen, setMatchOpen] = useState(false);
  const [matchBoqId, setMatchBoqId] = useState(0);
  const [matchBoqName, setMatchBoqName] = useState("");
  const [candidates, setCandidates] = useState<MatchCandidate[]>([]);
  const [matchLoading, setMatchLoading] = useState(false);

  // AI generate state
  const [genOpen, setGenOpen] = useState(false);
  const [genDesc, setGenDesc] = useState("");
  const [genLoading, setGenLoading] = useState(false);
  const [genItems, setGenItems] = useState<BoqSuggestion[]>([]);
  const [genSelected, setGenSelected] = useState<string[]>([]);
  const [genFloors, setGenFloors] = useState(0);

  // AI auto-valuate state
  const [avOpen, setAvOpen] = useState(false);
  const [avLoading, setAvLoading] = useState(false);
  const [avResult, setAvResult] = useState<AutoValuateResponse | null>(null);
  const [batchConfirmLoading, setBatchConfirmLoading] = useState(false);
  const [batchReplaceLoading, setBatchReplaceLoading] = useState(false);
  const [selectedBoqIds, setSelectedBoqIds] = useState<number[]>([]);

  // Agent panel state
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentBoqItem, setAgentBoqItem] = useState<BoqItem | null>(null);

  // Unit price provenance
  const [priceTraceOpen, setPriceTraceOpen] = useState(false);
  const [priceTraceLoading, setPriceTraceLoading] = useState(false);
  const [priceTrace, setPriceTrace] = useState<CalcProvenance | null>(null);

  // Inline editing state
  const [editingCell, setEditingCell] = useState<{ id: number; field: string } | null>(null);
  const [editingValue, setEditingValue] = useState<string | number>("");

  // Batch division change
  const [batchDivOpen, setBatchDivOpen] = useState(false);
  const [batchDivTarget, setBatchDivTarget] = useState("");

  // Inline quota search in expand row
  const [expandSearchId, setExpandSearchId] = useState<number | null>(null);
  const [expandSearchKw, setExpandSearchKw] = useState("");
  const [expandSearchResults, setExpandSearchResults] = useState<MatchCandidate[]>([]);
  const [expandSearchLoading, setExpandSearchLoading] = useState(false);

  // Coefficient editing
  const [editingCoeff, setEditingCoeff] = useState<{ bindingId: number; boqItemId: number } | null>(null);
  const [editingCoeffValue, setEditingCoeffValue] = useState(1);

  // Validation status cache per binding
  const [validationMap, _setValidationMap] = useState<Map<number, string>>(new Map());

  // Bindings with quota details
  const [bindingsMap, setBindingsMap] = useState<Map<number, BindingWithQuota[]>>(new Map());

  const loadBindings = async () => {
    try {
      const all = await api.listProjectBindings(projectId);
      const map = new Map<number, BindingWithQuota[]>();
      for (const b of all) {
        const arr = map.get(b.boq_item_id) ?? [];
        arr.push(b);
        map.set(b.boq_item_id, arr);
      }
      setBindingsMap(map);
    } catch { /**/ }
  };

  const load = async () => {
    setLoading(true);
    try { setItems(await api.listBoqItems(projectId)); } catch { /**/ }
    setLoading(false);
    loadBindings();
    setSelectedBoqIds([]);
  };
  useEffect(() => { load(); }, [projectId]);

  const divisions = [...new Set(items.map((i) => i.division).filter(Boolean))];
  const filtered = divisionFilter ? items.filter((i) => i.division === divisionFilter) : items;
  const handleDivisionFilterChange = (value: string | undefined) => {
    setDivisionFilter(value);
    onActiveDivisionChange?.(value);
  };

  // Build lookup: boq_item_id → LineCalcResult
  const calcMap = new Map<number, LineCalcResult>();
  if (calcResult) {
    for (const lr of calcResult.line_results) calcMap.set(lr.boq_item_id, lr);
  }

  // Section subtotal
  const sectionTotal = filtered.reduce((sum, item) => {
    if (isHK) return sum + (item.amount || 0);
    const lr = calcMap.get(item.id);
    return sum + (lr ? lr.total : 0);
  }, 0);

  // ── Inline editing ────────────────────────────────────────
  const startInlineEdit = (record: BoqItem, field: string) => {
    setEditingCell({ id: record.id, field });
    setEditingValue((record as unknown as Record<string, unknown>)[field] as string | number);
  };
  const saveInlineEdit = async () => {
    if (!editingCell) return;
    try {
      await api.updateBoqItem(projectId, editingCell.id, { [editingCell.field]: editingValue });
      setEditingCell(null);
      load();
      onDataChanged?.();
    } catch { message.error("保存失败"); }
  };

  // ── Batch operations ──────────────────────────────────────
  const handleBatchDelete = async () => {
    if (selectedBoqIds.length === 0) return;
    try {
      const res = await api.batchDeleteBoqItems(projectId, selectedBoqIds);
      message.success(`已删除 ${res.deleted} 项`);
      load();
      onDataChanged?.();
    } catch { message.error("批量删除失败"); }
  };
  const handleBatchDivision = async () => {
    if (!batchDivTarget || selectedBoqIds.length === 0) return;
    try {
      await api.batchUpdateBoqItems(projectId, selectedBoqIds, { division: batchDivTarget });
      message.success(`已更新 ${selectedBoqIds.length} 项分部`);
      setBatchDivOpen(false);
      setBatchDivTarget("");
      load();
      onDataChanged?.();
    } catch { message.error("批量更新失败"); }
  };

  // ── Move up/down (reorder) ────────────────────────────────
  const handleMove = async (itemId: number, direction: "up" | "down") => {
    const idx = filtered.findIndex((i) => i.id === itemId);
    if (idx < 0) return;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= filtered.length) return;
    const updates = [
      { id: filtered[idx].id, sort_order: filtered[swapIdx].sort_order },
      { id: filtered[swapIdx].id, sort_order: filtered[idx].sort_order },
    ];
    try {
      await api.reorderBoqItems(projectId, updates);
      load();
    } catch { /**/ }
  };

  // ── Expand row: inline quota search ───────────────────────
  const handleExpandSearch = async (boqItemId: number) => {
    if (!expandSearchKw.trim()) return;
    setExpandSearchLoading(true);
    try {
      setExpandSearchResults(await api.getQuotaCandidates(boqItemId, 5));
    } catch { /**/ }
    setExpandSearchLoading(false);
  };
  const handleExpandBind = async (boqItemId: number, quotaItemId: number) => {
    try {
      await api.confirmBinding(boqItemId, quotaItemId);
      message.success("绑定成功");
      setExpandSearchId(null);
      setExpandSearchKw("");
      setExpandSearchResults([]);
      load();
      onDataChanged?.();
    } catch { message.error("绑定失败"); }
  };
  const handleExpandUnbind = async (boqItemId: number, bindingId: number) => {
    try {
      await api.deleteBinding(boqItemId, bindingId);
      message.success("已解绑");
      load();
      onDataChanged?.();
    } catch { message.error("解绑失败"); }
  };
  const handleCoeffSave = async () => {
    if (!editingCoeff) return;
    try {
      await api.confirmBindingWithCoefficient(
        editingCoeff.boqItemId,
        bindingsMap.get(editingCoeff.boqItemId)?.find(b => b.binding_id === editingCoeff.bindingId)?.quota_item_id ?? 0,
        editingCoeffValue,
      );
      message.success("系数已更新");
      setEditingCoeff(null);
      load();
      onDataChanged?.();
    } catch { message.error("更新失败"); }
  };

  // CRUD
  const handleAdd = async () => {
    try {
      const v = await form.validateFields();
      await api.createBoqItem(projectId, v);
      message.success("清单项已创建");
      form.resetFields();
      setAddOpen(false);
      load();
      onDataChanged?.();
    } catch { message.error("创建失败"); }
  };

  const handleEdit = async () => {
    if (!editItem) return;
    try {
      const v = await editForm.validateFields();
      await api.updateBoqItem(projectId, editItem.id, v);
      message.success("已更新");
      setEditItem(null);
      load();
      onDataChanged?.();
    } catch { message.error("更新失败"); }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteBoqItem(projectId, id);
      message.success("已删除");
      load();
      onDataChanged?.();
    } catch { message.error("删除失败"); }
  };

  // Excel import
  const handleImport = async (file: File) => {
    try {
      const res = await api.importBoq(projectId, file);
      message.success(`导入成功：${res.imported} 条，跳过 ${res.skipped} 条`);
      load();
      onDataChanged?.();
    } catch { message.error("导入失败"); }
    return false;
  };

  // AI match
  const openMatch = async (item: BoqItem) => {
    setMatchBoqId(item.id);
    setMatchBoqName(`[${item.code}] ${item.name}`);
    setMatchOpen(true);
    setMatchLoading(true);
    setCandidates([]);
    try {
      setCandidates(await api.getQuotaCandidates(item.id));
    } catch { message.error("AI 匹配失败"); }
    setMatchLoading(false);
  };

  const confirmCandidate = async (quotaItemId: number) => {
    try {
      await api.confirmBinding(matchBoqId, quotaItemId);
      message.success("绑定成功");
      setMatchOpen(false);
      load();
    } catch { message.error("绑定失败"); }
  };

  // AI generate
  const handleGenerate = async () => {
    if (!genDesc.trim()) return;
    setGenLoading(true);
    setGenItems([]);
    setGenSelected([]);
    try {
      const res = await api.generateBoq(projectId, genDesc.trim());
      setGenItems(res.suggestions);
      setGenSelected(res.suggestions.map((s) => s.code));
      setGenFloors(res.floors_detected);
    } catch { message.error("AI 生成失败"); }
    setGenLoading(false);
  };

  const handleConfirmGen = async () => {
    const selected = genItems.filter((s) => genSelected.includes(s.code));
    if (selected.length === 0) { message.warning("请至少选择一项"); return; }
    let ok = 0;
    for (const s of selected) {
      try {
        await api.createBoqItem(projectId, {
          code: s.code, name: s.name, characteristics: s.characteristics,
          unit: s.unit, quantity: s.quantity, division: s.division,
        });
        ok++;
      } catch { /**/ }
    }
    message.success(`已创建 ${ok} 个清单项`);
    setGenOpen(false);
    setGenDesc("");
    setGenItems([]);
    load();
    onDataChanged?.();
  };

  // AI auto-valuate
  const handleAutoValuate = async () => {
    setAvOpen(true);
    setAvLoading(true);
    setAvResult(null);
    try {
      const res = await api.autoValuate(projectId);
      setAvResult(res);
      message.success(`自动套定额完成：匹配 ${res.newly_matched} 项，计算完成`);
      load();
      onDataChanged?.();
    } catch {
      message.error("自动套定额套价失败");
    }
    setAvLoading(false);
  };

  const openPriceTrace = async (item: BoqItem) => {
    setPriceTraceOpen(true);
    setPriceTraceLoading(true);
    setPriceTrace(null);
    try {
      const data = await api.getProvenance(item.id);
      setPriceTrace(data);
    } catch {
      message.error("加载综合单价溯源失败");
    }
    setPriceTraceLoading(false);
  };

  const runBatchAction = async (mode: "confirm" | "replace") => {
    const selected = items.filter((i) => selectedBoqIds.includes(i.id));
    if (selected.length === 0) {
      message.warning("请先勾选要批量处理的清单项");
      return;
    }

    const targets = mode === "confirm"
      ? selected.filter((i) => (bindingsMap.get(i.id)?.length ?? 0) === 0)
      : selected;
    if (targets.length === 0) {
      message.info(mode === "confirm" ? "所选项都已绑定，确认模式只处理未绑定项" : "没有可处理的清单项");
      return;
    }

    mode === "confirm" ? setBatchConfirmLoading(true) : setBatchReplaceLoading(true);
    try {
      const picks = await Promise.all(
        targets.map(async (row) => {
          try {
            const candidates = await api.getQuotaCandidates(row.id, 1);
            const best = candidates[0];
            if (!best) return null;
            return { boq_item_id: row.id, quota_item_id: best.quota_item_id, coefficient: 1 };
          } catch {
            return null;
          }
        }),
      );
      const bindings = picks.filter((p): p is { boq_item_id: number; quota_item_id: number; coefficient: number } => !!p);
      if (bindings.length === 0) {
        message.warning("未找到可用候选定额");
        return;
      }

      if (mode === "confirm") {
        await api.batchConfirmBindings(bindings);
        message.success(`批量确认完成：${bindings.length} 项`);
      } else {
        await api.batchReplaceBindings(bindings);
        message.success(`批量替换完成：${bindings.length} 项`);
      }
      await load();
      onDataChanged?.();
    } catch {
      message.error(mode === "confirm" ? "批量确认失败" : "批量替换失败");
    } finally {
      mode === "confirm" ? setBatchConfirmLoading(false) : setBatchReplaceLoading(false);
    }
  };

  // ── Inline editable cell renderer ──
  const renderEditable = (field: string, value: unknown, record: BoqItem, isNumber = false) => {
    const isEditing = editingCell?.id === record.id && editingCell?.field === field;
    if (isEditing) {
      return isNumber ? (
        <InputNumber
          size="small" autoFocus value={editingValue as number}
          onChange={(v) => setEditingValue(v ?? 0)}
          onPressEnter={saveInlineEdit} onBlur={saveInlineEdit}
          style={{ width: "100%" }}
        />
      ) : (
        <Input
          size="small" autoFocus value={editingValue as string}
          onChange={(e) => setEditingValue(e.target.value)}
          onPressEnter={saveInlineEdit} onBlur={saveInlineEdit}
          style={{ width: "100%" }}
        />
      );
    }
    return (
      <div
        className="boq-cell-editable"
        onDoubleClick={() => startInlineEdit(record, field)}
        title="双击编辑"
      >
        {value != null && value !== "" ? String(value) : <span className="boq-cell-editable-empty">—</span>}
      </div>
    );
  };

  // ── Build columns based on standard type ──
  const buildColumns = () => {
    if (isHK) {
      return [
        { title: "Ref", dataIndex: "item_ref", width: 60, render: (v: string, r: BoqItem) => renderEditable("item_ref", v, r) },
        { title: "Trade", dataIndex: "trade_section", width: 110, render: (v: string, r: BoqItem) => renderEditable("trade_section", v, r) },
        { title: "Description (EN)", dataIndex: "description_en", ellipsis: true, render: (v: string, r: BoqItem) => renderEditable("description_en", v, r) },
        { title: "名称", dataIndex: "name", width: 140, render: (v: string, r: BoqItem) => renderEditable("name", v, r) },
        { title: "Unit", dataIndex: "unit", width: 60, render: (v: string, r: BoqItem) => renderEditable("unit", v, r) },
        {
          title: "Qty", dataIndex: "quantity", width: 90,
          render: (v: number, r: BoqItem) => renderEditable("quantity", v, r, true),
        },
        {
          title: "Rate", dataIndex: "rate", width: 100,
          render: (v: number, r: BoqItem) => renderEditable("rate", v, r, true),
        },
        {
          title: "Amount", key: "amount", width: 120,
          render: (_: unknown, r: BoqItem) => (
            <strong style={{ display: "block", textAlign: "right" }}>
              {currencySymbol}{(r.amount || r.rate * r.quantity).toLocaleString("en", { minimumFractionDigits: 2 })}
            </strong>
          ),
        },
        {
          title: "↕", width: 50,
          render: (_: unknown, r: BoqItem) => (
            <div className="boq-reorder-wrap">
              <button className="boq-reorder-btn" onClick={() => handleMove(r.id, "up")}>▲</button>
              <button className="boq-reorder-btn" onClick={() => handleMove(r.id, "down")}>▼</button>
            </div>
          ),
        },
        {
          title: "", width: 80,
          render: (_: unknown, r: BoqItem) => (
            <div className="boq-actions-wrap">
              <Button size="small" type="text" icon={<EditOutlined />} onClick={() => { setEditItem(r); editForm.setFieldsValue(r); }} title="编辑" />
              <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />} title="删除" />
              </Popconfirm>
            </div>
          ),
        },
      ];
    }
    // GB50500 mode
    return [
      { title: "编码", dataIndex: "code", width: 80 },
      { title: "名称", dataIndex: "name", width: 160, render: (v: string, r: BoqItem) => (
        <span style={{ fontWeight: 500 }}>{renderEditable("name", v, r)}</span>
      ) },
      {
        title: "项目特征", dataIndex: "characteristics", ellipsis: true,
        render: (v: string, r: BoqItem) => renderEditable("characteristics", v, r),
      },
      { title: "单位", dataIndex: "unit", width: 70, render: (v: string, r: BoqItem) => renderEditable("unit", v, r) },
      {
        title: "工程量", dataIndex: "quantity", width: 110,
        render: (v: number, r: BoqItem) => renderEditable("quantity", v, r, true),
      },
      {
        title: (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--primary)" }}>auto_awesome</span>
            AI 综合单价
          </div>
        ),
        key: "unit_price", width: 140,
        render: (_: unknown, r: BoqItem) => {
          const lr = calcMap.get(r.id);
          const hasBinding = (bindingsMap.get(r.id)?.length ?? 0) > 0;
          if (!lr && !hasBinding) return <span className="boq-cell-editable-empty">—</span>;
          const unitPrice = lr && r.quantity > 0 ? lr.total / r.quantity : null;
          return (
            <button
              className="boq-unit-price-btn"
              onClick={() => openPriceTrace(r)}
              title="查看单价构成与溯源"
            >
              {unitPrice != null ? `${currencySymbol}${unitPrice.toFixed(2)}` : "查看"}
            </button>
          );
        },
      },
      {
        title: "合价", key: "total_price", width: 130,
        render: (_: unknown, r: BoqItem) => {
          const lr = calcMap.get(r.id);
          if (!lr) return <span className="boq-cell-editable-empty">—</span>;
          return <strong className="boq-total-price">{currencySymbol}{lr.total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</strong>;
        },
      },
      {
        title: "↕", width: 50,
        render: (_: unknown, r: BoqItem) => (
          <div className="boq-reorder-wrap">
            <button className="boq-reorder-btn" onClick={() => handleMove(r.id, "up")}>▲</button>
            <button className="boq-reorder-btn" onClick={() => handleMove(r.id, "down")}>▼</button>
          </div>
        ),
      },
      {
        title: "操作", width: 170,
        render: (_: unknown, r: BoqItem) => (
          <div className="boq-actions-wrap">
            <Button size="small" type="text" icon={<ThunderboltOutlined />} onClick={() => { setAgentBoqItem(r); setAgentOpen(true); }} title="Agent 组价" style={{ color: "#4096ff" }} />
            <Button size="small" type="text" icon={<BarChartOutlined />} onClick={() => navigate(`/pricing/analysis/${projectId}/${r.id}`)} title="综合单价分析" style={{ color: "#8b5cf6" }} />
            <Button size="small" type="text" icon={<RobotOutlined />} onClick={() => openMatch(r)} title="AI 匹配" />
            <Button size="small" type="text" icon={<EditOutlined />} onClick={() => { setEditItem(r); editForm.setFieldsValue(r); }} title="编辑" />
            <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
              <Button size="small" type="text" danger icon={<DeleteOutlined />} title="删除" />
            </Popconfirm>
          </div>
        ),
      },
    ];
  };
  const columns = buildColumns();

  return (
    <div>
      {/* Compact Toolbar */}
      <div className="boq-toolbar">
        <Button type="primary" icon={<RobotOutlined />} onClick={() => setGenOpen(true)}>
          AI {isHK ? "Smart Generate" : "智能开项"}
        </Button>
        <Upload
          accept=".xlsx,.xls"
          showUploadList={false}
          beforeUpload={(file) => { handleImport(file as File); return false; }}
        >
          <Button icon={<UploadOutlined />}>Excel {isHK ? "Import" : "导入"}</Button>
        </Upload>
        {!isHK && (
          <>
            <Button
              className="boq-toolbar-ai-btn"
              icon={<SyncOutlined />}
              onClick={handleAutoValuate}
              loading={avLoading}
            >
              AI 自动套定额套价
            </Button>
            <Button
              onClick={() => runBatchAction("confirm")}
              loading={batchConfirmLoading}
              disabled={selectedBoqIds.length === 0}
            >
              批量确认推荐
            </Button>
            <Button
              onClick={() => runBatchAction("replace")}
              loading={batchReplaceLoading}
              disabled={selectedBoqIds.length === 0}
            >
              批量替换为推荐
            </Button>
          </>
        )}
        {selectedBoqIds.length > 0 && (
          <>
            <Button onClick={() => setBatchDivOpen(true)}>
              批量改分部
            </Button>
            <Popconfirm title={`确认删除 ${selectedBoqIds.length} 项？`} onConfirm={handleBatchDelete}>
              <Button danger>批量删除</Button>
            </Popconfirm>
          </>
        )}
        <Select
          allowClear placeholder={isHK ? "Filter by Trade" : "按分部筛选"} style={{ width: 140 }}
          value={divisionFilter} onChange={handleDivisionFilterChange}
          options={divisions.map((d) => ({ label: d, value: d }))}
        />
        {isHK && <Tag color="orange">HKSMM4</Tag>}
        <div className="boq-toolbar-spacer" />
        <span className="boq-toolbar-count">已选 {selectedBoqIds.length} 项</span>
      </div>

      {/* BOQ Table */}
      <Table
        rowKey="id" columns={columns} dataSource={filtered}
        loading={loading} size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        rowSelection={{
          selectedRowKeys: selectedBoqIds,
          onChange: (keys) => setSelectedBoqIds(keys as number[]),
        }}
        expandable={{
        expandedRowRender: (record: BoqItem) => {
            const quotas = bindingsMap.get(record.id);
            const isExpSearch = expandSearchId === record.id;
            return (
              <div className="boq-expand-wrap">
                {/* Existing bindings */}
                {(!quotas || quotas.length === 0) ? (
                  <div className="boq-expand-empty">
                    <span className="material-symbols-outlined">link_off</span>
                    <span>暂无绑定定额</span>
                  </div>
                ) : (
                  quotas.map((q) => {
                    const lr = calcMap.get(record.id);
                    const isEditCoeff = editingCoeff?.bindingId === q.binding_id;
                    const unitMatch = q.quota_unit === record.unit;
                    const vStatus = validationMap.get(q.binding_id);
                    return (
                      <div key={q.binding_id} className="boq-quota-row">
                        <div className="boq-quota-row-left">
                          <span className="material-symbols-outlined boq-quota-icon">functions</span>
                          <Tag color="geekblue" style={{ fontSize: 11, marginRight: 6 }}>{q.quota_code}</Tag>
                          <span className="boq-quota-name">{q.quota_name}</span>
                          <span className="boq-quota-unit">{q.quota_unit}</span>
                          {/* Coefficient inline edit */}
                          {isEditCoeff ? (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, marginLeft: 6 }}>
                              <InputNumber
                                size="small" autoFocus min={0.01} step={0.05}
                                value={editingCoeffValue}
                                onChange={(v) => setEditingCoeffValue(v ?? 1)}
                                onPressEnter={handleCoeffSave}
                                onBlur={handleCoeffSave}
                                style={{ width: 72 }}
                              />
                            </span>
                          ) : (
                            <Tag
                              color="purple" style={{ fontSize: 11, marginLeft: 6, cursor: "pointer" }}
                              onClick={() => { setEditingCoeff({ bindingId: q.binding_id, boqItemId: record.id }); setEditingCoeffValue(q.coefficient); }}
                              title="点击编辑系数"
                            >
                              系数 ×{q.coefficient}
                            </Tag>
                          )}
                          {/* Validation status tag */}
                          {vStatus === "ok" && <Tag color="success" style={{ fontSize: 10, marginLeft: 4 }}>✓</Tag>}
                          {!unitMatch && <Tag color="warning" style={{ fontSize: 10, marginLeft: 4 }}>⚠单位不一致</Tag>}
                          {vStatus === "error" && <Tag color="error" style={{ fontSize: 10, marginLeft: 4 }}>❌异常</Tag>}
                        </div>
                        <div className="boq-quota-row-right">
                          <div className="boq-quota-qty-group">
                            <span className="boq-quota-qty-label">人工</span>
                            <span className="boq-quota-qty-value">{q.labor_qty}</span>
                          </div>
                          <div className="boq-quota-qty-group">
                            <span className="boq-quota-qty-label">材料</span>
                            <span className="boq-quota-qty-value">{q.material_qty}</span>
                          </div>
                          <div className="boq-quota-qty-group">
                            <span className="boq-quota-qty-label">机械</span>
                            <span className="boq-quota-qty-value">{q.machine_qty}</span>
                          </div>
                          {lr && (
                            <div className="boq-quota-cost">
                              {currencySymbol}{lr.direct_cost.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
                            </div>
                          )}
                          {/* Unbind button */}
                          <Popconfirm title="确认解绑此定额？" onConfirm={() => handleExpandUnbind(record.id, q.binding_id)}>
                            <Button size="small" type="text" danger icon={<DeleteOutlined />} title="解绑" style={{ marginLeft: 4 }} />
                          </Popconfirm>
                        </div>
                      </div>
                    );
                  })
                )}
                {/* Actions row: AI match + inline search toggle */}
                <div className="boq-expand-actions">
                  <Button type="link" size="small" icon={<RobotOutlined />} onClick={() => openMatch(record)}>
                    AI 匹配定额
                  </Button>
                  <Button
                    type="link" size="small"
                    onClick={() => { setExpandSearchId(isExpSearch ? null : record.id); setExpandSearchKw(""); setExpandSearchResults([]); }}
                  >
                    {isExpSearch ? "收起搜索" : "搜索添加定额"}
                  </Button>
                </div>
                {/* Inline quota search */}
                {isExpSearch && (
                  <div className="boq-expand-search-wrap">
                    <div className="boq-expand-search-bar">
                      <Input
                        size="small" placeholder="输入关键词搜索定额…" value={expandSearchKw}
                        onChange={(e) => setExpandSearchKw(e.target.value)}
                        onPressEnter={() => handleExpandSearch(record.id)}
                        style={{ width: 240 }}
                      />
                      <Button size="small" type="primary" loading={expandSearchLoading} onClick={() => handleExpandSearch(record.id)}>
                        搜索
                      </Button>
                    </div>
                    {expandSearchResults.map((c) => (
                      <div key={c.quota_item_id} className="boq-expand-search-result">
                        <div className="boq-expand-search-result-info">
                          <Tag color="blue" style={{ fontSize: 11 }}>{c.quota_code}</Tag>
                          <span className="boq-expand-search-result-name">{c.quota_name}</span>
                          <span className="boq-expand-search-result-unit">{c.unit}</span>
                          <span className="boq-expand-search-result-conf">{Math.round(c.confidence * 100)}%</span>
                        </div>
                        <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleExpandBind(record.id, c.quota_item_id)}>
                          绑定
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          },
          rowExpandable: () => true,
        }}
        footer={() => (
          <div>
            {/* 手动新增清单项 — dashed button */}
            <button className="boq-add-row-btn" onClick={() => setAddOpen(true)}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
              手动新增清单项
            </button>
            {/* 本节小计 */}
            {sectionTotal > 0 && (
              <div className="boq-section-total">
                <span>本节小计</span>
                <span className="boq-section-total-value">¥{sectionTotal.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</span>
              </div>
            )}
          </div>
        )}
      />

      {/* 新增弹窗 */}
      <Modal title="新增清单项" open={addOpen} onOk={handleAdd} onCancel={() => setAddOpen(false)} okText="创建">
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="编码" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="characteristics" label="项目特征"><Input.TextArea rows={2} placeholder="如：C30混凝土，截面400x400mm" /></Form.Item>
          <Form.Item name="unit" label="单位" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="quantity" label="工程量" rules={[{ required: true }]}><InputNumber style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="division" label="分部"><Input /></Form.Item>
        </Form>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal title="编辑清单项" open={!!editItem} onOk={handleEdit} onCancel={() => setEditItem(null)} okText="保存">
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="名称"><Input /></Form.Item>
          <Form.Item name="characteristics" label="项目特征"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="unit" label="单位"><Input /></Form.Item>
          <Form.Item name="quantity" label="工程量"><InputNumber style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="division" label="分部"><Input /></Form.Item>
        </Form>
      </Modal>

      {/* AI 智能开项弹窗 */}
      <Modal
        title={null}
        open={genOpen}
        onCancel={() => { setGenOpen(false); setGenItems([]); }}
        width={genItems.length > 0 ? 960 : 600}
        closable={false}
        className="gen-modal"
        footer={genItems.length > 0 ? [
          <span key="count" style={{ float: "left", lineHeight: "32px", color: "var(--text-secondary)", fontSize: 13 }}>
            已选 {genSelected.length}/{genItems.length} 项
          </span>,
          <Button key="cancel" onClick={() => setGenOpen(false)}>取消</Button>,
          <Button key="ok" type="primary" onClick={handleConfirmGen} icon={<RobotOutlined />}>
            确认添加 {genSelected.length} 项到清单
          </Button>,
        ] : null}
      >
        {/* Custom header */}
        <div className="boq-modal-header">
          <div className="boq-modal-header-icon"><RobotOutlined /></div>
          <div className="boq-modal-header-text">
            <h3>AI 智能开项</h3>
            <p>描述您的项目，AI 将自动生成工程量清单</p>
          </div>
          <button className="boq-modal-close" onClick={() => { setGenOpen(false); setGenItems([]); }}>×</button>
        </div>

        {/* Input area */}
        <div className="boq-gen-input-wrap">
          <textarea
            rows={3}
            placeholder={"描述您的项目，例如：\n• 5层办公楼，框架结构\n• 住宅小区，含基础和装修\n• 市政道路工程，双向四车道"}
            value={genDesc}
            onChange={(e) => setGenDesc(e.target.value)}
            className="boq-gen-textarea"
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <Button
              type="primary" icon={<RobotOutlined />}
              onClick={handleGenerate} loading={genLoading}
              disabled={!genDesc.trim()}
              style={{ borderRadius: 8 }}
            >
              {genLoading ? "AI 生成中..." : "生成清单"}
            </Button>
          </div>
        </div>

        {/* Tips when no results */}
        {genItems.length === 0 && !genLoading && (
          <div className="boq-gen-tips">
            {[
              { icon: "🏢", label: "办公楼", desc: "5层办公楼，框架结构" },
              { icon: "🏠", label: "住宅", desc: "住宅小区，含基础和装修" },
              { icon: "🛣️", label: "市政道路", desc: "市政道路工程" },
            ].map((tip) => (
              <button key={tip.label} className="boq-gen-tip" onClick={() => setGenDesc(tip.desc)}>
                <div className="boq-gen-tip-icon">{tip.icon}</div>
                <div className="boq-gen-tip-label">{tip.label}</div>
                <div className="boq-gen-tip-desc">{tip.desc}</div>
              </button>
            ))}
          </div>
        )}

        {/* Results table */}
        {genItems.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {genFloors > 1 && (
              <Tag color="blue" style={{ marginBottom: 10 }}>检测到 {genFloors} 层，工程量已按楼层缩放</Tag>
            )}
            <Table
              rowKey="code" size="small" pagination={false}
              scroll={{ y: 360 }}
              rowSelection={{
                selectedRowKeys: genSelected,
                onChange: (keys) => setGenSelected(keys as string[]),
              }}
              dataSource={genItems}
              columns={[
                { title: "编码", dataIndex: "code", width: 80 },
                { title: "名称", dataIndex: "name", width: 140, render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
                {
                  title: "项目特征", dataIndex: "characteristics", width: 200,
                  render: (v: string) => v ? (
                    <div style={{ fontSize: 11, color: "var(--text-secondary)", whiteSpace: "pre-line", lineHeight: 1.5 }}>{v}</div>
                  ) : <span style={{ color: "var(--text-muted)" }}>—</span>,
                },
                { title: "单位", dataIndex: "unit", width: 50 },
                { title: "工程量", dataIndex: "quantity", width: 80, render: (v: number) => <span style={{ fontWeight: 500 }}>{v}</span> },
                { title: "分部", dataIndex: "division", width: 80, render: (v: string) => <Tag style={{ fontSize: 11 }}>{v}</Tag> },
                {
                  title: "AI 理由", dataIndex: "reason", width: 180,
                  render: (r: string) => (
                    <div style={{ fontSize: 11, color: "var(--primary)", lineHeight: 1.4 }}>
                      <RobotOutlined style={{ marginRight: 4 }} />{r}
                    </div>
                  ),
                },
              ]}
            />
          </div>
        )}
      </Modal>

      {/* AI 匹配弹窗 */}
      <Modal
        title={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="boq-modal-header-icon" style={{ width: 28, height: 28, fontSize: 14 }}>
              <RobotOutlined />
            </div>
            AI 定额匹配 — {matchBoqName}
          </span>
        }
        open={matchOpen} onCancel={() => setMatchOpen(false)}
        footer={null} width={640}
      >
        {matchLoading ? (
          <div className="boq-match-loading">
            <SyncOutlined spin style={{ fontSize: 24, color: "var(--primary)", marginBottom: 12 }} />
            <div>AI 正在分析匹配候选定额...</div>
          </div>
        ) : candidates.length === 0 ? (
          <div className="boq-match-empty">未找到匹配的定额</div>
        ) : (
          candidates.map((c, i) => (
            <div key={c.quota_item_id} className={`boq-match-card${i === 0 ? " boq-match-card-best" : ""}`}>
              {i === 0 && <Tag color="green" style={{ position: "absolute", top: 8, right: 8, fontSize: 11 }}>AI 推荐</Tag>}
              <div className="boq-match-card-head">
                <div className="boq-match-card-info">
                  <Tag color="blue">{c.quota_code}</Tag>
                  <strong>{c.quota_name}</strong>
                  <span className="boq-match-card-unit">{c.unit}</span>
                </div>
                <Button
                  type="primary" size="small" icon={<CheckCircleOutlined />}
                  onClick={() => confirmCandidate(c.quota_item_id)}
                  style={{ borderRadius: 8 }}
                >确认绑定</Button>
              </div>
              <div className="boq-match-card-reasons">
                <Progress
                  percent={Math.round(c.confidence * 100)}
                  size="small"
                  strokeColor={
                    c.confidence > 0.7
                      ? { from: "#52c41a", to: "#95de64" }
                      : c.confidence > 0.4
                        ? { from: "#faad14", to: "#ffc53d" }
                        : { from: "#ff4d4f", to: "#ff7875" }
                  }
                />
                <div className="boq-match-card-reasons-text">
                  {c.reasons.map((r, j) => <Tag key={j} color="default" style={{ marginTop: 2 }}>{r}</Tag>)}
                </div>
              </div>
            </div>
          ))
        )}
      </Modal>

      <Modal
        title="AI 综合单价溯源"
        open={priceTraceOpen}
        onCancel={() => setPriceTraceOpen(false)}
        footer={null}
        width={760}
      >
        {priceTraceLoading ? (
          <div style={{ textAlign: "center", padding: 36 }}>
            <Spin />
          </div>
        ) : !priceTrace ? (
          <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: 24 }}>
            暂无可展示的溯源信息
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 16, fontWeight: 700 }}>
                [{priceTrace.boq_code}] {priceTrace.boq_name}
              </div>
              <div style={{ color: "var(--text-secondary)", fontSize: 12 }}>
                数量：{priceTrace.boq_quantity} {priceTrace.boq_unit}
              </div>
            </div>

            <Descriptions size="small" column={2} bordered style={{ marginBottom: 12 }}>
              <Descriptions.Item label="AI 综合单价">
                {priceTrace.unit_price != null ? `¥${priceTrace.unit_price.toFixed(2)}` : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="合价">
                {priceTrace.calc_total != null ? `¥${priceTrace.calc_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}` : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="人工单价">¥{priceTrace.price_snapshot.labor_price.toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="材料单价">¥{priceTrace.price_snapshot.material_price.toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="机械单价">¥{priceTrace.price_snapshot.machine_price.toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="税率">{((priceTrace.fee_config_snapshot.tax_rate ?? 0) * 100).toFixed(2)}%</Descriptions.Item>
            </Descriptions>

            {priceTrace.calc_breakdown && (
              <Descriptions size="small" column={3} bordered style={{ marginBottom: 12 }}>
                <Descriptions.Item label="直接费">¥{priceTrace.calc_breakdown.direct_cost.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="管理费">¥{priceTrace.calc_breakdown.management_fee.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="利润">¥{priceTrace.calc_breakdown.profit.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="规费">¥{priceTrace.calc_breakdown.regulatory_fee.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="税金">¥{priceTrace.calc_breakdown.tax.toFixed(2)}</Descriptions.Item>
                <Descriptions.Item label="税前合计">¥{priceTrace.calc_breakdown.pre_tax_total.toFixed(2)}</Descriptions.Item>
              </Descriptions>
            )}

            {priceTrace.bindings.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>组合定额</div>
                <Table
                  size="small"
                  rowKey="binding_id"
                  pagination={false}
                  dataSource={priceTrace.bindings}
                  columns={[
                    { title: "定额编码", dataIndex: ["quota", "quota_code"], width: 110 },
                    { title: "定额名称", dataIndex: ["quota", "quota_name"] },
                    { title: "系数", dataIndex: "coefficient", width: 80, render: (v: number) => `×${v}` },
                    {
                      title: "直接费贡献",
                      dataIndex: "direct_cost",
                      width: 120,
                      render: (v: number | null) => (v != null ? `¥${v.toFixed(2)}` : "—"),
                    },
                  ]}
                />
              </div>
            )}

            <div className="ai-explain-box">
              <RobotOutlined style={{ color: "var(--primary)", marginRight: 6 }} />
              <strong>AI 解释：</strong>
              <div style={{ marginTop: 6, color: "var(--text-secondary)", lineHeight: 1.7 }}>
                {priceTrace.explanation}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* AI 自动套定额套价结果弹窗 */}
      <Modal
        title={null}
        open={avOpen}
        onCancel={() => setAvOpen(false)}
        width={720}
        closable={false}
        className="gen-modal"
        footer={avResult ? [
          <Button key="close" type="primary" onClick={() => setAvOpen(false)}>完成</Button>,
        ] : null}
      >
        {/* Header */}
        <div className="boq-modal-header">
          <div className="boq-modal-header-icon"><SyncOutlined spin={avLoading} /></div>
          <div className="boq-modal-header-text">
            <h3>{avLoading ? "AI 正在自动套定额套价..." : "自动套定额套价完成"}</h3>
            <p>{avLoading ? "正在为清单项匹配定额并计算造价，请稍候" : "已完成所有清单项的定额匹配和造价计算"}</p>
          </div>
          {!avLoading && <button className="boq-modal-close" onClick={() => setAvOpen(false)}>×</button>}
        </div>

        {avLoading && (
          <div className="boq-av-loading">
            <SyncOutlined spin className="boq-av-loading-icon" />
            <div className="boq-av-loading-text">
              AI 正在分析 {items.length} 个清单项，匹配最佳定额并计算造价...
            </div>
            <div className="boq-av-loading-hint">此过程可能需要 10~30 秒</div>
          </div>
        )}

        {avResult && !avLoading && (
          <>
            {/* Summary cards */}
            <div className="boq-av-summary-grid">
              {[
                { label: "清单总数", value: avResult.total_items, color: "var(--text-primary)" },
                { label: "已有绑定", value: avResult.already_bound, color: "#6366f1" },
                { label: "新匹配", value: avResult.newly_matched, color: "#22c55e" },
                { label: "跳过", value: avResult.skipped, color: "#f59e0b" },
              ].map((card) => (
                <div key={card.label} className="boq-av-summary-card">
                  <div className="boq-av-summary-card-value" style={{ color: card.color }}>{card.value}</div>
                  <div className="boq-av-summary-card-label">{card.label}</div>
                </div>
              ))}
            </div>

            {/* Calc summary */}
            {avResult.calc_summary && (
              <div className="boq-av-calc-box">
                <div className="boq-av-calc-title">造价计算结果</div>
                <div className="boq-av-calc-grid">
                  <div><span>直接费：</span><strong>¥{avResult.calc_summary.total_direct.toLocaleString()}</strong></div>
                  <div><span>管理费：</span><strong>¥{avResult.calc_summary.total_management.toLocaleString()}</strong></div>
                  <div><span>利润：</span><strong>¥{avResult.calc_summary.total_profit.toLocaleString()}</strong></div>
                  <div><span>税金：</span><strong>¥{avResult.calc_summary.total_tax.toLocaleString()}</strong></div>
                  <div className="boq-av-calc-grand">
                    <span>工程合计：</span>
                    <strong>¥{avResult.calc_summary.grand_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</strong>
                  </div>
                </div>
              </div>
            )}

            {/* Match details */}
            {avResult.match_details.length > 0 && (
              <div>
                <div className="boq-av-detail-title">匹配明细</div>
                <div className="boq-av-detail-scroll">
                  {avResult.match_details.map((d) => (
                    <div key={d.boq_item_id} className={`boq-av-detail-item${d.status === "matched" ? " boq-av-detail-item-matched" : ""}`}>
                      {d.status === "matched"
                        ? <CheckCircleOutlined style={{ color: "#22c55e", flexShrink: 0 }} />
                        : <span style={{ color: "#f59e0b", flexShrink: 0 }}>⚠</span>
                      }
                      <div className="boq-av-detail-item-body">
                        <div className="boq-av-detail-item-head">
                          <Tag color="blue" style={{ fontSize: 11 }}>{d.boq_code}</Tag>
                          <span>{d.boq_name}</span>
                        </div>
                        {d.status === "matched" && (
                          <div className="boq-av-detail-item-sub">
                            → {d.quota_code} {d.quota_name}
                            <span className="boq-av-conf">置信度 {Math.round(d.confidence * 100)}%</span>
                          </div>
                        )}
                        {d.status === "skipped" && (
                          <div className="boq-av-detail-item-warn">未找到合适的定额匹配</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </Modal>

      {/* 批量改分部弹窗 */}
      <Modal
        title="批量修改分部"
        open={batchDivOpen}
        onOk={handleBatchDivision}
        onCancel={() => { setBatchDivOpen(false); setBatchDivTarget(""); }}
        okText="确认修改"
        okButtonProps={{ disabled: !batchDivTarget }}
      >
        <div style={{ marginBottom: 12, color: "var(--text-secondary)", fontSize: 13 }}>
          已选 {selectedBoqIds.length} 项，将统一修改为：
        </div>
        <Select
          placeholder="选择目标分部" style={{ width: "100%" }}
          value={batchDivTarget || undefined}
          onChange={(v) => setBatchDivTarget(v)}
          showSearch allowClear
        >
          {divisions.map((d) => <Select.Option key={d} value={d}>{d}</Select.Option>)}
        </Select>
        <div style={{ marginTop: 8 }}>
          <Input
            placeholder="或输入新分部名称"
            value={batchDivTarget}
            onChange={(e) => setBatchDivTarget(e.target.value)}
          />
        </div>
      </Modal>

      {/* Agent Panel */}
      {agentBoqItem && (
        <AgentPanel
          projectId={projectId}
          boqItem={agentBoqItem}
          open={agentOpen}
          onClose={() => { setAgentOpen(false); setAgentBoqItem(null); }}
          onBindingsChanged={() => { load(); onDataChanged?.(); }}
        />
      )}
    </div>
  );
}
