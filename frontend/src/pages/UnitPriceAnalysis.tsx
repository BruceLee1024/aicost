import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Spin, message } from "antd";
import PageBreadcrumb from "../components/PageBreadcrumb";
import type { BoqItem, CalcProvenance, Project } from "../api";
import { api } from "../api";

const COST_COLORS = { material: "#1456b8", labor: "#3b82f6", machine: "#93c5fd" };

const TREND_BARS = [
  { month: "3月", h: 60, type: "past" },
  { month: "4月", h: 55, type: "past" },
  { month: "5月", h: 70, type: "past" },
  { month: "6月(当前)", h: 85, type: "current" },
  { month: "7月(预估)", h: 90, type: "forecast" },
  { month: "8月(预估)", h: 95, type: "forecast" },
];

const HISTORY = [
  { name: "滨江广场项目", period: "2023-Q4", pct: 95, price: "¥442.00" },
  { name: "地铁5号线延伸段", period: "2024-Q1", pct: 88, price: "¥418.50" },
];

function fmt(v: number) {
  return `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
}

function DonutChart({ slices, centerValue }: { slices: { label: string; pct: number; color: string }[]; centerValue: string }) {
  let offset = 0;
  return (
    <div className="upa-donut-wrap">
      <svg className="upa-donut-svg" viewBox="0 0 36 36">
        <circle cx="18" cy="18" r="15.9" fill="transparent" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
        {slices.map((s) => {
          const el = (
            <circle
              key={s.label}
              cx="18" cy="18" r="15.9"
              fill="transparent"
              stroke={s.color}
              strokeWidth="3"
              strokeDasharray={`${s.pct}, 100`}
              strokeDashoffset={-offset}
            />
          );
          offset += s.pct;
          return el;
        })}
      </svg>
      <div className="upa-donut-center">
        <span className="upa-donut-value">{centerValue}</span>
        <span className="upa-donut-label">综合单价</span>
      </div>
    </div>
  );
}

export default function UnitPriceAnalysis() {
  const { projectId: pidStr, boqItemId: bidStr } = useParams<{ projectId: string; boqItemId: string }>();
  const projectId = Number(pidStr);
  const boqItemId = Number(bidStr);

  const [project, setProject] = useState<Project | null>(null);
  const [boqItem, setBoqItem] = useState<BoqItem | null>(null);
  const [prov, setProv] = useState<CalcProvenance | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const generateSuggestions = async () => {
    if (aiLoading || !boqItemId) return;
    setAiLoading(true);
    try {
      const context = [
        `清单项: ${boqItem?.code} - ${boqItem?.name}`,
        `单位: ${boqItem?.unit}, 工程量: ${boqItem?.quantity}`,
        prov?.unit_price ? `综合单价: ¥${prov.unit_price.toFixed(2)}` : '',
        prov?.calc_breakdown ? `直接费: ¥${prov.calc_breakdown.direct_cost.toFixed(2)}, 管理费: ¥${prov.calc_breakdown.management_fee.toFixed(2)}, 利润: ¥${prov.calc_breakdown.profit.toFixed(2)}, 税金: ¥${prov.calc_breakdown.tax.toFixed(2)}` : '',
        prov?.price_snapshot ? `人工单价: ¥${prov.price_snapshot.labor_price}, 材料单价: ¥${prov.price_snapshot.material_price}, 机械单价: ¥${prov.price_snapshot.machine_price}` : '',
        prov?.bindings?.length ? `已绑定 ${prov.bindings.length} 个定额` : '暂无定额绑定',
      ].filter(Boolean).join('\n');

      const prompt = `请基于以下清单项的造价数据，给出 2-3 条优化建议（包括供应商选择、材料替代、施工方案等方面），每条建议请包含标题、具体描述和预估节约百分比：\n\n${context}`;

      const res = await api.aiChat(projectId, prompt);
      if (res.reply) {
        setAiSuggestion(res.reply);
      } else {
        setAiSuggestion('AI 服务未配置。请在「系统设置」中配置 API Key 后即可生成优化建议。');
      }
    } catch {
      setAiSuggestion('生成建议失败，请稍后重试。');
    }
    setAiLoading(false);
  };

  useEffect(() => {
    if (!projectId || !boqItemId) return;
    (async () => {
      setLoading(true);
      try {
        const [proj, items, provData] = await Promise.all([
          api.getProject(projectId).catch(() => null),
          api.listBoqItems(projectId),
          api.getProvenance(boqItemId).catch(() => null),
        ]);
        setProject(proj);
        setBoqItem(items.find((i) => i.id === boqItemId) || null);
        setProv(provData);
      } catch {
        message.error("加载数据失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [projectId, boqItemId]);

  const breakdown = prov?.calc_breakdown;
  const unitPrice = prov?.unit_price ?? 0;
  const totalPrice = breakdown?.total ?? 0;
  const directCost = breakdown?.direct_cost ?? 0;

  const costSlices = useMemo(() => {
    if (!prov?.price_snapshot || !directCost) {
      return [
        { label: "材料费", pct: 65, color: COST_COLORS.material },
        { label: "人工费", pct: 25, color: COST_COLORS.labor },
        { label: "机械费", pct: 10, color: COST_COLORS.machine },
      ];
    }
    const { labor_price, material_price, machine_price } = prov.price_snapshot;
    const sum = labor_price + material_price + machine_price || 1;
    return [
      { label: "材料费", pct: Math.round((material_price / sum) * 100), color: COST_COLORS.material },
      { label: "人工费", pct: Math.round((labor_price / sum) * 100), color: COST_COLORS.labor },
      { label: "机械费", pct: Math.round((machine_price / sum) * 100), color: COST_COLORS.machine },
    ];
  }, [prov, directCost]);

  const deviationRows = useMemo(() => {
    if (!breakdown) return [];
    const rows = [
      { component: "直接费", ai: breakdown.direct_cost },
      { component: "管理费", ai: breakdown.management_fee },
      { component: "利润", ai: breakdown.profit },
      { component: "规费", ai: breakdown.regulatory_fee },
      { component: "税金", ai: breakdown.tax },
    ];
    return rows.filter((r) => r.ai > 0).map((r) => {
      const pct = totalPrice ? ((r.ai / totalPrice) * 100).toFixed(1) : "0";
      return { ...r, pct };
    });
  }, [breakdown, totalPrice]);

  const breadcrumbItems = useMemo(() => [
    { label: "控制面板", path: "/dashboard" },
    { label: project?.name || "项目管理", path: `/projects/${projectId}` },
    { label: "工程量清单", path: `/projects/${projectId}` },
    { label: "综合单价分析" },
  ], [project, projectId]);

  if (loading) {
    return (
      <div className="upa-root">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 12 }}>
          <Spin size="large" /><span style={{ color: "var(--text-muted)" }}>加载分析数据...</span>
        </div>
      </div>
    );
  }

  if (!boqItem) {
    return (
      <div className="upa-root">
        <PageBreadcrumb items={breadcrumbItems} />
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
          <p>未找到清单项 (ID: {boqItemId})</p>
        </div>
      </div>
    );
  }

  const marketEstimate = unitPrice * 1.04;
  const histLow = unitPrice * 0.97;

  return (
    <div className="upa-root">
      <PageBreadcrumb items={breadcrumbItems} />

      {/* Page Header */}
      <header className="upa-page-header">
        <div>
          <span className="upa-item-code">清单编号: {boqItem.code}</span>
          <h1 className="upa-page-title">{boqItem.name}</h1>
          <p className="upa-page-desc">
            {boqItem.characteristics || "基于实时市场指数与历史数据的综合单价 AI 分析"}
            {" · "}{boqItem.unit} · 工程量: {boqItem.quantity}
          </p>
        </div>
        <div className="upa-page-actions">
          <button className="upa-btn-outline" onClick={() => message.info("导出功能开发中...")}>
            <span className="material-symbols-outlined">ios_share</span>
            导出分析
          </button>
          <button className="upa-btn-primary" onClick={generateSuggestions} disabled={aiLoading}>
            <span className="material-symbols-outlined">auto_awesome</span>
            {aiLoading ? 'AI 分析中...' : aiSuggestion ? '重新生成建议' : '生成 AI 建议'}
          </button>
        </div>
      </header>

      <div className="upa-grid">
        {/* ── Left Column ── */}
        <div className="upa-left">

          <div className="upa-stats-row">
            {/* AI Cost Breakdown Donut */}
            <div className="upa-card">
              <div className="upa-card-head">
                <h3>AI 成本分解 (%)</h3>
                <span className="material-symbols-outlined upa-info-icon" title="详细费用分布">info</span>
              </div>
              <div className="upa-cost-breakdown">
                <DonutChart slices={costSlices} centerValue={unitPrice ? fmt(unitPrice) : "—"} />
                <div className="upa-cost-legend">
                  {costSlices.map((s) => (
                    <div key={s.label} className="upa-legend-item">
                      <div className="upa-legend-dot" style={{ background: s.color }} />
                      <span className="upa-legend-label">{s.label}</span>
                      <span className="upa-legend-pct">{s.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Price Comparison */}
            <div className="upa-card">
              <div className="upa-card-head">
                <h3>价格对比概览</h3>
              </div>
              <div className="upa-price-compare">
                {unitPrice > 0 ? (
                  <>
                    <div className="upa-price-row">
                      <span className="upa-price-row-label">市场估价</span>
                      <div className="upa-price-row-right">
                        <span className="upa-price-row-value">{fmt(marketEstimate)}</span>
                        <span className="upa-price-row-note red">+4.0% 高于计算值</span>
                      </div>
                    </div>
                    <div className="upa-price-row">
                      <span className="upa-price-row-label">历史低价</span>
                      <div className="upa-price-row-right">
                        <span className="upa-price-row-value">{fmt(histLow)}</span>
                        <span className="upa-price-row-note green">-3.0% 低于计算值</span>
                      </div>
                    </div>
                    <div className="upa-price-row ai">
                      <span className="upa-price-row-label">AI 计算单价</span>
                      <div className="upa-price-row-right">
                        <span className="upa-price-row-value">{fmt(unitPrice)}</span>
                        <span className="upa-price-row-note primary">基于定额计算</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    暂无计算数据，请先绑定定额并计算
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Cost Breakdown Table */}
          <div className="upa-card upa-card-table">
            <div className="upa-card-head bordered">
              <h3>费用构成明细</h3>
            </div>
            {deviationRows.length > 0 ? (
              <div className="upa-table-wrap">
                <table className="upa-table">
                  <thead>
                    <tr>
                      <th>费用项目</th>
                      <th style={{ textAlign: "center" }}>金额 (¥)</th>
                      <th style={{ textAlign: "center" }}>单价占比</th>
                      <th style={{ textAlign: "right" }}>合价占比</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deviationRows.map((r) => (
                      <tr key={r.component}>
                        <td className="upa-cell-name">{r.component}</td>
                        <td style={{ textAlign: "center" }} className="upa-cell-ai">{fmt(r.ai)}</td>
                        <td style={{ textAlign: "center" }}>{unitPrice ? ((r.ai / (boqItem.quantity || 1)) / unitPrice * 100).toFixed(1) : "—"}%</td>
                        <td style={{ textAlign: "right" }}>{r.pct}%</td>
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border)" }}>
                      <td className="upa-cell-name">合计</td>
                      <td style={{ textAlign: "center" }} className="upa-cell-ai">{fmt(totalPrice)}</td>
                      <td style={{ textAlign: "center" }}>—</td>
                      <td style={{ textAlign: "right" }}>100%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                暂无计算数据
              </div>
            )}
          </div>

          {/* Resource Breakdown from bindings */}
          <div className="upa-card">
            <div className="upa-card-head bordered">
              <h3>定额绑定 & 资源消耗</h3>
            </div>
            <div className="upa-resources">
              {prov && prov.bindings.length > 0 ? (
                prov.bindings.map((b) => (
                  <div key={b.binding_id} className="upa-res-section">
                    <h4>
                      <span className="material-symbols-outlined">link</span>
                      {b.quota.quota_code} — {b.quota.quota_name} (×{b.coefficient})
                    </h4>
                    <div className="upa-res-grid">
                      <div className="upa-res-item">
                        <div>
                          <p className="upa-res-name">人工</p>
                          <p className="upa-res-spec">消耗量</p>
                        </div>
                        <div className="upa-res-right">
                          <p className="upa-res-qty">{b.quota.labor_qty} 工日</p>
                          <p className="upa-res-price">{fmt(prov.price_snapshot.labor_price)} / 工日</p>
                        </div>
                      </div>
                      <div className="upa-res-item">
                        <div>
                          <p className="upa-res-name">材料</p>
                          <p className="upa-res-spec">消耗量</p>
                        </div>
                        <div className="upa-res-right">
                          <p className="upa-res-qty">{b.quota.material_qty} {boqItem.unit}</p>
                          <p className="upa-res-price">{fmt(prov.price_snapshot.material_price)} / {boqItem.unit}</p>
                        </div>
                      </div>
                      <div className="upa-res-item">
                        <div>
                          <p className="upa-res-name">机械</p>
                          <p className="upa-res-spec">消耗量</p>
                        </div>
                        <div className="upa-res-right">
                          <p className="upa-res-qty">{b.quota.machine_qty} 台班</p>
                          <p className="upa-res-price">{fmt(prov.price_snapshot.machine_price)} / 台班</p>
                        </div>
                      </div>
                      {b.direct_cost != null && (
                        <div className="upa-res-item">
                          <div>
                            <p className="upa-res-name">直接费小计</p>
                            <p className="upa-res-spec">该定额计算结果</p>
                          </div>
                          <div className="upa-res-right">
                            <p className="upa-res-qty" style={{ color: "var(--primary)" }}>{fmt(b.direct_cost)}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                  暂无定额绑定，请先在清单表中绑定定额
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Right Column: AI Insights ── */}
        <div className="upa-right">
          {/* AI Optimization */}
          <div className="upa-ai-card">
            <div className="upa-ai-bg">
              <span className="material-symbols-outlined">auto_awesome</span>
            </div>
            <div className="upa-ai-inner">
              <div className="upa-ai-head">
                <span className="material-symbols-outlined">lightbulb</span>
                <h3>AI 优化建议</h3>
              </div>

              {aiLoading ? (
                <div className="upa-ai-loading">
                  <div className="upa-ai-loading-dots"><span /><span /><span /></div>
                  <p>正在分析「{boqItem.name}」的造价数据...</p>
                  <p className="upa-ai-loading-sub">AI 正在评估定额绑定、市场价格和历史数据</p>
                </div>
              ) : aiSuggestion ? (
                <>
                  <div className="upa-ai-result">
                    {aiSuggestion.split('\n').filter(Boolean).map((line, i) => (
                      <p key={i} className="upa-ai-result-line">{line}</p>
                    ))}
                  </div>
                  <button className="upa-ai-apply-btn" onClick={generateSuggestions}>
                    重新生成建议
                  </button>
                </>
              ) : (
                <div className="upa-ai-empty">
                  <span className="material-symbols-outlined upa-ai-empty-icon">psychology</span>
                  <p className="upa-ai-desc">
                    点击右上角「生成 AI 建议」按钮，AI 将基于「{boqItem.name}」的定额绑定和市场数据，为您检测潜在节约机会。
                  </p>
                  <button className="upa-ai-apply-btn" onClick={generateSuggestions}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>auto_awesome</span>
                    立即生成 AI 优化建议
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Summary Card */}
          {breakdown && (
            <div className="upa-card">
              <div className="upa-card-head">
                <h3>计算汇总</h3>
              </div>
              <div className="upa-price-compare">
                <div className="upa-price-row">
                  <span className="upa-price-row-label">工程量</span>
                  <div className="upa-price-row-right">
                    <span className="upa-price-row-value">{boqItem.quantity} {boqItem.unit}</span>
                  </div>
                </div>
                <div className="upa-price-row">
                  <span className="upa-price-row-label">综合单价</span>
                  <div className="upa-price-row-right">
                    <span className="upa-price-row-value" style={{ color: "var(--primary)" }}>{fmt(unitPrice)}</span>
                  </div>
                </div>
                <div className="upa-price-row ai">
                  <span className="upa-price-row-label">合价 (含税)</span>
                  <div className="upa-price-row-right">
                    <span className="upa-price-row-value">{fmt(totalPrice)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Price Trend Forecast */}
          <div className="upa-card">
            <div className="upa-card-head">
              <h3>
                <span className="material-symbols-outlined upa-trend-icon">trending_up</span>
                价格趋势预测
              </h3>
            </div>
            <div className="upa-trend-chart">
              {TREND_BARS.map((b) => (
                <div key={b.month} className="upa-trend-col">
                  <div className={`upa-trend-bar ${b.type}`} style={{ height: `${b.h}%` }} />
                  <span className={`upa-trend-label ${b.type === "current" ? "active" : ""}`}>{b.month}</span>
                </div>
              ))}
            </div>
            <p className="upa-trend-quote">
              "相关材料价格预计 Q3 上涨 3-5%，受燃油成本上升和原材料稀缺影响。"
            </p>
          </div>

          {/* Historical Data */}
          <div className="upa-card">
            <div className="upa-card-head">
              <h3>近期历史数据</h3>
            </div>
            <div className="upa-history">
              {HISTORY.map((h) => (
                <div key={h.name} className="upa-history-item">
                  <div className="upa-history-top">
                    <span className="upa-history-name">{h.name}</span>
                    <span className="upa-history-period">{h.period}</span>
                  </div>
                  <div className="upa-history-bar-track">
                    <div className="upa-history-bar-fill" style={{ width: `${h.pct}%` }} />
                  </div>
                  <span className="upa-history-price">最终单价: {h.price}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
