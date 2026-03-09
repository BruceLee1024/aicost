import { useEffect, useState } from "react";
import {
  Button, Card, Collapse, Form, Input, InputNumber, Popconfirm,
  Select, Space, Table, Tag, Upload, message,
} from "antd";
import {
  ApiOutlined, DeleteOutlined, PlusOutlined, SettingOutlined,
  TeamOutlined, UploadOutlined,
} from "@ant-design/icons";
import type {
  MaterialPrice, MaterialPriceQuery,
  MeasureItem, Member, RulePackage,
} from "../api";
import { api } from "../api";

interface Props { projectId: number }

export default function SettingsTab({ projectId }: Props) {
  // Rule packages
  const [rulePackages, setRulePackages] = useState<RulePackage[]>([]);
  const [rpForm] = Form.useForm();
  const [rpOpen, setRpOpen] = useState(false);

  // Material prices
  const [materials, setMaterials] = useState<MaterialPrice[]>([]);
  const [mpForm] = Form.useForm();
  const [mpOpen, setMpOpen] = useState(false);
  const [mpFilterRegion, setMpFilterRegion] = useState("");
  const [mpFilterName, setMpFilterName] = useState("");
  const [mpFilterDate, setMpFilterDate] = useState("");
  const [mpLatestOnly, setMpLatestOnly] = useState(false);

  // Measures
  const [measures, setMeasures] = useState<MeasureItem[]>([]);
  const [msForm] = Form.useForm();
  const [msOpen, setMsOpen] = useState(false);

  // Members
  const [members, setMembers] = useState<Member[]>([]);
  const [memberName, setMemberName] = useState("");
  const [memberRole, setMemberRole] = useState("viewer");

  const buildMaterialQuery = (): MaterialPriceQuery => ({
    region: mpFilterRegion.trim() || undefined,
    name: mpFilterName.trim() || undefined,
    as_of_date: mpFilterDate.trim() || undefined,
    latest_only: mpLatestOnly || undefined,
  });

  const loadMaterials = async (query?: MaterialPriceQuery) => {
    try {
      setMaterials(await api.listMaterialPrices(query ?? buildMaterialQuery()));
    } catch {
      message.error("加载材料价格失败");
    }
  };

  useEffect(() => {
    api.listRulePackages().then(setRulePackages).catch(() => {});
    loadMaterials({});
    api.listMeasures(projectId).then(setMeasures).catch(() => {});
    api.listMembers(projectId).then(setMembers).catch(() => {});
  }, [projectId]);

  // Rule packages
  const handleCreateRp = async () => {
    try {
      const v = await rpForm.validateFields();
      await api.createRulePackage(v);
      message.success("规则包已创建");
      rpForm.resetFields(); setRpOpen(false);
      setRulePackages(await api.listRulePackages());
    } catch { message.error("创建失败"); }
  };

  const handleSearchMaterials = async () => {
    await loadMaterials();
  };

  const handleResetMaterialFilters = async () => {
    setMpFilterRegion("");
    setMpFilterName("");
    setMpFilterDate("");
    setMpLatestOnly(false);
    await loadMaterials({});
  };

  const handleBindRp = async (rpId: number) => {
    try {
      await api.bindRulePackage(projectId, rpId);
      message.success("规则包已绑定到项目");
    } catch { message.error("绑定失败"); }
  };

  // Material prices
  const handleCreateMp = async () => {
    try {
      const v = await mpForm.validateFields();
      if (!v.effective_date) v.effective_date = new Date().toISOString().slice(0, 10);
      await api.createMaterialPrice(v);
      message.success("材料价格已创建");
      mpForm.resetFields(); setMpOpen(false);
      await loadMaterials();
    } catch { message.error("创建失败"); }
  };

  // Import quota
  const handleImportQuota = async (file: File) => {
    try {
      const res = await api.importQuota(file);
      message.success(`导入定额成功：${res.imported} 条`);
    } catch { message.error("导入失败"); }
    return false;
  };

  // Measures
  const handleCreateMs = async () => {
    try {
      const v = await msForm.validateFields();
      await api.createMeasure(projectId, v);
      message.success("措施项已创建");
      msForm.resetFields(); setMsOpen(false);
      setMeasures(await api.listMeasures(projectId));
    } catch { message.error("创建失败"); }
  };

  const handleDeleteMs = async (id: number) => {
    try {
      await api.deleteMeasure(projectId, id);
      message.success("已删除");
      setMeasures(await api.listMeasures(projectId));
    } catch { message.error("删除失败"); }
  };

  // Members
  const handleAddMember = async () => {
    if (!memberName.trim()) return;
    try {
      await api.addMember(projectId, memberName.trim(), memberRole);
      message.success("成员已添加");
      setMemberName("");
      setMembers(await api.listMembers(projectId));
    } catch { message.error("添加失败"); }
  };

  const collapseItems = [
    {
      key: "rp",
      label: <span><SettingOutlined /> 规则包管理</span>,
      children: (
        <div>
          <Space style={{ marginBottom: 12 }}>
            <Button size="small" icon={<PlusOutlined />} onClick={() => setRpOpen(!rpOpen)}>新建规则包</Button>
            <Upload accept=".xlsx,.xls" showUploadList={false}
              beforeUpload={(f) => { handleImportQuota(f as File); return false; }}>
              <Button size="small" icon={<UploadOutlined />}>导入定额库</Button>
            </Upload>
          </Space>
          {rpOpen && (
            <Card size="small" style={{ marginBottom: 12 }}>
              <Form form={rpForm} layout="inline" size="small">
                <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="名称" /></Form.Item>
                <Form.Item name="region"><Input placeholder="地区" style={{ width: 80 }} /></Form.Item>
                <Form.Item name="management_rate"><InputNumber placeholder="管理费率" style={{ width: 100 }} /></Form.Item>
                <Form.Item name="profit_rate"><InputNumber placeholder="利润率" style={{ width: 100 }} /></Form.Item>
                <Form.Item name="tax_rate"><InputNumber placeholder="税率" style={{ width: 80 }} /></Form.Item>
                <Button type="primary" size="small" onClick={handleCreateRp}>创建</Button>
              </Form>
            </Card>
          )}
          <Table rowKey="id" size="small" pagination={false} dataSource={rulePackages} columns={[
            { title: "名称", dataIndex: "name" },
            { title: "地区", dataIndex: "region", width: 80 },
            { title: "管理费率", dataIndex: "management_rate", width: 90 },
            { title: "利润率", dataIndex: "profit_rate", width: 80 },
            { title: "税率", dataIndex: "tax_rate", width: 70 },
            {
              title: "操作", width: 100,
              render: (_: unknown, r: RulePackage) => (
                <Button size="small" type="link" onClick={() => handleBindRp(r.id)}>绑定到项目</Button>
              ),
            },
          ]} />
        </div>
      ),
    },
    {
      key: "mp",
      label: <span>材料价格管理</span>,
      forceRender: true,
      children: (
        <div>
          <Space style={{ marginBottom: 12 }} wrap>
            <Input
              placeholder="地区（如 sh / bj）"
              value={mpFilterRegion}
              onChange={(e) => setMpFilterRegion(e.target.value)}
              style={{ width: 140 }}
            />
            <Input
              placeholder="价格名称（人工费/材料费/机械费）"
              value={mpFilterName}
              onChange={(e) => setMpFilterName(e.target.value)}
              style={{ width: 220 }}
            />
            <Input
              placeholder="截至日期 YYYY-MM-DD"
              value={mpFilterDate}
              onChange={(e) => setMpFilterDate(e.target.value)}
              style={{ width: 170 }}
            />
            <Select
              value={mpLatestOnly ? "latest" : "all"}
              onChange={(v) => setMpLatestOnly(v === "latest")}
              style={{ width: 120 }}
              options={[
                { label: "全部版本", value: "all" },
                { label: "仅最新", value: "latest" },
              ]}
            />
            <Button size="small" onClick={handleSearchMaterials}>筛选</Button>
            <Button size="small" onClick={handleResetMaterialFilters}>重置</Button>
          </Space>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setMpOpen(!mpOpen)} style={{ marginBottom: 12 }}>
            新增材料价格
          </Button>
          {mpOpen && (
            <Card size="small" style={{ marginBottom: 12 }}>
              <Form form={mpForm} layout="inline" size="small">
                <Form.Item name="code" rules={[{ required: true }]}><Input placeholder="编码" style={{ width: 100 }} /></Form.Item>
                <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="名称" /></Form.Item>
                <Form.Item name="unit" rules={[{ required: true }]}><Input placeholder="单位" style={{ width: 60 }} /></Form.Item>
                <Form.Item name="unit_price" rules={[{ required: true }]}><InputNumber placeholder="单价" style={{ width: 100 }} /></Form.Item>
                <Form.Item name="region"><Input placeholder="地区" style={{ width: 80 }} /></Form.Item>
                <Form.Item
                  name="effective_date"
                  rules={[{ pattern: /^\d{4}-\d{2}-\d{2}$/, message: "格式 YYYY-MM-DD" }]}
                >
                  <Input placeholder="生效日期 YYYY-MM-DD" style={{ width: 170 }} />
                </Form.Item>
                <Form.Item name="spec"><Input placeholder="规格" style={{ width: 100 }} /></Form.Item>
                <Button type="primary" size="small" onClick={handleCreateMp}>创建</Button>
              </Form>
            </Card>
          )}
          <Table rowKey="id" size="small" dataSource={materials}
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
            columns={[
              { title: "编码", dataIndex: "code", width: 100 },
              { title: "名称", dataIndex: "name" },
              { title: "规格", dataIndex: "spec", width: 100 },
              { title: "单位", dataIndex: "unit", width: 60 },
              { title: "单价", dataIndex: "unit_price", width: 80 },
              { title: "地区", dataIndex: "region", width: 80, render: (v: string) => v || "全局" },
              { title: "生效日期", dataIndex: "effective_date", width: 120 },
              { title: "来源", dataIndex: "source", width: 90 },
          ]} />
        </div>
      ),
    },
    {
      key: "ms",
      label: <span>措施项管理</span>,
      children: (
        <div>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setMsOpen(!msOpen)} style={{ marginBottom: 12 }}>
            新增措施项
          </Button>
          {msOpen && (
            <Card size="small" style={{ marginBottom: 12 }}>
              <Form form={msForm} layout="inline" size="small">
                <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="名称" /></Form.Item>
                <Form.Item name="calc_base" initialValue="direct">
                  <Select style={{ width: 100 }} options={[
                    { label: "直接费", value: "direct" },
                    { label: "税前", value: "pre_tax" },
                  ]} />
                </Form.Item>
                <Form.Item name="rate"><InputNumber placeholder="费率" style={{ width: 80 }} /></Form.Item>
                <Form.Item name="amount"><InputNumber placeholder="固定金额" style={{ width: 100 }} /></Form.Item>
                <Button type="primary" size="small" onClick={handleCreateMs}>创建</Button>
              </Form>
            </Card>
          )}
          <Table rowKey="id" size="small" pagination={false} dataSource={measures} columns={[
            { title: "名称", dataIndex: "name" },
            { title: "计算基数", dataIndex: "calc_base", width: 90 },
            { title: "费率", dataIndex: "rate", width: 80 },
            { title: "固定金额", dataIndex: "amount", width: 100 },
            { title: "类型", dataIndex: "is_fixed", width: 80, render: (v: boolean) => v ? <Tag>固定</Tag> : <Tag color="blue">比率</Tag> },
            {
              title: "操作", width: 80,
              render: (_: unknown, r: MeasureItem) => (
                <Popconfirm title="确认删除？" onConfirm={() => handleDeleteMs(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]} />
        </div>
      ),
    },
    {
      key: "members",
      label: <span><TeamOutlined /> 项目成员</span>,
      children: (
        <div>
          <Space style={{ marginBottom: 12 }}>
            <Input placeholder="用户名" value={memberName} onChange={(e) => setMemberName(e.target.value)} style={{ width: 140 }} />
            <Select value={memberRole} onChange={setMemberRole} style={{ width: 100 }} options={[
              { label: "管理员", value: "owner" },
              { label: "编辑", value: "editor" },
              { label: "查看", value: "viewer" },
            ]} />
            <Button type="primary" size="small" onClick={handleAddMember}>添加</Button>
          </Space>
          <Table rowKey="id" size="small" pagination={false} dataSource={members} columns={[
            { title: "用户", dataIndex: "user_name" },
            {
              title: "角色", dataIndex: "role", width: 100,
              render: (r: string) => {
                const c: Record<string, string> = { owner: "red", editor: "blue", viewer: "default" };
                const l: Record<string, string> = { owner: "管理员", editor: "编辑", viewer: "查看" };
                return <Tag color={c[r]}>{l[r] ?? r}</Tag>;
              },
            },
          ]} />
        </div>
      ),
    },
  ];

  const aiCollapseItem = {
    key: "ai",
    label: <span><ApiOutlined /> AI 模型配置</span>,
    children: (
      <div style={{ padding: "8px 0" }}>
        <p style={{ color: "var(--text-secondary)", marginBottom: 12 }}>
          AI 模型配置已移至系统设置页面，支持配置 DeepSeek、通义千问、Kimi、智谱 GLM 等供应商。
        </p>
        <Button type="primary" icon={<ApiOutlined />} onClick={() => { window.location.href = "/settings"; }}>
          前往系统设置
        </Button>
      </div>
    ),
  };

  return <Collapse items={[aiCollapseItem, ...collapseItems]} defaultActiveKey={["rp"]} />;
}
