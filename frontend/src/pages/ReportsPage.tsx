import { useEffect, useMemo, useState } from "react";
import { Select, Spin, message } from "antd";
import type {
  BindingWithQuota,
  BoqItem,
  CalcProvenance,
  CalcSummary,
  LineCalcResult,
  MeasureItem,
  Project,
} from "../api";
import { api } from "../api";

type ReportKey = "E1.1" | "E2.1" | "E2.2-1" | "E2.2-2" | "E2.3" | "E3.1" | "E3.2" | "E4.6" | "E5.1";

interface ReportMeta { key: ReportKey; code: string; title: string }

const REPORTS: ReportMeta[] = [
  { key: "E1.1", code: "E.1.1", title: "工程项目清单汇总表" },
  { key: "E2.1", code: "E.2.1", title: "分部分项工程项目清单计价表" },
  { key: "E2.2-1", code: "E.2.2-1", title: "综合单价分析表" },
  { key: "E2.2-2", code: "E.2.2-2", title: "综合单价分析表(简版)" },
  { key: "E2.3", code: "E.2.3", title: "材料暂估单价及调整表" },
  { key: "E3.1", code: "E.3.1", title: "措施项目清单计价表" },
  { key: "E3.2", code: "E.3.2", title: "措施项目清单构成明细分析表" },
  { key: "E4.6", code: "E.4.6", title: "直接发包的专业工程明细表" },
  { key: "E5.1", code: "E.5.1", title: "增值税计价表" },
];

const fmt = (n: number | null | undefined) =>
  n != null ? n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

interface RD {
  projectName: string;
  boqItems: BoqItem[];
  calcResult: CalcSummary | null;
  calcMap: Map<number, LineCalcResult>;
  bindings: BindingWithQuota[];
  bindingsMap: Map<number, BindingWithQuota[]>;
  measures: MeasureItem[];
  provenances: Map<number, CalcProvenance>;
}

/* ════════════════════════════════════════════════════════════════
   E.1.1 工程项目清单汇总表
   ════════════════════════════════════════════════════════════════ */
