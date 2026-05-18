import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Input,
  Row,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Upload,
  message,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { QuotaItemDTO, QuotaChapterStat } from "../api";
import { api } from "../api";
import PageBreadcrumb from "../components/PageBreadcrumb";
import { BizTable, bizCellCode, bizCellNum } from "../components/BizTable";

const DEFAULT_PAGE_SIZE = 20;
const CHAPTER_COLLAPSED_COUNT = 12;

const CHAPTER_COLORS: Record<string, string> = {
  "土石方工程": "#d4a017",
  "地基与桩基工程": "#8b6914",
  "砌筑工程": "#cd853f",
  "混凝土工程": "#4a90d9",
  "钢筋工程": "#5b8def",
  "模板工程": "#7b68ee",
  "防水工程": "#20b2aa",
  "保温工程": "#3cb371",
  "装饰装修-抹灰": "#daa520",
  "装饰装修-墙面": "#db7093",
  "装饰装修-吊顶": "#da70d6",
  "楼地面工程": "#bc8f8f",
  "门窗工程": "#6495ed",
  "给排水-管道": "#1e90ff",
  "给排水-附件设备": "#4169e1",
  "电气-配管": "#ffa500",
  "电气-线缆": "#ff8c00",
  "电气-设备器具": "#ff7f50",
  "暖通空调工程": "#ff6347",
  "消防工程": "#dc143c",
  "弱电智能化": "#9370db",
  "室外工程": "#2e8b57",
  "脚手架及措施": "#708090",
  "拆除工程": "#a0522d",
  "钢结构工程": "#4682b4",
  "涂料涂装工程": "#deb887",
  "电梯安装工程": "#5f9ea0",
  "管道保温防腐": "#66cdaa",
  "预制装配式": "#7b68ee",
};

