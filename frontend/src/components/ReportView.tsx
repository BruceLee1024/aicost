import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  message,
  Progress,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Tooltip,
} from "antd";
import { BizTable } from "./BizTable";
import {
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  ReloadOutlined,
  PieChartOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { api } from "../api";

interface Props {
  projectId: number;
}

const COST_COLORS = [
  "#1677ff", "#52c41a", "#faad14", "#ff4d4f",
  "#722ed1", "#13c2c2", "#eb2f96", "#fa8c16",
];

export default function ReportView({ projectId }: Props) {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [exporting, setExporting] = useState(false);
  const [filterDivision, setFilterDivision] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");

  const load = async (div?: string, kw?: string) => {
    setLoading(true);
    try {
      const data = await api.getReport(projectId, {
        division: div,
        search: kw || undefined,
      });
      setReport(data);
    } catch (e: any) {
      message.error("加载报告失败: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [projectId]);

  const handleFilter = () => load(filterDivision, searchText);

  const handleExport = async (
    format: "pdf" | "excel" | "docx",
    opts?: { narrative?: boolean },
  ) => {
    setExporting(true);
    try {
      const blob = await api.exportReport(projectId, format, opts);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext =
        format === "excel" ? "xlsx" : format === "docx" ? "docx" : "pdf";
      a.download = `report_${projectId}.${ext}`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success(`${format.toUpperCase()} 导出成功`);
    } catch (e: any) {
      message.error("导出失败: " + e.message);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Spin size="large" />
        <div style={{ marginTop: 12, color: "var(--text-muted)" }}>加载报告...</div>
      </div>
    );
  }

  if (!report) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Empty description="暂无报告数据，请先添加清单项并执行计算" />
      </div>
    );
  }

  const { project, statistics, cost_summary, divisions, line_items } = report;

  // No items — show guidance
  if (statistics.total_items === 0) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Empty description="该项目暂无清单数据">
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
            请先在「智能开项」页面生成清单，或在「清单树」页面手动添加清单项
          </p>
        </Empty>
      </div>
    );
  }

  const bindingPct = statistics.total_items > 0
    ? Math.round((statistics.bound_count / statistics.total_items) * 100)
    : 0;

  const divisionColumns = [
    { title: "分部工程", dataIndex: "division", key: "division" },
    { title: "清单数", dataIndex: "item_count", key: "item_count", align: "right" as const },
    { title: "已绑定", dataIndex: "bound_count", key: "bound_count", align: "right" as const },
    {
      title: "合计金额",
      dataIndex: "total_cost",
      key: "total_cost",
      align: "right" as const,
      render: (v: number) => `¥${v?.toLocaleString() ?? "—"}`,
    },
    {
      title: "占比",
      dataIndex: "percentage",
      key: "percentage",
      width: 160,
      render: (pct: string, _: any, idx: number) => {
        const num = parseFloat(pct) || 0;
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{
              flex: 1, height: 6, borderRadius: 3,
              background: "rgba(255,255,255,0.06)", overflow: "hidden",
            }}>
              <div style={{
                width: `${num}%`, height: "100%", borderRadius: 3,
                background: COST_COLORS[idx % COST_COLORS.length],
              }} />
            </div>
            <span style={{ fontSize: 12, minWidth: 40 }}>{pct}</span>
          </div>
        );
      },
    },
  ];

  const lineColumns = [
    { title: "编码", dataIndex: "code", key: "code", width: 120 },
    { title: "名称", dataIndex: "name", key: "name", ellipsis: true },
    { title: "单位", dataIndex: "unit", key: "unit", width: 60, align: "center" as const },
    {
      title: "工程量",
      dataIndex: "quantity",
      key: "quantity",
      width: 90,
      align: "right" as const,
      render: (v: number) => v?.toLocaleString(),
    },
    {
      title: "综合单价",
      dataIndex: "unit_price",
      key: "unit_price",
      width: 100,
      align: "right" as const,
      render: (v: number | null) => (v != null ? `¥${v.toLocaleString()}` : "—"),
    },
    {
      title: "合价",
      dataIndex: "total_cost",
      key: "total_cost",
      width: 110,
      align: "right" as const,
      render: (v: number | null) => (v != null ? `¥${v.toLocaleString()}` : "—"),
    },
    {
      title: "状态",
      dataIndex: "is_bound",
      key: "status",
      width: 80,
      align: "center" as const,
      render: (bound: boolean) =>
        bound ? <Tag color="green">已绑定</Tag> : <Tag color="orange">未绑定</Tag>,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Space>
          <span style={{ fontSize: 16, fontWeight: 600 }}>
            计价报告 — {project.name}
          </span>
          <Tag>{project.standard_type}</Tag>
          <Tag>{project.region}</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => load(filterDivision, searchText)}>
            刷新
          </Button>
          <Button
            icon={<FileExcelOutlined />}
            loading={exporting}
            onClick={() => handleExport("excel")}
          >
            导出 Excel
          </Button>
          <Button
            icon={<FileWordOutlined />}
            loading={exporting}
            onClick={() => handleExport("docx")}
          >
            导出 Word
          </Button>
          <Tooltip title="导出 Word 并附 AI 生成的执行摘要、分部分析、风险与建议（Sprint 9）">
            <Button
              icon={<FileWordOutlined />}
              loading={exporting}
              onClick={() => handleExport("docx", { narrative: true })}
            >
              Word + AI 摘要
            </Button>
          </Tooltip>
          <Button
            type="primary"
            icon={<FilePdfOutlined />}
            loading={exporting}
            onClick={() => handleExport("pdf")}
          >
            导出 PDF
          </Button>
        </Space>
      </div>

      {/* Cost Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Card size="small">
          <Statistic
            title="工程总价"
            value={cost_summary.grand_total}
            prefix="¥"
            precision={2}
            valueStyle={{ color: "var(--primary)", fontWeight: 700, fontSize: 20 }}
          />
        </Card>
        <Card size="small">
          <Statistic title="直接费" value={cost_summary.total_direct} prefix="¥" precision={2} />
        </Card>
        <Card size="small">
          <Statistic title="管理费 + 利润" value={(cost_summary.total_management || 0) + (cost_summary.total_profit || 0)} prefix="¥" precision={2} />
        </Card>
        <Card size="small">
          <Statistic title="税金" value={cost_summary.total_tax} prefix="¥" precision={2} />
        </Card>
      </div>

      {/* Statistics + Binding Progress */}
      <Card size="small" title="项目统计">
        <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="清单总数">{statistics.total_items}</Descriptions.Item>
              <Descriptions.Item label="已计算">{statistics.calculated_items}</Descriptions.Item>
              <Descriptions.Item label="已绑定">{statistics.bound_count}</Descriptions.Item>
              <Descriptions.Item label="未绑定">{statistics.unbound_count}</Descriptions.Item>
            </Descriptions>
          </div>
          <div style={{ width: 120, textAlign: "center" }}>
            <Tooltip title={`绑定率: ${statistics.binding_rate}`}>
              <Progress
                type="circle"
                percent={bindingPct}
                size={80}
                strokeColor={bindingPct === 100 ? "#52c41a" : bindingPct > 60 ? "#1677ff" : "#faad14"}
                format={(pct) => `${pct}%`}
              />
            </Tooltip>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>绑定率</div>
          </div>
        </div>
      </Card>

      {/* Division Breakdown with visual bars */}
      <Card
        size="small"
        title={
          <Space>
            <PieChartOutlined />
            <span>分部工程汇总</span>
            <Tag color="blue">{divisions.length} 个分部</Tag>
          </Space>
        }
      >
        <BizTable
          dataSource={divisions}
          columns={divisionColumns}
          rowKey="division"
          pagination={false}
        />
      </Card>

      {/* Line Items with filter/search */}
      <Card
        size="small"
        title={`分部分项工程计价表 (${line_items.length} 项)`}
        extra={
          <Space size={8}>
            <Select
              allowClear
              placeholder="按分部筛选"
              style={{ width: 150 }}
              value={filterDivision}
              onChange={(v) => { setFilterDivision(v); load(v, searchText); }}
              options={divisions.map((d: any) => ({ label: d.division, value: d.division }))}
            />
            <Input
              allowClear
              placeholder="搜索名称/编码"
              prefix={<SearchOutlined />}
              style={{ width: 160 }}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onPressEnter={handleFilter}
            />
          </Space>
        }
      >
        <BizTable
          showIndex
          dataSource={line_items}
          columns={lineColumns}
          rowKey="boq_item_id"
          pagination={{ pageSize: 20, showTotal: (t: number) => `共 ${t} 项` }}
          scroll={{ x: 800 }}
        />
      </Card>
    </div>
  );
}