function TableE11({ d }: { d: RD }) {
  const c = d.calcResult;
  const rows = [
    { no: "1", content: "分部分项工程项目", amount: c?.total_direct, indent: 0 },
    { no: "2", content: "措施项目", amount: c?.total_measures, indent: 0 },
    { no: "2.1", content: "其中：安全生产措施项目", amount: null, indent: 1 },
    { no: "3", content: "其他项目", amount: null, indent: 0 },
    { no: "3.1", content: "其中：暂列金额", amount: null, indent: 1 },
    { no: "3.2", content: "其中：专业工程暂估价", amount: null, indent: 1 },
    { no: "3.3", content: "其中：计日工", amount: null, indent: 1 },
    { no: "3.4", content: "其中：总承包服务费", amount: null, indent: 1 },
    { no: "3.5", content: "其中：合同中约定的其他项目", amount: null, indent: 1 },
    { no: "4", content: "增值税", amount: c?.total_tax, indent: 0 },
  ];
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.1.1 工程项目清单汇总表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead><tr><th style={{ width: 60 }}>序号</th><th>项目内容</th><th style={{ width: 150 }}>金额（元）</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.no} className={r.indent === 0 ? "rpt-row-bold" : ""}>
              <td className="center">{r.no}</td>
              <td style={{ paddingLeft: 16 + r.indent * 24 }}>{r.content}</td>
              <td className="right">{fmt(r.amount)}</td>
            </tr>
          ))}
          <tr className="rpt-row-total">
            <td className="center" colSpan={2}>合 计</td>
            <td className="right">{fmt(c?.grand_total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.2.1 分部分项工程项目清单计价表
   ════════════════════════════════════════════════════════════════ */
function TableE21({ d }: { d: RD }) {
  const items = d.boqItems;
  const pageTotal = useMemo(() => {
    let unitP = 0, total = 0;
    for (const b of items) {
      const lr = d.calcMap.get(b.id);
      if (lr) { const up = b.quantity ? lr.total / b.quantity : 0; unitP += up; total += lr.total; }
    }
    return { unitP, total };
  }, [items, d.calcMap]);

  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.2.1 分部分项工程项目清单计价表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead>
          <tr>
            <th rowSpan={2} style={{ width: 44 }}>序号</th>
            <th rowSpan={2} style={{ width: 90 }}>项目编码</th>
            <th rowSpan={2}>项目名称</th>
            <th rowSpan={2}>项目特征描述</th>
            <th rowSpan={2} style={{ width: 60 }}>计量单位</th>
            <th rowSpan={2} style={{ width: 72 }}>工程量</th>
            <th colSpan={2}>金额（元）</th>
          </tr>
          <tr><th style={{ width: 100 }}>综合单价</th><th style={{ width: 100 }}>合价</th></tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr><td colSpan={8} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无清单数据</td></tr>
          ) : items.map((b, i) => {
            const lr = d.calcMap.get(b.id);
            const unitPrice = lr && b.quantity ? lr.total / b.quantity : null;
            return (
              <tr key={b.id}>
                <td className="center">{i + 1}</td>
                <td>{b.code}</td>
                <td>{b.name}</td>
                <td>{b.characteristics || "—"}</td>
                <td className="center">{b.unit}</td>
                <td className="right">{fmt(b.quantity)}</td>
                <td className="right">{fmt(unitPrice)}</td>
                <td className="right">{fmt(lr?.total)}</td>
              </tr>
            );
          })}
          <tr className="rpt-row-subtotal">
            <td colSpan={6} className="center">本页小计</td>
            <td className="right"></td>
            <td className="right">{fmt(pageTotal.total)}</td>
          </tr>
          <tr className="rpt-row-total">
            <td colSpan={6} className="center">合 计</td>
            <td className="right"></td>
            <td className="right">{fmt(pageTotal.total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.2.2-1 综合单价分析表（详版） — per BOQ item with provenance
   ════════════════════════════════════════════════════════════════ */
function TableE221({ d }: { d: RD }) {
  const itemsWithProv = d.boqItems.filter((b) => d.provenances.has(b.id));
  return (
    <div className="rpt-sheet" style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <div className="rpt-sheet-title">表 E.2.2-1 分部分项工程项目清单综合单价分析表</div>
      {itemsWithProv.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 24 }}>暂无计算溯源数据，请先执行智能组价</div>
      ) : itemsWithProv.map((b) => {
        const prov = d.provenances.get(b.id)!;
        const bd = prov.calc_breakdown;
        const ps = prov.price_snapshot;
        const laborCost = prov.bindings.reduce((s, r) => s + r.quota.labor_qty * (r.coefficient ?? 1), 0) * ps.labor_price;
        const materialCost = prov.bindings.reduce((s, r) => s + r.quota.material_qty * (r.coefficient ?? 1), 0) * ps.material_price;
        const machineCost = prov.bindings.reduce((s, r) => s + r.quota.machine_qty * (r.coefficient ?? 1), 0) * ps.machine_price;
        const directCost = laborCost + materialCost + machineCost;

        return (
          <div key={b.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 20 }}>
            <div className="rpt-sub-meta">
              <span>项目编码：<strong>{b.code}</strong></span>
              <span>项目名称：<strong>{b.name}</strong></span>
              <span>计量单位：<strong>{b.unit}</strong></span>
            </div>
            <table className="rpt-table">
              <thead><tr>
                <th style={{ width: 50 }}>序号</th><th>费用项目</th>
                <th style={{ width: 90 }}>金额(元)</th>
              </tr></thead>
              <tbody>
                <tr className="rpt-row-bold"><td className="center">1</td><td>人工费</td><td className="right">{fmt(laborCost)}</td></tr>
                {prov.bindings.map((r, i) => (
                  <tr key={i}><td className="center"></td><td style={{ paddingLeft: 32 }}>{r.quota.quota_name} (人工×{fmt(r.quota.labor_qty)})</td><td className="right">{fmt(r.quota.labor_qty * (r.coefficient ?? 1) * ps.labor_price)}</td></tr>
                ))}
                <tr className="rpt-row-bold"><td className="center">2</td><td>材料费</td><td className="right">{fmt(materialCost)}</td></tr>
                {prov.bindings.map((r, i) => (
                  <tr key={`m-${i}`}><td className="center"></td><td style={{ paddingLeft: 32 }}>{r.quota.quota_name} (材料×{fmt(r.quota.material_qty)})</td><td className="right">{fmt(r.quota.material_qty * (r.coefficient ?? 1) * ps.material_price)}</td></tr>
                ))}
                <tr className="rpt-row-bold"><td className="center">3</td><td>施工机具使用费</td><td className="right">{fmt(machineCost)}</td></tr>
                {prov.bindings.map((r, i) => (
                  <tr key={`c-${i}`}><td className="center"></td><td style={{ paddingLeft: 32 }}>{r.quota.quota_name} (机械×{fmt(r.quota.machine_qty)})</td><td className="right">{fmt(r.quota.machine_qty * (r.coefficient ?? 1) * ps.machine_price)}</td></tr>
                ))}
                <tr className="rpt-row-bold"><td className="center">4</td><td>1+2+3 小计</td><td className="right">{fmt(directCost)}</td></tr>
                <tr className="rpt-row-bold"><td className="center">5</td><td>管理费</td><td className="right">{fmt(bd?.management_fee)}</td></tr>
                <tr className="rpt-row-bold"><td className="center">6</td><td>利润</td><td className="right">{fmt(bd?.profit)}</td></tr>
                <tr className="rpt-row-total"><td colSpan={2} className="center">综合单价</td><td className="right">{fmt(prov.unit_price)}</td></tr>
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.2.2-2 综合单价分析表（简版）
   ════════════════════════════════════════════════════════════════ */
function TableE222({ d }: { d: RD }) {
  const itemsWithProv = d.boqItems.filter((b) => d.provenances.has(b.id));
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.2.2-2 分部分项工程项目清单综合单价分析表(简版)</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead>
          <tr>
            <th rowSpan={2} style={{ width: 44 }}>序号</th>
            <th rowSpan={2} style={{ width: 80 }}>项目编码</th>
            <th rowSpan={2}>项目名称</th>
            <th rowSpan={2}>项目特征描述</th>
            <th rowSpan={2} style={{ width: 56 }}>计量单位</th>
            <th colSpan={6}>综合单价组成明细(元)</th>
          </tr>
          <tr>
            <th style={{ width: 76 }}>人工费</th><th style={{ width: 76 }}>材料费</th>
            <th style={{ width: 86 }}>施工机具使用费</th><th style={{ width: 76 }}>管理费</th>
            <th style={{ width: 66 }}>利润</th><th style={{ width: 86 }}>综合单价</th>
          </tr>
        </thead>
        <tbody>
          {itemsWithProv.length === 0 ? (
            <tr><td colSpan={11} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无数据</td></tr>
          ) : itemsWithProv.map((b, idx) => {
            const prov = d.provenances.get(b.id)!;
            const bd = prov.calc_breakdown;
            const ps = prov.price_snapshot;
            const laborCost = prov.bindings.reduce((s, r) => s + r.quota.labor_qty * (r.coefficient ?? 1), 0) * ps.labor_price;
            const materialCost = prov.bindings.reduce((s, r) => s + r.quota.material_qty * (r.coefficient ?? 1), 0) * ps.material_price;
            const machineCost = prov.bindings.reduce((s, r) => s + r.quota.machine_qty * (r.coefficient ?? 1), 0) * ps.machine_price;
            return (
              <tr key={b.id}>
                <td className="center">{idx + 1}</td>
                <td>{b.code}</td><td>{b.name}</td><td>{b.characteristics || "—"}</td>
                <td className="center">{b.unit}</td>
                <td className="right">{fmt(laborCost)}</td>
                <td className="right">{fmt(materialCost)}</td>
                <td className="right">{fmt(machineCost)}</td>
                <td className="right">{fmt(bd?.management_fee)}</td>
                <td className="right">{fmt(bd?.profit)}</td>
                <td className="right">{fmt(prov.unit_price)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.2.3 材料暂估单价及调整表 — placeholder (no material-level data yet)
   ════════════════════════════════════════════════════════════════ */
function TableE23({ d }: { d: RD }) {
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.2.3 材料暂估单价及调整表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead>
          <tr>
            <th rowSpan={2} style={{ width: 50 }}>序号</th><th rowSpan={2}>材料名称</th>
            <th rowSpan={2} style={{ width: 70 }}>规格型号</th><th rowSpan={2} style={{ width: 60 }}>计量单位</th>
            <th colSpan={3}>暂估</th><th colSpan={3}>确认</th>
            <th rowSpan={2} style={{ width: 90 }}>调整金额(元)</th><th rowSpan={2} style={{ width: 50 }}>备注</th>
          </tr>
          <tr>
            <th style={{ width: 60 }}>数量</th><th style={{ width: 76 }}>单价(元)</th><th style={{ width: 76 }}>合价(元)</th>
            <th style={{ width: 60 }}>数量</th><th style={{ width: 76 }}>单价(元)</th><th style={{ width: 76 }}>合价(元)</th>
          </tr>
        </thead>
        <tbody>
          <tr><td colSpan={12} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无材料暂估数据</td></tr>
          <tr className="rpt-row-total"><td colSpan={4} className="center">合 计</td><td colSpan={8} className="right">—</td></tr>
        </tbody>
      </table>
      <div className="rpt-note">注：本表可由招标人填写"暂估单价"栏，并在备注栏说明拟用暂估价材料的清单项目。</div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.3.1 措施项目清单计价表
   ════════════════════════════════════════════════════════════════ */
function TableE31({ d }: { d: RD }) {
  const total = d.measures.reduce((s, m) => s + m.amount, 0);
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.3.1 措施项目清单计价表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead><tr>
          <th style={{ width: 50 }}>序号</th><th>项目名称</th>
          <th style={{ width: 90 }}>计算基础</th><th style={{ width: 70 }}>费率(%)</th>
          <th style={{ width: 110 }}>价格（元）</th><th style={{ width: 80 }}>备注</th>
        </tr></thead>
        <tbody>
          {d.measures.length === 0 ? (
            <tr><td colSpan={6} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无措施项目</td></tr>
          ) : d.measures.map((m, i) => (
            <tr key={m.id}>
              <td className="center">{i + 1}</td>
              <td>{m.name}</td>
              <td className="right">{m.calc_base || "—"}</td>
              <td className="right">{m.rate ? fmt(m.rate * 100) : "—"}</td>
              <td className="right">{fmt(m.amount)}</td>
              <td>{m.is_fixed ? "固定" : "浮动"}</td>
            </tr>
          ))}
          <tr className="rpt-row-total">
            <td colSpan={4} className="center">合 计</td>
            <td className="right">{fmt(total)}</td><td></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.3.2 措施项目清单构成明细分析表 — uses same measures data
   ════════════════════════════════════════════════════════════════ */
function TableE32({ d }: { d: RD }) {
  const total = d.measures.reduce((s, m) => s + m.amount, 0);
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.3.2 措施项目清单构成明细分析表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead><tr>
          <th style={{ width: 50 }}>序号</th><th>措施项目名称</th>
          <th style={{ width: 80 }}>计算基础</th><th style={{ width: 66 }}>费率(%)</th><th style={{ width: 90 }}>价格(元)</th>
          <th style={{ width: 60 }}>备注</th>
        </tr></thead>
        <tbody>
          {d.measures.length === 0 ? (
            <tr><td colSpan={6} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无措施项目</td></tr>
          ) : d.measures.map((m, i) => (
            <tr key={m.id}>
              <td className="center">{i + 1}</td><td>{m.name}</td>
              <td className="right">{m.calc_base || "—"}</td>
              <td className="right">{m.rate ? fmt(m.rate * 100) : "—"}</td>
              <td className="right">{fmt(m.amount)}</td>
              <td>{m.is_fixed ? "固定" : ""}</td>
            </tr>
          ))}
          <tr className="rpt-row-total"><td colSpan={4} className="center">合 计</td><td className="right">{fmt(total)}</td><td></td></tr>
        </tbody>
      </table>
      <div className="rpt-note">注：采用费率计价方式的，应分别填写"计算基础""费率""价格"列数值。</div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.4.6 直接发包的专业工程明细表
   ════════════════════════════════════════════════════════════════ */
function TableE46({ d }: { d: RD }) {
  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.4.6 直接发包的专业工程明细表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead><tr><th style={{ width: 50 }}>序号</th><th>直接发包的专业工程名称</th><th style={{ width: 100 }}>备注</th></tr></thead>
        <tbody>
          <tr><td colSpan={3} className="center" style={{ color: "var(--text-muted)", padding: 24 }}>暂无直接发包专业工程</td></tr>
        </tbody>
      </table>
      <div className="rpt-note">注：本表应由招标人填写，用于计算直接发包的专业工程总承包服务费。</div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   E.5.1 增值税计价表
   ════════════════════════════════════════════════════════════════ */
function TableE51({ d }: { d: RD }) {
  const c = d.calcResult;
  const preTax = c?.total_pre_tax ?? 0;
  const taxRate = preTax > 0 && c?.total_tax ? (c.total_tax / preTax) * 100 : 9;
  const rows = [
    { no: "1", name: "分部分项工程费", base: "直接费+管理费+利润+规费", baseAmt: c ? c.total_direct + c.total_management + c.total_profit + c.total_regulatory : null, rate: taxRate, amount: null as number | null },
    { no: "2", name: "措施项目费", base: "措施费合计", baseAmt: c?.total_measures ?? null, rate: taxRate, amount: null as number | null },
  ];
  rows.forEach((r) => { if (r.baseAmt != null) r.amount = r.baseAmt * r.rate / 100; });

  return (
    <div className="rpt-sheet">
      <div className="rpt-sheet-title">表 E.5.1 增值税计价表</div>
      <div className="rpt-sheet-meta">
        <span>工程名称：<strong>{d.projectName || "—"}</strong></span>
        <span className="rpt-page-info">第 1 页 共 1 页</span>
      </div>
      <table className="rpt-table">
        <thead><tr>
          <th style={{ width: 50 }}>序号</th><th>项目名称</th><th>计算基础说明</th>
          <th style={{ width: 100 }}>计算基础</th><th style={{ width: 76 }}>税率(%)</th><th style={{ width: 110 }}>金额（元）</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.no}>
              <td className="center">{r.no}</td><td>{r.name}</td><td>{r.base}</td>
              <td className="right">{fmt(r.baseAmt)}</td>
              <td className="right">{fmt(r.rate)}</td>
              <td className="right">{fmt(r.amount)}</td>
            </tr>
          ))}
          <tr className="rpt-row-total">
            <td colSpan={5} className="center">合 计</td>
            <td className="right">{fmt(c?.total_tax)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   Main ReportsPage — project selector + data loading
   ════════════════════════════════════════════════════════════════ */
export default function ReportsPage() {
  const [active, setActive] = useState<ReportKey>("E1.1");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const [boqItems, setBoqItems] = useState<BoqItem[]>([]);
  const [calcResult, setCalcResult] = useState<CalcSummary | null>(null);
  const [bindings, setBindings] = useState<BindingWithQuota[]>([]);
  const [measures, setMeasures] = useState<MeasureItem[]>([]);
  const [provenances, setProvenances] = useState<Map<number, CalcProvenance>>(new Map());

  useEffect(() => { api.listProjects().then(setProjects).catch(() => {}); }, []);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setProvenances(new Map());
    Promise.all([
      api.listBoqItems(projectId),
      api.calculate(projectId).catch(() => null),
      api.listProjectBindings(projectId).catch(() => [] as BindingWithQuota[]),
      api.listMeasures(projectId).catch(() => [] as MeasureItem[]),
    ]).then(([items, calc, binds, meas]) => {
      setBoqItems(items);
      setCalcResult(calc);
      setBindings(binds);
      setMeasures(meas);
      setLoading(false);
      // Load provenances lazily in background (not blocking UI)
      if (items.length > 0) {
        const provMap = new Map<number, CalcProvenance>();
        const BATCH = 5;
        let idx = 0;
        const next = () => {
          const batch = items.slice(idx, idx + BATCH);
          if (batch.length === 0) return;
          idx += BATCH;
          Promise.allSettled(batch.map((b) => api.getProvenance(b.id))).then((results) => {
            results.forEach((r) => {
              if (r.status === "fulfilled") provMap.set(r.value.boq_item_id, r.value);
            });
            setProvenances(new Map(provMap));
            next();
          });
        };
        next();
      }
    }).catch(() => {
      message.error("加载报表数据失败");
      setLoading(false);
    });
  }, [projectId]);

  const calcMap = useMemo(() => {
    const m = new Map<number, LineCalcResult>();
    calcResult?.line_results.forEach((lr) => m.set(lr.boq_item_id, lr));
    return m;
  }, [calcResult]);

  const bindingsMap = useMemo(() => {
    const m = new Map<number, BindingWithQuota[]>();
    bindings.forEach((b) => { const arr = m.get(b.boq_item_id) ?? []; arr.push(b); m.set(b.boq_item_id, arr); });
    return m;
  }, [bindings]);

  const project = projects.find((p) => p.id === projectId);
  const d: RD = { projectName: project?.name ?? "", boqItems, calcResult, calcMap, bindings, bindingsMap, measures, provenances };

  const renderTable = () => {
    switch (active) {
      case "E1.1": return <TableE11 d={d} />;
      case "E2.1": return <TableE21 d={d} />;
      case "E2.2-1": return <TableE221 d={d} />;
      case "E2.2-2": return <TableE222 d={d} />;
      case "E2.3": return <TableE23 d={d} />;
      case "E3.1": return <TableE31 d={d} />;
      case "E3.2": return <TableE32 d={d} />;
      case "E4.6": return <TableE46 d={d} />;
      case "E5.1": return <TableE51 d={d} />;
    }
  };

  return (
    <div className="rpt-root">
      <header className="rpt-page-header">
        <div className="rpt-page-header-left">
          <h2 className="rpt-page-title">报表中心</h2>
          <span className="pmc-live">GB 50500</span>
        </div>
        <div className="rpt-page-header-right">
          <Select
            placeholder="选择项目"
            value={projectId}
            onChange={setProjectId}
            style={{ width: 220 }}
            options={projects.map((p) => ({ label: p.name, value: p.id }))}
          />
          <button className="pmc-action-btn">
            <span className="material-symbols-outlined">print</span>
            打印
          </button>
          <button className="pmc-action-btn">
            <span className="material-symbols-outlined">download</span>
            导出
          </button>
        </div>
      </header>

      <div className="rpt-body">
        <nav className="rpt-sidebar">
          <div className="rpt-sidebar-title">工程计价费用汇总表</div>
          {REPORTS.map((r) => (
            <button key={r.key} className={`rpt-sidebar-item ${active === r.key ? "active" : ""}`} onClick={() => setActive(r.key)}>
              <span className="rpt-sidebar-code">{r.code}</span>
              <span className="rpt-sidebar-label">{r.title}</span>
            </button>
          ))}
        </nav>
        <div className="rpt-content">
          {!projectId ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12, color: "var(--text-muted)" }}>
              <span className="material-symbols-outlined" style={{ fontSize: 48 }}>assignment</span>
              <p>请先在顶部选择一个项目</p>
            </div>
          ) : loading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", gap: 12 }}>
              <Spin size="large" /><span style={{ color: "var(--text-muted)" }}>加载报表数据...</span>
            </div>
          ) : renderTable()}
        </div>
      </div>
    </div>
  );
}