export default function QuotaLibrary() {
  const [items, setItems] = useState<QuotaItemDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<QuotaChapterStat[]>([]);
  const [statsTotal, setStatsTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [keyword, setKeyword] = useState("");
  const [chapter, setChapter] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState("");
  const [chapterFilter, setChapterFilter] = useState("");
  const [chaptersExpanded, setChaptersExpanded] = useState(false);
  const [show2024Fees, setShow2024Fees] = useState(false);

  // Load stats once
  useEffect(() => {
    api.getQuotaStats().then((res) => {
      setStats(res.chapters);
      setStatsTotal(res.total);
    }).catch(() => message.error("加载统计失败"));
  }, []);

  // Load items on filter/page change
  useEffect(() => {
    setLoading(true);
    api.listQuotaItems({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      chapter,
      keyword: keyword || undefined,
    }).then((res) => {
      setItems(res.items);
      setTotal(res.total);
    }).catch(() => message.error("加载定额失败"))
      .finally(() => setLoading(false));
  }, [page, pageSize, keyword, chapter]);

  // Reset page when filter changes
  useEffect(() => { setPage(1); }, [keyword, chapter, pageSize]);

  const filteredStats = useMemo(() => {
    const q = chapterFilter.trim().toLowerCase();
    if (!q) return stats;
    return stats.filter((s) => s.chapter.toLowerCase().includes(q));
  }, [stats, chapterFilter]);

  const visibleStats =
    chaptersExpanded || chapterFilter.trim()
      ? filteredStats
      : filteredStats.slice(0, CHAPTER_COLLAPSED_COUNT);

  const isFiltered = Boolean(keyword || chapter);
  const handleClearFilters = () => {
    setKeyword("");
    setSearchText("");
    setChapter(undefined);
    setChapterFilter("");
  };

  const handleImport2024 = async (file: File) => {
    setImporting(true);
    try {
      const res = await api.importQuota2024(file);
      message.success(`导入成功：${res.imported} 条定额`);
      if (res.errors?.length) message.warning(`${res.errors.length} 条跳过`);
      api.getQuotaStats().then((r) => { setStats(r.chapters); setStatsTotal(r.total); }).catch(() => {});
      setPage(1);
    } catch {
      message.error("导入失败");
    } finally {
      setImporting(false);
    }
    return false;
  };

  const copyCode = (code: string) => {
    navigator.clipboard?.writeText(code).then(
      () => message.success(`已复制 ${code}`),
      () => message.error("复制失败"),
    );
  };

  const columns: ColumnsType<QuotaItemDTO> = [
    {
      title: "编码",
      dataIndex: "quota_code",
      width: 130,
      render: (v: string) => bizCellCode(v, copyCode),
    },
    {
      title: "名称",
      dataIndex: "name",
      ellipsis: true,
    },
    {
      title: "单位",
      dataIndex: "unit",
      width: 70,
      align: "center",
      render: (v: string) => (
        <span style={{ color: "var(--text-secondary)" }}>{v}</span>
      ),
    },
    // Chapter column auto-hidden when a chapter filter is active.
    ...(chapter
      ? []
      : ([
          {
            title: "章节",
            dataIndex: "chapter",
            width: 150,
            render: (v: string) => (
              <Tag
                color={CHAPTER_COLORS[v] || "#555"}
                style={{ cursor: "pointer" }}
                onClick={() => setChapter(v)}
              >
                {v}
              </Tag>
            ),
          },
        ] as ColumnsType<QuotaItemDTO>)),
    ...(show2024Fees
      ? [
          { title: "人工费", dataIndex: "labor_fee", width: 90, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.labor_fee ?? 0) - (b.labor_fee ?? 0),
            render: (v: number) => bizCellNum(v ?? 0) },
          { title: "材料费", dataIndex: "material_fee", width: 90, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.material_fee ?? 0) - (b.material_fee ?? 0),
            render: (v: number) => bizCellNum(v ?? 0) },
          { title: "机械费", dataIndex: "machine_fee", width: 90, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.machine_fee ?? 0) - (b.machine_fee ?? 0),
            render: (v: number) => bizCellNum(v ?? 0) },
          { title: "基价", dataIndex: "base_price", width: 90, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.base_price ?? 0) - (b.base_price ?? 0),
            render: (v: number) => bizCellNum(v ?? 0) },
        ]
      : [
          { title: "人工", dataIndex: "labor_qty", width: 80, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.labor_qty ?? 0) - (b.labor_qty ?? 0),
            render: (v: number) => bizCellNum(v) },
          { title: "材料", dataIndex: "material_qty", width: 80, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.material_qty ?? 0) - (b.material_qty ?? 0),
            render: (v: number) => bizCellNum(v) },
          { title: "机械", dataIndex: "machine_qty", width: 80, align: "right" as const,
            sorter: (a: QuotaItemDTO, b: QuotaItemDTO) => (a.machine_qty ?? 0) - (b.machine_qty ?? 0),
            render: (v: number) => bizCellNum(v) },
        ]),
  ];

  const topChapter = stats[0];

  return (
    <div className="page-container" style={{ padding: 24, maxWidth: 1400 }}>
      <PageBreadcrumb items={[{ label: "定额库" }]} />

      {/* Stats Row — responsive */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={12} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>定额总数</span>
              <div className="mini-stat-card-icon blue">
                <span className="material-symbols-outlined">inventory_2</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26 }}>{statsTotal.toLocaleString()}</div>
            <div className="mini-stat-card-label">条定额条目</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>章节分类</span>
              <div className="mini-stat-card-icon emerald">
                <span className="material-symbols-outlined">category</span>
              </div>
            </div>
            <div className="mini-stat-card-value" style={{ fontSize: 26 }}>{stats.length}</div>
            <div className="mini-stat-card-label">个分类</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <div
            className="mini-stat-card"
            style={isFiltered ? { borderColor: "rgba(218, 165, 32, 0.4)" } : undefined}
          >
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>
                {isFiltered ? "当前筛选" : "当前显示"}
              </span>
              <div className={`mini-stat-card-icon ${isFiltered ? "gold" : "blue"}`}>
                <span className="material-symbols-outlined">{isFiltered ? "filter_alt" : "visibility"}</span>
              </div>
            </div>
            <div
              className="mini-stat-card-value"
              style={{ fontSize: 26, color: isFiltered ? "#fbbf24" : undefined }}
            >
              {total}
            </div>
            <div className="mini-stat-card-label">条</div>
          </div>
        </Col>
        <Col xs={24} sm={24} md={6}>
          <div className="mini-stat-card">
            <div className="mini-stat-card-head">
              <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>最大章节</span>
              <div className="mini-stat-card-icon purple">
                <span className="material-symbols-outlined">trending_up</span>
              </div>
            </div>
            {topChapter ? (
              <>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color: "#a78bfa",
                    cursor: "pointer",
                    lineHeight: 1.3,
                    letterSpacing: "-0.01em",
                  }}
                  onClick={() => setChapter(topChapter.chapter)}
                >
                  {topChapter.chapter}
                </div>
                <div className="mini-stat-card-label">{topChapter.count} 条明细</div>
              </>
            ) : (
              <div className="mini-stat-card-value" style={{ color: "var(--text-muted)", fontSize: 18 }}>—</div>
            )}
          </div>
        </Col>
      </Row>

      {/* Search bar — only the global keyword search; chapter is in the cloud below */}
      <Card
        size="small"
        className="ql-filter-card"
        style={{ marginBottom: 12 }}
        bodyStyle={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}
      >
        <span className="material-symbols-outlined" style={{ color: "#94a3b8", fontSize: 20 }}>
          search
        </span>
        <Input.Search
          placeholder="搜索定额名称…"
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onSearch={(v) => setKeyword(v)}
          style={{ width: 320 }}
        />
        {chapter && (
          <Tag
            closable
            onClose={() => setChapter(undefined)}
            color={CHAPTER_COLORS[chapter] || "#555"}
            style={{ fontSize: 13 }}
          >
            章节：{chapter}
          </Tag>
        )}
        {keyword && (
          <Tag
            closable
            onClose={() => {
              setKeyword("");
              setSearchText("");
            }}
          >
            关键词：{keyword}
          </Tag>
        )}
        {isFiltered && (
          <a
            style={{ color: "#60a5fa", cursor: "pointer", fontSize: 13 }}
            onClick={handleClearFilters}
          >
            清除全部
          </a>
        )}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <Tooltip title="显示2024版费用单价列（人工费/材料费/机械费/基价）">
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>2024费用列</span>
            <Switch
              size="small"
              checked={show2024Fees}
              onChange={setShow2024Fees}
              style={{ marginLeft: 6 }}
            />
          </Tooltip>
          <Upload
            accept=".xlsx,.xls"
            showUploadList={false}
            beforeUpload={(file) => { handleImport2024(file); return false; }}
          >
            <Button
              size="small"
              icon={<UploadOutlined />}
              loading={importing}
              type="dashed"
            >
              导入2024定额
            </Button>
          </Upload>
        </div>
      </Card>

      {/* Chapter Tag Cloud — collapsible + searchable */}
      <Card
        size="small"
        className="ql-chapter-card"
        style={{ marginBottom: 16 }}
        bodyStyle={{ display: "flex", flexDirection: "column", gap: 8 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>
            按章节筛选
          </span>
          <Input
            size="small"
            placeholder="过滤章节…"
            allowClear
            value={chapterFilter}
            onChange={(e) => setChapterFilter(e.target.value)}
            style={{ width: 180 }}
          />
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-muted)" }}>
            共 {filteredStats.length} / {stats.length}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Tag
            color={!chapter ? "blue" : undefined}
            style={{ cursor: "pointer" }}
            onClick={() => setChapter(undefined)}
          >
            全部 ({statsTotal})
          </Tag>
          {visibleStats.map((s) => {
            const active = chapter === s.chapter;
            const dimmed = chapter && !active;
            return (
              <Tag
                key={s.chapter}
                color={active ? CHAPTER_COLORS[s.chapter] || "#555" : undefined}
                style={{
                  cursor: "pointer",
                  opacity: dimmed ? 0.4 : 1,
                  transition: "opacity 0.2s",
                }}
                onClick={() => setChapter(active ? undefined : s.chapter)}
              >
                {s.chapter} ({s.count})
              </Tag>
            );
          })}
          {!chapterFilter.trim() &&
            filteredStats.length > CHAPTER_COLLAPSED_COUNT && (
              <Button
                type="link"
                size="small"
                style={{ padding: "0 8px", height: 22, fontSize: 12 }}
                onClick={() => setChaptersExpanded((v) => !v)}
              >
                {chaptersExpanded
                  ? "收起"
                  : `展开全部 (+${filteredStats.length - CHAPTER_COLLAPSED_COUNT})`}
              </Button>
            )}
        </div>
      </Card>

      {/* Table */}
      <Spin spinning={loading}>
        <BizTable<QuotaItemDTO>
          showIndex
          dataSource={items}
          columns={columns}
          rowKey="id"
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: (p, ps) => {
              setPage(p);
              if (ps !== pageSize) setPageSize(ps);
            },
          }}
          scroll={{ y: 520 }}
        />
      </Spin>
    </div>
  );
}
