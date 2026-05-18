/**
 * BoqDraftEditor — Sprint 9 Phase 2.1
 *
 * Editable preview of a BOQ draft proposed by the agent. The user can:
 *   - Tweak code / name / unit / quantity / division / characteristics
 *   - Delete rows
 *   - Add a blank row
 *   - Bulk-edit division for selected rows
 *   - Group/expand by division
 *   - Submit final list to commit endpoint
 *   - Discard the draft
 *
 * The agent returns a `draft_token` via the SSE stream (encoded inside the
 * `tool_result` of the `propose_boq_items` step). The parent component is
 * responsible for extracting that token and passing it here.
 */

import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Input,
  InputNumber,
  Modal,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import {
  CheckCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { api, type BoqDraftItem } from "../api";

interface Props {
  open: boolean;
  projectId: number;
  token: string | null;
  onClose: () => void;
  onCommitted?: (createdCount: number) => void;
}

interface EditableItem extends BoqDraftItem {
  _key: string;
  _dirty?: boolean;
  _new?: boolean;
}

function uid(): string {
  return `r${Math.random().toString(36).slice(2, 9)}`;
}

export default function BoqDraftEditor({
  open,
  projectId,
  token,
  onClose,
  onCommitted,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [items, setItems] = useState<EditableItem[]>([]);
  const [original, setOriginal] = useState<EditableItem[]>([]);
  const [error, setError] = useState<string>("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  // ── Load draft ────────────────────────────────────────────────
  useEffect(() => {
    if (!open || !token) return;
    setLoading(true);
    setError("");
    api
      .getBoqDraft(projectId, token)
      .then((draft) => {
        const editable: EditableItem[] = draft.items.map((it) => ({
          ...it,
          _key: it.draft_id || uid(),
        }));
        setItems(editable);
        setOriginal(editable);
      })
      .catch((e) => setError(e.message || "草稿加载失败"))
      .finally(() => setLoading(false));
  }, [open, token, projectId]);

  // ── Statistics ────────────────────────────────────────────────
  const stats = useMemo(() => {
    const byDivision: Record<string, number> = {};
    let totalQty = 0;
    for (const it of items) {
      const div = it.division || "未分类";
      byDivision[div] = (byDivision[div] || 0) + 1;
      totalQty += Number(it.quantity) || 0;
    }
    return {
      total: items.length,
      byDivision,
      totalQty,
      dirty: items.filter((i) => i._dirty || i._new).length,
    };
  }, [items]);

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const s = search.toLowerCase();
    return items.filter(
      (i) =>
        i.name.toLowerCase().includes(s) ||
        i.code.toLowerCase().includes(s) ||
        (i.division || "").toLowerCase().includes(s),
    );
  }, [items, search]);

  // ── Mutations ─────────────────────────────────────────────────
  const updateCell = (key: string, field: keyof BoqDraftItem, value: unknown) => {
    setItems((prev) =>
      prev.map((it) =>
        it._key === key ? { ...it, [field]: value, _dirty: true } : it,
      ),
    );
  };

  const deleteRow = (key: string) => {
    setItems((prev) => prev.filter((it) => it._key !== key));
    setSelected((prev) => prev.filter((k) => k !== key));
  };

  const addRow = () => {
    setItems((prev) => [
      ...prev,
      {
        _key: uid(),
        _new: true,
        draft_id: null,
        code: "",
        name: "",
        unit: "项",
        quantity: 0,
        division: "",
        characteristics: "",
        remark: "",
      },
    ]);
  };

  const bulkSetDivision = () => {
    if (selected.length === 0) {
      message.warning("请先选择行");
      return;
    }
    let value = "";
    Modal.confirm({
      title: `批量设置 ${selected.length} 行的分部`,
      content: (
        <Input
          placeholder="如：基础工程 / 主体结构"
          onChange={(e) => {
            value = e.target.value;
          }}
        />
      ),
      onOk: () => {
        if (!value) return;
        setItems((prev) =>
          prev.map((it) =>
            selected.includes(it._key)
              ? { ...it, division: value, _dirty: true }
              : it,
          ),
        );
        setSelected([]);
      },
    });
  };

  const reset = () => {
    Modal.confirm({
      title: "放弃所有修改？",
      onOk: () => setItems(original),
    });
  };

  // ── Commit / Discard ──────────────────────────────────────────
  const handleCommit = async () => {
    if (!token) return;
    const invalid = items.filter((i) => !i.name?.trim() || !i.code?.trim());
    if (invalid.length > 0) {
      message.error(`有 ${invalid.length} 行缺少 编码 或 名称`);
      return;
    }
    setCommitting(true);
    try {
      const payload: BoqDraftItem[] = items.map(
        ({ _key, _dirty, _new, ...rest }) => rest,
      );
      const result = await api.commitBoqDraft(projectId, token, payload);
      message.success(`已写入 ${result.created_count} 项`);
      onCommitted?.(result.created_count);
      onClose();
    } catch (e: any) {
      message.error(e.message || "提交失败");
    } finally {
      setCommitting(false);
    }
  };

  const handleDiscard = () => {
    if (!token) return;
    Modal.confirm({
      title: "确认放弃此草稿？",
      content: "草稿将被删除，AI 已识别的清单不会写入项目。",
      okType: "danger",
      onOk: async () => {
        try {
          await api.discardBoqDraft(projectId, token);
          message.success("草稿已放弃");
          onClose();
        } catch (e: any) {
          message.error(e.message || "操作失败");
        }
      },
    });
  };

  // ── Columns ───────────────────────────────────────────────────
  const columns: ColumnsType<EditableItem> = [
    {
      title: "编码",
      dataIndex: "code",
      width: 130,
      render: (v: string, r) => (
        <Input
          size="small"
          value={v}
          onChange={(e) => updateCell(r._key, "code", e.target.value)}
        />
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      render: (v: string, r) => (
        <Input
          size="small"
          value={v}
          onChange={(e) => updateCell(r._key, "name", e.target.value)}
        />
      ),
    },
    {
      title: "单位",
      dataIndex: "unit",
      width: 70,
      render: (v: string, r) => (
        <Input
          size="small"
          value={v}
          onChange={(e) => updateCell(r._key, "unit", e.target.value)}
        />
      ),
    },
    {
      title: "工程量",
      dataIndex: "quantity",
      width: 110,
      render: (v: number, r) => (
        <InputNumber
          size="small"
          value={v}
          min={0}
          step={0.01}
          style={{ width: "100%" }}
          onChange={(val) => updateCell(r._key, "quantity", val ?? 0)}
        />
      ),
    },
    {
      title: "分部",
      dataIndex: "division",
      width: 140,
      render: (v: string, r) => (
        <Input
          size="small"
          value={v}
          placeholder="未分类"
          onChange={(e) => updateCell(r._key, "division", e.target.value)}
        />
      ),
    },
    {
      title: "特征",
      dataIndex: "characteristics",
      ellipsis: true,
      render: (v: string, r) => (
        <Input
          size="small"
          value={v}
          onChange={(e) => updateCell(r._key, "characteristics", e.target.value)}
        />
      ),
    },
    {
      title: "",
      key: "_actions",
      width: 60,
      fixed: "right",
      render: (_, r) => (
        <Space>
          {r._new && (
            <Tooltip title="新增行">
              <Tag color="green">新</Tag>
            </Tooltip>
          )}
          {r._dirty && !r._new && (
            <Tooltip title="已修改">
              <Tag color="blue">改</Tag>
            </Tooltip>
          )}
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => deleteRow(r._key)}
          />
        </Space>
      ),
    },
  ];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width="80vw"
      title={
        <Space>
          <span>清单草稿预览 / 编辑</span>
          {token && <Tag>{token}</Tag>}
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => token && api.getBoqDraft(projectId, token).then((d) => {
            const editable = d.items.map((it) => ({ ...it, _key: it.draft_id || uid() }));
            setItems(editable);
            setOriginal(editable);
          })}>
            重新加载
          </Button>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={stats.dirty === 0}>
            撤销修改
          </Button>
          <Button danger onClick={handleDiscard}>放弃草稿</Button>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            loading={committing}
            onClick={handleCommit}
            disabled={items.length === 0}
          >
            写入项目（{items.length} 项）
          </Button>
        </Space>
      }
    >
      {error && <Alert type="error" message={error} style={{ marginBottom: 12 }} />}

      <div style={{ display: "flex", gap: 24, marginBottom: 12 }}>
        <Statistic title="总条数" value={stats.total} />
        <Statistic title="分部数" value={Object.keys(stats.byDivision).length} />
        <Statistic title="工程量合计" value={stats.totalQty} precision={2} />
        <Statistic title="未保存修改" value={stats.dirty} valueStyle={{ color: stats.dirty > 0 ? "#faad14" : undefined }} />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <Input.Search
          placeholder="搜索编码/名称/分部"
          allowClear
          style={{ width: 280 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button icon={<PlusOutlined />} onClick={addRow}>新增行</Button>
        <Button onClick={bulkSetDivision} disabled={selected.length === 0}>
          批量设置分部 ({selected.length})
        </Button>
        <span style={{ flex: 1 }} />
        <Space size={4} wrap>
          {Object.entries(stats.byDivision).slice(0, 8).map(([d, n]) => (
            <Tag key={d}>{d}: {n}</Tag>
          ))}
        </Space>
      </div>

      <Table<EditableItem>
        loading={loading}
        rowKey="_key"
        size="small"
        dataSource={filtered}
        columns={columns}
        pagination={{ pageSize: 50, showSizeChanger: true }}
        scroll={{ x: 900, y: "calc(100vh - 380px)" }}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as string[]),
        }}
      />
    </Drawer>
  );
}
