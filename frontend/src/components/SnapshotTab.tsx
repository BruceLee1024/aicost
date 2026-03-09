import { useEffect, useState } from "react";
import {
  Button, Card, Input, Select, Space, Statistic, Table, Tag, message,
} from "antd";
import { CameraOutlined, DownloadOutlined, RobotOutlined, SwapOutlined } from "@ant-design/icons";
import type { DiffReport, LineDiff, Snapshot } from "../api";
import { api } from "../api";

interface Props { projectId: number }

export default function SnapshotTab({ projectId }: Props) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [label, setLabel] = useState("");
  const [snapA, setSnapA] = useState<number | undefined>();
  const [snapB, setSnapB] = useState<number | undefined>();
  const [diff, setDiff] = useState<DiffReport | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const load = async () => {
    try { setSnapshots(await api.listSnapshots(projectId)); } catch { /**/ }
  };
  useEffect(() => { load(); }, [projectId]);

  const handleCreate = async () => {
    try {
      await api.createSnapshot(projectId, label || "快照");
      message.success("快照已创建");
      setLabel("");
      load();
    } catch { message.error("创建快照失败"); }
  };

  const handleDiff = async () => {
    if (!snapA || !snapB) { message.warning("请选择两个快照"); return; }
    setDiffLoading(true);
    try {
      setDiff(await api.diffSnapshots(projectId, snapA, snapB));
    } catch { message.error("对比失败"); }
    setDiffLoading(false);
  };

  const handleExportDiff = () => {
    if (!snapA || !snapB) return;
    const url = api.exportDiffUrl(snapA, snapB);
    const form = document.createElement("form");
    form.method = "POST"; form.action = url; form.target = "_blank";
    document.body.appendChild(form); form.submit(); form.remove();
  };

  const snapColumns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "标签", dataIndex: "label" },
    { title: "合计", dataIndex: "grand_total", width: 120, render: (v: number) => `¥${v}` },
    { title: "创建时间", dataIndex: "created_at", width: 200 },
  ];

  const diffColumns = [
    { title: "编码", dataIndex: "boq_code", width: 100 },
    { title: "名称", dataIndex: "boq_name", ellipsis: true },
    {
      title: "变更类型", dataIndex: "change_type", width: 90,
      render: (t: string) => {
        const colors: Record<string, string> = { added: "green", removed: "red", modified: "blue" };
        const labels: Record<string, string> = { added: "新增", removed: "删除", modified: "变更" };
        return <Tag color={colors[t] ?? "default"}>{labels[t] ?? t}</Tag>;
      },
    },
    { title: "旧合计", dataIndex: "old_total", width: 100 },
    { title: "新合计", dataIndex: "new_total", width: 100 },
    {
      title: "差异", dataIndex: "delta", width: 100,
      render: (v: number) => (
        <span style={{ color: v > 0 ? "#cf1322" : v < 0 ? "#3f8600" : undefined }}>
          {v > 0 ? "+" : ""}{v}
        </span>
      ),
    },
  ];

  const snapOpts = snapshots.map((s) => ({ label: `#${s.id} ${s.label} (¥${s.grand_total})`, value: s.id }));

  return (
    <div>
      {/* Create snapshot */}
      <Space style={{ marginBottom: 20 }} size="middle">
        <Input placeholder="快照标签" value={label} onChange={(e) => setLabel(e.target.value)} style={{ width: 220, borderRadius: 10 }} size="large" />
        <Button type="primary" icon={<CameraOutlined />} onClick={handleCreate} size="large">创建快照</Button>
      </Space>

      <Table rowKey="id" columns={snapColumns} dataSource={snapshots} pagination={false} size="small" />

      {/* Diff comparison */}
      {snapshots.length >= 2 && (
        <Card title={
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <SwapOutlined style={{ color: "var(--primary)" }} /> 快照对比
          </span>
        } size="small" style={{ marginTop: 24 }}>
          <Space style={{ marginBottom: 20 }} size="middle">
            <Select placeholder="快照 A" style={{ width: 260 }} options={snapOpts} value={snapA} onChange={setSnapA} />
            <SwapOutlined style={{ color: "var(--text-secondary)" }} />
            <Select placeholder="快照 B" style={{ width: 260 }} options={snapOpts} value={snapB} onChange={setSnapB} />
            <Button type="primary" onClick={handleDiff} loading={diffLoading}>对比</Button>
          </Space>

          {diff && (
            <>
          <Card size="small" style={{ marginBottom: 14 }}>
                <Space size="large">
                  <Statistic title="旧合计" value={diff.old_grand_total} prefix="¥" />
                  <Statistic title="新合计" value={diff.new_grand_total} prefix="¥" />
                  <Statistic
                    title="差异" value={diff.grand_total_delta} prefix="¥"
                    styles={{ content: { color: diff.grand_total_delta > 0 ? "#ef4444" : "#22c55e", fontWeight: 700 } }}
                  />
                </Space>
              </Card>

              {diff.explanation && (
                <div className="ai-explain-box" style={{ marginBottom: 14 }}>
                  <RobotOutlined style={{ color: "var(--primary)", marginRight: 8 }} />
                  <strong>AI 差异分析：</strong>
                  <div style={{ marginTop: 6, color: "var(--text-secondary)", lineHeight: 1.6 }}>{diff.explanation}</div>
                </div>
              )}

              <Table
                rowKey={(r: LineDiff) => r.boq_code} columns={diffColumns}
                dataSource={diff.lines} pagination={false} size="small"
              />
              <Button icon={<DownloadOutlined />} onClick={handleExportDiff} style={{ marginTop: 8 }}>
                导出差异报告
              </Button>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
