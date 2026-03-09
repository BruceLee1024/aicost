import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Steps,
  Table,
  Tabs,
  Tag,
  message,
} from "antd";
import type {
  BoqItem,
  ContractMeasurement,
  ContractMeasurementCreate,
  PaymentCertificate,
  PaymentCertificateCreate,
  PriceAdjustment,
  PriceAdjustmentCreate,
  Project,
  ValuationOverview,
} from "../api";
import { api } from "../api";
import PageBreadcrumb from "../components/PageBreadcrumb";

const STANDARD_OPTIONS = [
  { label: "GB/T50500-2024", value: "GB/T50500-2024" },
];

export default function PricingManagement() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>(undefined);
  const [boqItems, setBoqItems] = useState<BoqItem[]>([]);
  const [overview, setOverview] = useState<ValuationOverview | null>(null);
  const [measurements, setMeasurements] = useState<ContractMeasurement[]>([]);
  const [adjustments, setAdjustments] = useState<PriceAdjustment[]>([]);
  const [payments, setPayments] = useState<PaymentCertificate[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);

  const [measurementOpen, setMeasurementOpen] = useState(false);
  const [adjustmentOpen, setAdjustmentOpen] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [measurementForm] = Form.useForm();
  const [adjustmentForm] = Form.useForm();
  const [paymentForm] = Form.useForm();

  const loadProjects = async () => {
    try {
      const rows = await api.listProjects();
      setProjects(rows);
      if (!projectId && rows.length > 0) {
        setProjectId(rows[0].id);
      }
    } catch {
      message.error("加载项目失败");
    }
  };

  const loadProjectData = async (pid: number) => {
    setLoading(true);
    try {
      const [ov, ms, ads, pcs, boqs] = await Promise.all([
        api.getValuationOverview(pid),
        api.listContractMeasurements(pid),
        api.listPriceAdjustments(pid),
        api.listPaymentCertificates(pid),
        api.listBoqItems(pid),
      ]);
      setOverview(ov);
      setMeasurements(ms);
      setAdjustments(ads);
      setPayments(pcs);
      setBoqItems(boqs);
    } catch {
      message.error("加载计价管理数据失败");
    }
    setLoading(false);
  };

  useEffect(() => { loadProjects(); }, []);
  useEffect(() => {
    if (projectId) loadProjectData(projectId);
  }, [projectId]);

  const boqOptions = useMemo(
    () => boqItems.map((b) => ({ label: `[${b.code}] ${b.name}`, value: b.id })),
    [boqItems],
  );

  const saveStandard = async () => {
    if (!projectId || !overview) return;
    setSavingStandard(true);
    try {
      await api.updateValuationConfig(projectId, {
        standard_code: overview.standard.standard_code,
        standard_name: overview.standard.standard_name,
        effective_date: overview.standard.effective_date,
        lock_standard: true,
      });
      message.success("计价标准已锁定");
      await loadProjectData(projectId);
    } catch (e) {
      message.error("标准锁定失败");
    }
    setSavingStandard(false);
  };

  const createMeasurement = async () => {
    if (!projectId) return;
    try {
      const values = await measurementForm.validateFields();
      await api.createContractMeasurement(projectId, values as ContractMeasurementCreate);
      message.success("合同计量已新增");
      measurementForm.resetFields();
      setMeasurementOpen(false);
      await loadProjectData(projectId);
    } catch {
      message.error("新增合同计量失败");
    }
  };

  const approveMeasurement = async (measurementId: number) => {
    if (!projectId) return;
    try {
      await api.approveContractMeasurement(projectId, measurementId, "审核人");
      message.success("计量已签认");
      await loadProjectData(projectId);
    } catch {
      message.error("签认失败");
    }
  };

  const createAdjustment = async () => {
    if (!projectId) return;
    try {
      const values = await adjustmentForm.validateFields();
      await api.createPriceAdjustment(projectId, values as PriceAdjustmentCreate);
      message.success("价款调整单已新增");
      adjustmentForm.resetFields();
      setAdjustmentOpen(false);
      await loadProjectData(projectId);
    } catch {
      message.error("新增调整单失败");
    }
  };

  const createPayment = async () => {
    if (!projectId) return;
    try {
      const values = await paymentForm.validateFields();
      await api.createPaymentCertificate(projectId, values as PaymentCertificateCreate);
      message.success("支付证书已新增");
      paymentForm.resetFields();
      setPaymentOpen(false);
      await loadProjectData(projectId);
    } catch {
      message.error("新增支付证书失败");
    }
  };

  const measurementColumns = [
    { title: "期间", dataIndex: "period_label", width: 110 },
    { title: "清单编码", dataIndex: "boq_code", width: 100 },
    { title: "清单名称", dataIndex: "boq_name" },
    { title: "本期计量", dataIndex: "measured_qty", width: 90 },
    { title: "累计计量", dataIndex: "cumulative_qty", width: 90 },
    { title: "状态", dataIndex: "status", width: 90, render: (v: string) => <Tag color={v === "approved" ? "green" : "orange"}>{v}</Tag> },
    {
      title: "操作",
      width: 100,
      render: (_: unknown, r: ContractMeasurement) =>
        r.status === "approved"
          ? <span style={{ color: "var(--text-secondary)" }}>已签认</span>
          : <Button size="small" onClick={() => approveMeasurement(r.id)}>签认</Button>,
    },
  ];

  const adjustmentColumns = [
    { title: "类型", dataIndex: "adjustment_type", width: 150 },
    { title: "关联清单", dataIndex: "boq_code", width: 100, render: (v: string) => v || "-" },
    { title: "说明", dataIndex: "reason" },
    { title: "金额", dataIndex: "amount", width: 120, render: (v: number) => `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}` },
    { title: "状态", dataIndex: "status", width: 100, render: (v: string) => <Tag>{v}</Tag> },
  ];

  const paymentColumns = [
    { title: "期间", dataIndex: "period_label", width: 120 },
    { title: "应付总额", dataIndex: "gross_amount", width: 120 },
    { title: "预付款扣回", dataIndex: "prepayment_deduction", width: 120 },
    { title: "质保金", dataIndex: "retention", width: 100 },
    { title: "净支付额", dataIndex: "net_payable", width: 120, render: (v: number) => <strong>¥{v.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</strong> },
    { title: "已支付", dataIndex: "paid_amount", width: 100 },
    { title: "状态", dataIndex: "status", width: 90, render: (v: string) => <Tag>{v}</Tag> },
  ];

  return (
    <div className="page-container" style={{ padding: 24 }}>
      <PageBreadcrumb items={[
        { label: "控制面板", path: "/dashboard" },
        { label: "计价管理" },
      ]} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0 }}>计价管理</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>基于新清单规范的计价业务闭环（2024版）</p>
        </div>
        <Space>
          <span style={{ color: "var(--text-secondary)" }}>项目</span>
          <Select
            style={{ width: 280 }}
            value={projectId}
            options={projects.map((p) => ({ label: `${p.name}（${p.region}）`, value: p.id }))}
            onChange={(v) => setProjectId(v)}
            placeholder="请选择项目"
          />
        </Space>
      </div>

      <Card loading={loading} style={{ marginBottom: 16 }}>
        {overview && (
          <>
            <Descriptions column={4} size="small">
              <Descriptions.Item label="计价标准">
                <Select
                  value={overview.standard.standard_code}
                  options={STANDARD_OPTIONS}
                  disabled={overview.standard.locked}
                  onChange={(v) => setOverview({
                    ...overview,
                    standard: { ...overview.standard, standard_code: v },
                  })}
                  style={{ width: 180 }}
                />
              </Descriptions.Item>
              <Descriptions.Item label="实施日期">{overview.standard.effective_date}</Descriptions.Item>
              <Descriptions.Item label="锁定状态">
                {overview.standard.locked ? <Tag color="green">已锁定</Tag> : <Tag color="orange">未锁定</Tag>}
              </Descriptions.Item>
              <Descriptions.Item>
                <Button type="primary" disabled={overview.standard.locked} loading={savingStandard} onClick={saveStandard}>
                  锁定项目口径
                </Button>
              </Descriptions.Item>
              <Descriptions.Item label="合同计量">{overview.measurement_count} 条</Descriptions.Item>
              <Descriptions.Item label="价款调整">¥{overview.adjustment_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</Descriptions.Item>
              <Descriptions.Item label="支付证书">{overview.payment_count} 份</Descriptions.Item>
              <Descriptions.Item label="净支付累计">¥{overview.payment_net_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 18 }}>
              <Steps
                size="small"
                items={overview.stages.map((s) => ({
                  title: s.label,
                  status: s.status === "done" ? "finish" : s.status === "in_progress" ? "process" : "wait",
                  subTitle: s.detail,
                }))}
              />
            </div>
          </>
        )}
      </Card>

      <Card loading={loading}>
        <Tabs
          items={[
            {
              key: "measurement",
              label: "合同计量",
              children: (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Button type="primary" onClick={() => setMeasurementOpen(true)}>新增计量</Button>
                  </div>
                  <Table rowKey="id" size="small" columns={measurementColumns} dataSource={measurements} pagination={{ pageSize: 8 }} />
                </>
              ),
            },
            {
              key: "adjustment",
              label: "价款调整",
              children: (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Button type="primary" onClick={() => setAdjustmentOpen(true)}>新增调整单</Button>
                  </div>
                  <Table rowKey="id" size="small" columns={adjustmentColumns} dataSource={adjustments} pagination={{ pageSize: 8 }} />
                </>
              ),
            },
            {
              key: "payment",
              label: "期中支付",
              children: (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Button type="primary" onClick={() => setPaymentOpen(true)}>新增支付证书</Button>
                  </div>
                  <Table rowKey="id" size="small" columns={paymentColumns} dataSource={payments} pagination={{ pageSize: 8 }} />
                </>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="新增合同计量" open={measurementOpen} onCancel={() => setMeasurementOpen(false)} onOk={createMeasurement}>
        <Form form={measurementForm} layout="vertical">
          <Form.Item name="period_label" label="计量期间" rules={[{ required: true }]}>
            <Input placeholder="如：2026-03" />
          </Form.Item>
          <Form.Item name="boq_item_id" label="清单项" rules={[{ required: true }]}>
            <Select options={boqOptions} showSearch optionFilterProp="label" />
          </Form.Item>
          <Form.Item name="measured_qty" label="本期计量工程量" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} min={0} />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="新增价款调整单" open={adjustmentOpen} onCancel={() => setAdjustmentOpen(false)} onOk={createAdjustment}>
        <Form form={adjustmentForm} layout="vertical" initialValues={{ adjustment_type: "change_order", status: "draft" }}>
          <Form.Item name="adjustment_type" label="调整类型" rules={[{ required: true }]}>
            <Select
              options={[
                { label: "设计变更", value: "design_change" },
                { label: "签证", value: "site_instruction" },
                { label: "材料价差", value: "material_price_change" },
                { label: "暂估价转实价", value: "provisional_to_actual" },
              ]}
            />
          </Form.Item>
          <Form.Item name="boq_item_id" label="关联清单项（可选）">
            <Select allowClear options={boqOptions} showSearch optionFilterProp="label" />
          </Form.Item>
          <Form.Item name="amount" label="调整金额" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select options={[{ label: "草稿", value: "draft" }, { label: "已确认", value: "approved" }]} />
          </Form.Item>
          <Form.Item name="reason" label="调整说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="新增支付证书" open={paymentOpen} onCancel={() => setPaymentOpen(false)} onOk={createPayment}>
        <Form form={paymentForm} layout="vertical" initialValues={{ prepayment_deduction: 0, retention: 0, paid_amount: 0, status: "issued" }}>
          <Form.Item name="period_label" label="支付期间" rules={[{ required: true }]}>
            <Input placeholder="如：2026-Q1" />
          </Form.Item>
          <Form.Item name="gross_amount" label="应付总额" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="prepayment_deduction" label="预付款扣回">
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="retention" label="质保金">
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="paid_amount" label="已支付金额">
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select options={[{ label: "已签发", value: "issued" }, { label: "已支付", value: "paid" }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

