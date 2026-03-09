import { useEffect, useState } from "react";
import {
  Button, Drawer, Modal, Popconfirm, Space, Spin, Table, Tag, message,
} from "antd";
import { LinkOutlined, RobotOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { Binding, BoqItem, CalcProvenance, MatchCandidate } from "../api";
import { api } from "../api";

interface Props { projectId: number }

interface BoqBindingRow extends BoqItem {
  bindings: Binding[];
  bound: boolean;
}

export default function BindingTab({ projectId }: Props) {
  const [rows, setRows] = useState<BoqBindingRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  // provenance drawer
  const [provOpen, setProvOpen] = useState(false);
  const [provenance, setProvenance] = useState<CalcProvenance | null>(null);
  const [provLoading, setProvLoading] = useState(false);
  // replace modal
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceRow, setReplaceRow] = useState<BoqBindingRow | null>(null);
  const [replaceCandidates, setReplaceCandidates] = useState<MatchCandidate[]>([]);
  const [replaceChosen, setReplaceChosen] = useState<number | undefined>(undefined);
  const [replaceLoading, setReplaceLoading] = useState(false);
  const [replaceSubmitting, setReplaceSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const items = await api.listBoqItems(projectId);
      const enriched: BoqBindingRow[] = await Promise.all(
        items.map(async (item) => {
          try {
            const bindings = await api.listBindings(item.id);
            return { ...item, bindings, bound: bindings.length > 0 };
          } catch {
            return { ...item, bindings: [], bound: false };
          }
        }),
      );
      setRows(enriched);
    } catch { /**/ }
    setLoading(false);
  };

  const openReplaceModal = async (row: BoqBindingRow) => {
    setReplaceOpen(true);
    setReplaceRow(row);
    setReplaceCandidates([]);
    setReplaceChosen(undefined);
    setReplaceLoading(true);
    try {
      const candidates = await api.getQuotaCandidates(row.id, 5);
      if (candidates.length === 0) {
        message.warning("未找到可替换候选");
      } else {
        setReplaceCandidates(candidates);
        setReplaceChosen(candidates[0].quota_item_id);
      }
    } catch {
      message.error("加载候选失败");
      setReplaceOpen(false);
    }
    setReplaceLoading(false);
  };

  const confirmManualReplace = async () => {
    if (!replaceRow || !replaceChosen) {
      message.warning("请先选择一个候选定额");
      return;
    }
    setReplaceSubmitting(true);
    try {
      await api.replaceBinding(replaceRow.id, replaceChosen);
      message.success("绑定替换成功");
      setReplaceOpen(false);
      await load();
    } catch {
      message.error("替换失败");
    }
    setReplaceSubmitting(false);
  };

  const handleClearBindings = async (row: BoqBindingRow) => {
    try {
      const res = await api.clearBindings(row.id);
      message.success(`已移除 ${res.removed} 条绑定`);
      await load();
    } catch {
      message.error("解绑失败");
    }
  };

  useEffect(() => { load(); }, [projectId]);

  const unboundRows = rows.filter((r) => !r.bound);

  // Batch AI match: for each unbound item, get top-1 candidate and confirm
  const handleBatchBind = async () => {
    if (unboundRows.length === 0) { message.info("所有清单项均已绑定"); return; }
    setBatchLoading(true);
    let successCount = 0;
    for (const row of unboundRows) {
      try {
        const candidates = await api.getQuotaCandidates(row.id, 1);
        if (candidates.length > 0) {
          await api.confirmBinding(row.id, candidates[0].quota_item_id);
          successCount++;
        }
      } catch { /**/ }
    }
    message.success(`批量智能绑定完成：${successCount}/${unboundRows.length} 项`);
    setBatchLoading(false);
    load();
  };

  // Provenance
  const openProvenance = async (boqItemId: number) => {
    setProvOpen(true);
    setProvLoading(true);
    setProvenance(null);
    try {
      setProvenance(await api.getProvenance(boqItemId));
    } catch { message.error("获取溯源失败"); }
    setProvLoading(false);
  };

  const columns = [
    { title: "编码", dataIndex: "code", width: 100 },
    { title: "名称", dataIndex: "name", ellipsis: true },
    { title: "单位", dataIndex: "unit", width: 60 },
    { title: "工程量", dataIndex: "quantity", width: 90 },
    {
      title: "绑定状态", width: 110,
      render: (_: unknown, r: BoqBindingRow) =>
        r.bound
          ? <Tag color="green" icon={<LinkOutlined />}>已绑定</Tag>
          : <Tag color="red">未绑定</Tag>,
    },
    {
      title: "操作", width: 260,
      render: (_: unknown, r: BoqBindingRow) =>
        r.bound ? (
          <Space size={6}>
            <Button size="small" icon={<RobotOutlined />} onClick={() => openProvenance(r.id)}>
              查看溯源
            </Button>
            <Button size="small" onClick={() => openReplaceModal(r)}>
              手动重配
            </Button>
            <Popconfirm title="确认清空该清单项全部绑定？" onConfirm={() => handleClearBindings(r)}>
              <Button size="small" danger>
                解绑
              </Button>
            </Popconfirm>
          </Space>
        ) : null,
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 20 }} size="middle">
        <Tag color="blue" style={{ padding: "4px 12px", fontSize: 13 }}>✓ 已绑定 {rows.length - unboundRows.length}</Tag>
        <Tag color="red" style={{ padding: "4px 12px", fontSize: 13 }}>○ 未绑定 {unboundRows.length}</Tag>
        <Button
          type="primary" icon={<ThunderboltOutlined />}
          loading={batchLoading}
          onClick={handleBatchBind}
          disabled={unboundRows.length === 0}
        >
          AI 批量智能绑定（{unboundRows.length} 项）
        </Button>
      </Space>

      <Table
        rowKey="id" columns={columns} dataSource={rows}
        loading={loading} size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        rowClassName={(r) => r.bound ? "" : "ant-table-row-warning"}
      />

      <Modal
        title={replaceRow ? `手动重配候选 - [${replaceRow.code}] ${replaceRow.name}` : "手动重配候选"}
        open={replaceOpen}
        onCancel={() => setReplaceOpen(false)}
        onOk={confirmManualReplace}
        okText="确认替换"
        confirmLoading={replaceSubmitting}
        width={760}
      >
        {replaceLoading ? (
          <div style={{ textAlign: "center", padding: 24 }}><Spin /></div>
        ) : replaceCandidates.length === 0 ? (
          <div style={{ color: "var(--text-secondary)", padding: 24, textAlign: "center" }}>暂无候选</div>
        ) : (
          <Table
            rowKey="quota_item_id"
            size="small"
            pagination={false}
            dataSource={replaceCandidates}
            rowSelection={{
              type: "radio",
              selectedRowKeys: replaceChosen ? [replaceChosen] : [],
              onChange: (keys) => setReplaceChosen(Number(keys[0])),
            }}
            columns={[
              { title: "定额编码", dataIndex: "quota_code", width: 100 },
              { title: "定额名称", dataIndex: "quota_name" },
              { title: "单位", dataIndex: "unit", width: 60 },
              {
                title: "置信度",
                dataIndex: "confidence",
                width: 80,
                render: (v: number) => `${Math.round(v * 100)}%`,
              },
              {
                title: "理由",
                dataIndex: "reasons",
                width: 240,
                render: (reasons: string[]) => (
                  <span style={{ color: "var(--text-secondary)" }}>
                    {reasons?.slice(0, 2).join("；") || "—"}
                  </span>
                ),
              },
            ]}
          />
        )}
      </Modal>

      <Drawer
        title={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 28, height: 28, borderRadius: 8,
              background: "var(--primary)", color: "#fff", fontSize: 14,
            }}>
              <RobotOutlined />
            </div>
            AI 计算溯源
          </span>
        }
        open={provOpen} onClose={() => setProvOpen(false)} size={500}
      >
        {provLoading ? <Spin /> : provenance ? (
          <div>
            <h4 style={{ fontSize: 16, marginBottom: 8 }}>{provenance.boq_code} — {provenance.boq_name}</h4>
            <p style={{ color: "var(--text-secondary)" }}>数量：{provenance.boq_quantity} {provenance.boq_unit}</p>
            {provenance.bindings.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>绑定的定额：</strong>
                {provenance.bindings.map((b) => (
                  <div key={b.binding_id} style={{
                    marginTop: 8, padding: 12, background: "var(--bg)",
                    borderRadius: 8, border: "1px solid var(--border)",
                  }}>
                    <Tag color="blue">{b.quota.quota_code}</Tag> <strong>{b.quota.quota_name}</strong>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6, display: "flex", gap: 12 }}>
                      <span>人工 {b.quota.labor_qty}</span>
                      <span>材料 {b.quota.material_qty}</span>
                      <span>机械 {b.quota.machine_qty}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {provenance.calc_total != null && (
              <p style={{ fontSize: 16, fontWeight: 700 }}>计算合计：<span style={{ color: "var(--primary)" }}>¥{provenance.calc_total}</span></p>
            )}
            <div className="ai-explain-box" style={{ marginTop: 16 }}>
              <RobotOutlined style={{ color: "var(--primary)", marginRight: 8 }} />
              <strong>AI 解释：</strong>
              <div style={{ marginTop: 6, color: "var(--text-secondary)", lineHeight: 1.6 }}>{provenance.explanation}</div>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
