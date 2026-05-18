import { useCallback, useEffect, useState } from "react";
import {
  Button, Col, Divider, Form, Input, InputNumber, Modal,
  Row, Select, Space, Spin, Statistic, Table, Tag, Tooltip, message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import type {
  OtherItem, OtherItemCategory, OtherItemCreate, OtherItemSummary, RegulatoryFees,
} from "../api";
import { api, OTHER_ITEM_CATEGORY_ZH } from "../api";

const CATEGORIES: OtherItemCategory[] = [
  "provisional_sum", "provisional_price", "daywork", "gc_service",
];

const CATEGORY_COLOR: Record<OtherItemCategory, string> = {
  provisional_sum: "blue",
  provisional_price: "cyan",
  daywork: "orange",
  gc_service: "purple",
};

const CATEGORY_ICON: Record<OtherItemCategory, string> = {
  provisional_sum: "savings",
  provisional_price: "price_change",
  daywork: "engineering",
  gc_service: "handshake",
};

interface Props { projectId: number }

export default function OtherItemsTab({ projectId }: Props) {
  const [items, setItems] = useState<OtherItem[]>([]);
  const [summary, setSummary] = useState<OtherItemSummary | null>(null);
  const [regFees, setRegFees] = useState<RegulatoryFees | null>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OtherItem | null>(null);
  const [filterCat, setFilterCat] = useState<OtherItemCategory | "">("");
  const [form] = Form.useForm<OtherItemCreate & { is_fixed: number }>();
  const isFixed = Form.useWatch("is_fixed", form);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [its, sum, reg] = await Promise.all([
        api.listOtherItems(projectId, filterCat || undefined),
        api.getOtherItemsSummary(projectId),
        api.getRegulatoryFees(projectId),
      ]);
      setItems(its);
      setSummary(sum);
      setRegFees(reg);
    } catch {
      message.error("加载其他项目费数据失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, filterCat]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const openAdd = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ category: "provisional_sum", is_fixed: 1, quantity: 1, unit_price: 0, amount: 0 });
    setModalOpen(true);
  };

  const openEdit = (row: OtherItem) => {
    setEditing(row);
    form.setFieldsValue({ ...row });
    setModalOpen(true);
  };

  const handleDelete = async (row: OtherItem) => {
    try {
      await api.deleteOtherItem(projectId, row.id);
      message.success("已删除");
      loadAll();
    } catch {
      message.error("删除失败");
    }
  };

  const handleSubmit = async () => {
    try {
      const vals = await form.validateFields();
      if (editing) {
        await api.updateOtherItem(projectId, editing.id, vals);
        message.success("已更新");
      } else {
        await api.createOtherItem(projectId, vals);
        message.success("已添加");
      }
      setModalOpen(false);
      loadAll();
    } catch {
      message.error("保存失败");
    }
  };

  const fmt = (n: number) =>
    n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const columns: ColumnsType<OtherItem> = [
    {
      title: "类别",
      dataIndex: "category",
      width: 110,
      render: (v: OtherItemCategory) => (
        <Tag color={CATEGORY_COLOR[v]}>{OTHER_ITEM_CATEGORY_ZH[v]}</Tag>
      ),
    },
    { title: "名称", dataIndex: "name", ellipsis: true },
    { title: "单位", dataIndex: "unit", width: 60, render: v => v || "—" },
    {
      title: "数量",
      dataIndex: "quantity",
      width: 80,
      align: "right",
      render: (v, r) => r.is_fixed ? "—" : v,
    },
    {
      title: "单价",
      dataIndex: "unit_price",
      width: 100,
      align: "right",
      render: (v, r) => r.is_fixed ? "—" : fmt(v),
    },
    {
      title: "金额（元）",
      dataIndex: "amount",
      width: 130,
      align: "right",
      render: (v) => <span style={{ fontVariantNumeric: "tabular-nums" }}>¥{fmt(v)}</span>,
    },
    { title: "备注", dataIndex: "note", ellipsis: true, render: v => v || "—" },
    {
      title: "操作",
      width: 80,
      align: "center",
      render: (_, row) => (
        <Space size={4}>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(row)} />
          </Tooltip>
          <Tooltip title="删除">
            <Button
              type="text" size="small" danger icon={<DeleteOutlined />}
              onClick={() => Modal.confirm({
                title: `确认删除「${row.name}」？`,
                onOk: () => handleDelete(row),
              })}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: "0 4px" }}>
      {/* ─── 汇总统计 ─── */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        {CATEGORIES.map((cat) => {
          const s = summary?.categories.find(c => c.category === cat);
          return (
            <Col key={cat} span={6}>
              <div className="mini-stat-card">
                <div className="mini-stat-card-head">
                  <Tag color={CATEGORY_COLOR[cat]} style={{ margin: 0 }}>
                    {OTHER_ITEM_CATEGORY_ZH[cat]}
                  </Tag>
                  <div className={`mini-stat-card-icon ${CATEGORY_COLOR[cat]}`}>
                    <span className="material-symbols-outlined">{CATEGORY_ICON[cat]}</span>
                  </div>
                </div>
                <div className="mini-stat-card-value">
                  ¥{fmt(s?.total ?? 0)}
                </div>
                <div className="mini-stat-card-label">
                  {s?.count ?? 0} 条明细
                </div>
              </div>
            </Col>
          );
        })}
      </Row>

      {/* ─── 规费明细 ─── */}
      {regFees && (
        <div className="reg-fees-panel" style={{ marginBottom: 20 }}>
          <div className="reg-fees-head">
            <div className="reg-fees-head-icon">
              <span className="material-symbols-outlined">account_balance</span>
            </div>
            <span className="reg-fees-title">规费明细</span>
            <span className="reg-fees-base">
              人工费合计 <strong>¥{fmt(regFees.labor_base)}</strong> 为计算基础
            </span>
          </div>
          <Row gutter={32}>
            <Col>
              <Statistic
                title={`社会保险费（费率 ${(regFees.social_insurance_rate * 100).toFixed(1)}%）`}
                value={regFees.social_insurance_fee}
                precision={2}
                prefix="¥"
                valueStyle={{ fontSize: 18 }}
              />
            </Col>
            <Col>
              <Statistic
                title={`住房公积金（费率 ${(regFees.housing_fund_rate * 100).toFixed(1)}%）`}
                value={regFees.housing_fund_fee}
                precision={2}
                prefix="¥"
                valueStyle={{ fontSize: 18 }}
              />
            </Col>
            <Col>
              <Divider type="vertical" style={{ height: "100%", marginRight: 16 }} />
              <Statistic
                title="规费合计"
                value={regFees.regulatory_fee_total}
                precision={2}
                prefix="¥"
                valueStyle={{ fontSize: 20, fontWeight: 700, color: "var(--primary)" }}
              />
            </Col>
          </Row>
        </div>
      )}

      {/* ─── 工具栏 ─── */}
      <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
        <Select
          allowClear
          placeholder="按类别筛选"
          style={{ width: 140 }}
          value={filterCat || undefined}
          onChange={(v) => setFilterCat(v ?? "")}
          options={CATEGORIES.map(c => ({ value: c, label: OTHER_ITEM_CATEGORY_ZH[c] }))}
        />
        <div style={{ flex: 1 }} />
        <Button icon={<ReloadOutlined />} onClick={loadAll}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>新增条目</Button>
      </div>

      {/* ─── 列表 ─── */}
      <Spin spinning={loading}>
        <Table<OtherItem>
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={items}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          locale={{ emptyText: "暂无其他项目费条目，点击「新增条目」添加" }}
          summary={(pageData) => {
            const total = pageData.reduce((s, r) => s + r.amount, 0);
            return (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={5}>
                  <span style={{ fontWeight: 600, paddingLeft: 8 }}>本页合计</span>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right">
                  <span style={{ fontWeight: 700 }}>¥{fmt(total)}</span>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={6} colSpan={2} />
              </Table.Summary.Row>
            );
          }}
        />
      </Spin>

      {/* ─── 总计 ─── */}
      {summary && (
        <div className="other-items-total">
          <span className="other-items-total-label">其他项目费合计</span>
          <span className="other-items-total-value">¥{fmt(summary.grand_total)}</span>
        </div>
      )}

      {/* ─── 新增 / 编辑 Modal ─── */}
      <Modal
        title={editing ? "编辑其他项目费" : "新增其他项目费"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        width={520}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="类别" rules={[{ required: true }]}>
                <Select options={CATEGORIES.map(c => ({ value: c, label: OTHER_ITEM_CATEGORY_ZH[c] }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_fixed" label="金额类型" rules={[{ required: true }]}>
                <Select options={[
                  { value: 1, label: "固定金额" },
                  { value: 0, label: "数量×单价" },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="如：暂列金额、计日工-普工" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="unit" label="单位">
                <Input placeholder="项、元" />
              </Form.Item>
            </Col>
            {isFixed === 0 ? (
              <>
                <Col span={8}>
                  <Form.Item name="quantity" label="数量">
                    <InputNumber style={{ width: "100%" }} min={0} precision={4} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="unit_price" label="单价（元）">
                    <InputNumber style={{ width: "100%" }} min={0} precision={2} />
                  </Form.Item>
                </Col>
              </>
            ) : (
              <Col span={16}>
                <Form.Item name="amount" label="金额（元）" rules={[{ required: true }]}>
                  <InputNumber style={{ width: "100%" }} min={0} precision={2} />
                </Form.Item>
              </Col>
            )}
          </Row>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} placeholder="可选备注" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
