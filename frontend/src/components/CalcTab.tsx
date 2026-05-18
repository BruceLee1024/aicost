import { useState } from "react";
import {
  Button, Card, Descriptions, Space, Statistic, Tag, message,
} from "antd";
import { BizTable } from "./BizTable";
import { CalculatorOutlined, DownloadOutlined, RobotOutlined } from "@ant-design/icons";
import type { CalcProvenance, CalcSummary, LineCalcResult } from "../api";
import { api } from "../api";

interface Props { projectId: number }

export default function CalcTab({ projectId }: Props) {
  const [result, setResult] = useState<CalcSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [provCache, setProvCache] = useState<Record<number, CalcProvenance>>({});

  const handleCalc = async () => {
    setLoading(true);
    try {
      const res = await api.calculate(projectId);
      setResult(res);
      message.success(`计算完成，合计 ¥${res.grand_total}`);
    } catch { message.error("计算失败"); }
    setLoading(false);
  };

  const loadProvenance = async (boqItemId: number) => {
    if (provCache[boqItemId]) return;
    try {
      const p = await api.getProvenance(boqItemId);
      setProvCache((prev) => ({ ...prev, [boqItemId]: p }));
    } catch { /**/ }
  };

  const handleExport = () => {
    const url = api.exportValuationUrl(projectId);
    const form = document.createElement("form");
    form.method = "POST";
    form.action = url;
    form.target = "_blank";
    document.body.appendChild(form);
    form.submit();
    form.remove();
    message.info("正在生成报告...");
  };

  const columns = [
    { title: "编码", dataIndex: "boq_code", width: 100 },
    { title: "名称", dataIndex: "boq_name", ellipsis: true },
    { title: "直接费", dataIndex: "direct_cost", width: 100 },
    { title: "管理费", dataIndex: "management_fee", width: 100 },
    { title: "利润", dataIndex: "profit", width: 80 },
    { title: "规费", dataIndex: "regulatory_fee", width: 80 },
    { title: "税金", dataIndex: "tax", width: 80 },
    { title: "合计", dataIndex: "total", width: 110, render: (v: number) => <strong>¥{v}</strong> },
  ];

  const expandedRowRender = (record: LineCalcResult) => {
    const prov = provCache[record.boq_item_id];
    if (!prov) return <div style={{ color: "#94a3b8", padding: 8 }}>加载中...</div>;
    return (
      <div className="ai-explain-box">
        <RobotOutlined style={{ color: "var(--primary)", marginRight: 8 }} />
        <strong>AI 溯源解释：</strong>
        <div style={{ marginTop: 6, color: "var(--text-secondary)", lineHeight: 1.6 }}>{prov.explanation}</div>
        <div style={{ marginTop: 8 }}>
          {prov.bindings.map((b) => (
            <Tag key={b.binding_id} color="blue" style={{ marginTop: 4 }}>
              {b.quota.quota_code} — {b.quota.quota_name}
            </Tag>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div>
      <Space style={{ marginBottom: 20 }} size="middle">
        <Button type="primary" icon={<CalculatorOutlined />} loading={loading} onClick={handleCalc} size="large">
          执行计算
        </Button>
        {result && (
          <Button icon={<DownloadOutlined />} onClick={handleExport} size="middle">
            导出计价报告
          </Button>
        )}
      </Space>

      {!result && !loading && (
        <div style={{
          textAlign: "center", padding: "56px 24px",
          background: "var(--bg-surface)", borderRadius: 16,
          border: "1px dashed var(--border)",
        }}>
          <span className="material-symbols-outlined" style={{
            fontSize: 56, color: "var(--primary)", display: "block",
            marginBottom: 16, opacity: 0.5,
          }}>calculate</span>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", marginBottom: 8 }}>尚未执行计算</div>
          <div style={{ color: "var(--text-muted)", fontSize: 13, maxWidth: 400, margin: "0 auto", lineHeight: 1.6 }}>
            请先确保清单项已绑定定额，然后点击上方「执行计算」按钮开始计价。
            <br />计算将根据定额绑定自动生成费用明细和溯源。
          </div>
        </div>
      )}

      {result && (
        <>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={4} size="small">
              <Descriptions.Item label="直接费">¥{result.total_direct}</Descriptions.Item>
              <Descriptions.Item label="管理费">¥{result.total_management}</Descriptions.Item>
              <Descriptions.Item label="利润">¥{result.total_profit}</Descriptions.Item>
              <Descriptions.Item label="规费">¥{result.total_regulatory}</Descriptions.Item>
              <Descriptions.Item label="税金">¥{result.total_tax}</Descriptions.Item>
              <Descriptions.Item label="措施费">¥{result.total_measures}</Descriptions.Item>
              <Descriptions.Item label="合计">
              <Statistic value={result.grand_total} prefix="¥" styles={{ content: { fontSize: 18, fontWeight: "bold", color: "var(--primary)" } }} />
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <BizTable<LineCalcResult>
            showIndex
            rowKey="boq_item_id" columns={columns}
            dataSource={result.line_results}
            pagination={false}
            expandable={{
              expandedRowRender,
              onExpand: (expanded, record) => { if (expanded) loadProvenance(record.boq_item_id); },
              expandRowByClick: true,
            }}
          />
          <div style={{
            marginTop: 12, fontSize: 12, color: "var(--text-secondary)",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <RobotOutlined style={{ color: "var(--primary)" }} />
          </div>
        </>
      )}
    </div>
  );
}
