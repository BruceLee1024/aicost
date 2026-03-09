import { useEffect, useState } from "react";
import { Button, Card, Col, Row, Statistic, Table, Tag } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined, WarningOutlined } from "@ant-design/icons";
import type { ValidationIssue, ValidationReport } from "../api";
import { api } from "../api";

interface Props { projectId: number }

export default function ValidationTab({ projectId }: Props) {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try { setReport(await api.validate(projectId)); } catch { /**/ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [projectId]);

  const columns = [
    {
      title: "级别", dataIndex: "severity", width: 80,
      render: (s: string) =>
        s === "error"
          ? <Tag color="red" icon={<CloseCircleOutlined />}>错误</Tag>
          : <Tag color="orange" icon={<WarningOutlined />}>警告</Tag>,
    },
    { title: "规则代码", dataIndex: "code", width: 200 },
    { title: "说明", dataIndex: "message" },
    { title: "建议", dataIndex: "suggestion" },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20 }}>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} size="middle">刷新校验</Button>
      </div>
      {report && (
        <Row gutter={20} style={{ marginBottom: 20 }}>
          <Col span={8}>
            <div className="stat-card">
              <div className="stat-card-icon blue"><span className="material-symbols-outlined">warning</span></div>
              <Statistic title="总问题数" value={report.total_issues} />
            </div>
          </Col>
          <Col span={8}>
            <div className="stat-card">
              <div className="stat-card-icon red"><span className="material-symbols-outlined">cancel</span></div>
              <Statistic
                title="错误" value={report.errors}
                styles={report.errors > 0 ? { content: { color: "#ef4444" } } : undefined}
              />
            </div>
          </Col>
          <Col span={8}>
            <div className="stat-card">
              <div className="stat-card-icon orange"><span className="material-symbols-outlined">error</span></div>
              <Statistic
                title="警告" value={report.warnings}
                styles={report.warnings > 0 ? { content: { color: "#f59e0b" } } : undefined}
              />
            </div>
          </Col>
        </Row>
      )}
      {report && report.total_issues === 0 ? (
        <Card style={{ textAlign: "center", padding: 48 }}>
          <CheckCircleOutlined style={{ fontSize: 56, color: "#22c55e" }} />
          <div style={{ marginTop: 16, fontSize: 17, color: "#22c55e", fontWeight: 600 }}>校验通过，无问题</div>
          <div style={{ marginTop: 8, color: "var(--text-secondary)", fontSize: 13 }}>所有校验规则均已通过</div>
        </Card>
      ) : (
        <Table
          rowKey={(r: ValidationIssue) => `${r.code}-${r.boq_item_id ?? "g"}-${r.message.slice(0, 20)}`} columns={columns}
          dataSource={report?.issues ?? []} loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }} size="small"
        />
      )}
    </div>
  );
}
