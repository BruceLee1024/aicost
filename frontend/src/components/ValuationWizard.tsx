import { useEffect, useState } from "react";
import { Modal as AntModal, Progress, Tag, message } from "antd";
import { CheckCircleOutlined } from "@ant-design/icons";
import type {
  Binding, BoqItem, CalcSummary, LineCalcResult,
  MatchCandidate, ValidationIssue, ValidationReport,
} from "../api";
import { api } from "../api";
import AiInsightPanel from "./AiInsightPanel";

// ─── Types ───────────────────────────────────────────────────────

interface Props {
  projectId: number;
  open: boolean;
  onClose: () => void;
  onComplete: (calcResult: CalcSummary) => void;
}

type Step = 0 | 1 | 2 | 3;

interface BoqScanRow extends BoqItem {
  bindings: Binding[];
  bound: boolean;
}

interface MatchChoice {
  boqItem: BoqItem;
  candidates: MatchCandidate[];
  chosen: number | null; // quota_item_id or null = skip
  status: "pending" | "loading" | "ready" | "confirmed" | "skipped";
}

const STEP_LABELS = ["扫描分析", "智能匹配", "计算预览", "异常检测"];
const STEP_ICONS = ["search", "auto_awesome", "calculate", "verified"];

// ─── Component ───────────────────────────────────────────────────

export default function ValuationWizard({ projectId, open, onClose, onComplete }: Props) {
  const [step, setStep] = useState<Step>(0);

  // Step 1: scan
  const [scanRows, setScanRows] = useState<BoqScanRow[]>([]);
  const [scanning, setScanning] = useState(false);

  // Step 2: match
  const [matchItems, setMatchItems] = useState<MatchChoice[]>([]);
  const [matchIdx, setMatchIdx] = useState(0);
  const [matchBatchLoading, setMatchBatchLoading] = useState(false);
  const [matchApplyAllLoading, setMatchApplyAllLoading] = useState(false);

  // Step 3: calc
  const [calcResult, setCalcResult] = useState<CalcSummary | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);

  // Step 4: validate
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [valLoading, setValLoading] = useState(false);

  // Reset on open
  useEffect(() => {
    if (open) {
      setStep(0);
      setScanRows([]);
      setMatchItems([]);
      setMatchIdx(0);
      setCalcResult(null);
      setValidation(null);
      runScan();
    }
  }, [open]);

  // ─── Step 1: Scan ────────────────────────────────────────────

  const runScan = async () => {
    setScanning(true);
    try {
      const items = await api.listBoqItems(projectId);
      const enriched: BoqScanRow[] = await Promise.all(
        items.map(async (item) => {
          try {
            const bindings = await api.listBindings(item.id);
            return { ...item, bindings, bound: bindings.length > 0 };
          } catch {
            return { ...item, bindings: [], bound: false };
          }
        }),
      );
      setScanRows(enriched);
    } catch {
      message.error("扫描失败");
    }
    setScanning(false);
  };

  const boundRows = scanRows.filter((r) => r.bound);
  const unboundRows = scanRows.filter((r) => !r.bound);

  // ─── Step 2: Match ───────────────────────────────────────────

  const startMatching = async () => {
    setStep(1);
    setMatchIdx(0);
    setMatchBatchLoading(true);
    // Pre-fetch candidates for all unbound items
    const choices: MatchChoice[] = unboundRows.map((item) => ({
      boqItem: item,
      candidates: [],
      chosen: null,
      status: "pending" as const,
    }));
    setMatchItems(choices);

    // Fetch candidates in parallel (batches of 3)
    for (let i = 0; i < choices.length; i += 3) {
      const batch = choices.slice(i, i + 3);
      const results = await Promise.allSettled(
        batch.map((c) => api.getQuotaCandidates(c.boqItem.id, 3)),
      );
      results.forEach((res, j) => {
        const idx = i + j;
        if (res.status === "fulfilled") {
          choices[idx].candidates = res.value;
          choices[idx].chosen = res.value.length > 0 ? res.value[0].quota_item_id : null;
          choices[idx].status = "ready";
        } else {
          choices[idx].status = "ready";
        }
      });
      setMatchItems([...choices]);
    }
    setMatchBatchLoading(false);
  };

  const handleMatchAccept = async (idx: number) => {
    const item = matchItems[idx];
    if (!item.chosen) return;
    const updated = [...matchItems];
    updated[idx] = { ...item, status: "loading" };
    setMatchItems(updated);
    try {
      await api.replaceBinding(item.boqItem.id, item.chosen);
      updated[idx] = { ...item, status: "confirmed" };
    } catch {
      message.error("绑定失败");
      updated[idx] = { ...item, status: "ready" };
    }
    setMatchItems([...updated]);
    // Auto-advance to next
    if (idx < matchItems.length - 1) setMatchIdx(idx + 1);
  };

  const handleMatchSkip = (idx: number) => {
    const updated = [...matchItems];
    updated[idx] = { ...matchItems[idx], status: "skipped" };
    setMatchItems(updated);
    if (idx < matchItems.length - 1) setMatchIdx(idx + 1);
  };

  const handleMatchChoose = (idx: number, quotaId: number) => {
    const updated = [...matchItems];
    updated[idx] = { ...matchItems[idx], chosen: quotaId };
    setMatchItems(updated);
  };

  const handleBatchMatchAccept = async () => {
    const targets = matchItems
      .filter((m) => m.status === "ready" && !!m.chosen)
      .map((m) => ({ boq_item_id: m.boqItem.id, quota_item_id: m.chosen as number }));

    if (targets.length === 0) {
      message.info("没有可批量确认的候选项");
      return;
    }

    setMatchApplyAllLoading(true);
    try {
      await api.batchReplaceBindings(targets);
      const acceptedIds = new Set(targets.map((t) => t.boq_item_id));
      const updated = matchItems.map((m) => (
        acceptedIds.has(m.boqItem.id) && m.status === "ready"
          ? { ...m, status: "confirmed" as const }
          : m
      ));
      setMatchItems(updated);
      const nextPendingIdx = updated.findIndex((m) => m.status === "ready");
      if (nextPendingIdx >= 0) setMatchIdx(nextPendingIdx);
      message.success(`已批量确认 ${targets.length} 项绑定`);
    } catch {
      message.error("批量确认失败");
    }
    setMatchApplyAllLoading(false);
  };

  const matchConfirmedCount = matchItems.filter((m) => m.status === "confirmed").length;
  const matchDoneCount = matchItems.filter((m) => m.status === "confirmed" || m.status === "skipped").length;

  // ─── Step 3: Calculate ───────────────────────────────────────

  const runCalc = async () => {
    setStep(2);
    setCalcLoading(true);
    try {
      const res = await api.calculate(projectId);
      setCalcResult(res);
    } catch {
      message.error("计算失败");
    }
    setCalcLoading(false);
  };

  // ─── Step 4: Validate ────────────────────────────────────────

  const runValidation = async () => {
    setStep(3);
    setValLoading(true);
    try {
      setValidation(await api.validate(projectId));
    } catch {
      message.error("校验失败");
    }
    setValLoading(false);
  };

  const handleClose = () => {
    if (step > 0 || matchItems.length > 0 || calcResult) {
      AntModal.confirm({
        title: "确认关闭",
        content: "关闭将丢失当前组价进度，确认关闭吗？",
        okText: "确认关闭",
        cancelText: "继续操作",
        okButtonProps: { danger: true },
        onOk: onClose,
      });
    } else {
      onClose();
    }
  };

  const handleFinish = () => {
    if (calcResult) onComplete(calcResult);
    onClose();
  };

  // ─── Render ──────────────────────────────────────────────────

  if (!open) return null;

  return (
    <div className="wizard-overlay">
      <div className="wizard-container">
        {/* Header with stepper */}
        <div className="wizard-header">
          <div className="wizard-header-title">
            <span className="material-symbols-outlined" style={{ color: "var(--primary)" }}>auto_awesome</span>
            <span>智能组价助手</span>
          </div>
          <button className="wizard-close" onClick={handleClose}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Stepper */}
        <div className="wizard-stepper">
          {STEP_LABELS.map((label, i) => (
            <div key={i} className={`wizard-step-dot ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}>
              <div className="wizard-step-circle">
                {i < step
                  ? <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check</span>
                  : <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{STEP_ICONS[i]}</span>}
              </div>
              <span className="wizard-step-label">{label}</span>
              {i < 3 && <div className={`wizard-step-line ${i < step ? "done" : ""}`} />}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="wizard-body">
          {step === 0 && renderStep1()}
          {step === 1 && renderStep2()}
          {step === 2 && renderStep3()}
          {step === 3 && renderStep4()}
        </div>

        {/* Footer */}
        <div className="wizard-footer">
          {step > 0 && (
            <button className="btn-secondary" onClick={() => setStep((s) => (s - 1) as Step)}>
              <span className="material-symbols-outlined">arrow_back</span> 上一步
            </button>
          )}
          <div style={{ flex: 1 }} />
          {renderFooterActions()}
        </div>
      </div>
    </div>
  );

  // ─── Step Renderers ──────────────────────────────────────────

  function renderStep1() {
    if (scanning) {
      return (
        <div className="wizard-loading">
          <span className="material-symbols-outlined wizard-loading-icon">radar</span>
          <div className="wizard-loading-text">AI 正在扫描项目清单...</div>
          <div className="wizard-loading-sub">分析绑定状态与定额匹配情况</div>
        </div>
      );
    }

    return (
      <div className="wizard-content-split">
        <div className="wizard-main">
          <h3 className="wizard-section-title">清单扫描结果</h3>
          <div className="wizard-stat-grid">
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">{scanRows.length}</div>
              <div className="wizard-stat-label">清单项总数</div>
            </div>
            <div className="wizard-stat-card green">
              <div className="wizard-stat-value">{boundRows.length}</div>
              <div className="wizard-stat-label">已绑定定额</div>
            </div>
            <div className="wizard-stat-card orange">
              <div className="wizard-stat-value">{unboundRows.length}</div>
              <div className="wizard-stat-label">待匹配</div>
            </div>
          </div>

          {unboundRows.length > 0 && (
            <>
              <h3 className="wizard-section-title" style={{ marginTop: 24 }}>待匹配清单项</h3>
              <div className="wizard-item-list">
                {unboundRows.map((r) => (
                  <div key={r.id} className="wizard-item-row">
                    <Tag color="red" style={{ flexShrink: 0 }}>未绑定</Tag>
                    <span style={{ fontWeight: 500 }}>{r.code}</span>
                    <span style={{ color: "var(--text-secondary)" }}>{r.name}</span>
                    <span style={{ color: "var(--text-muted)", marginLeft: "auto" }}>{r.quantity} {r.unit}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <AiInsightPanel
          projectId={projectId}
          contextType="scan"
          contextData={{
            boq_count: scanRows.length,
            bound_count: boundRows.length,
            unbound_count: unboundRows.length,
            divisions: [...new Set(scanRows.map((r) => r.division).filter(Boolean))],
          }}
          title="AI 扫描分析"
          fallback={`已扫描 ${scanRows.length} 个清单项：${boundRows.length} 项已绑定，${unboundRows.length} 项待匹配。${unboundRows.length === 0 ? "可直接进入计算阶段。" : "建议进入下一步进行智能匹配。"}`}
          triggerKey={`scan-${scanRows.length}`}
        />
      </div>
    );
  }

  function renderStep2() {
    if (matchBatchLoading && matchItems.every((m) => m.status === "pending")) {
      return (
        <div className="wizard-loading">
          <span className="material-symbols-outlined wizard-loading-icon">auto_awesome</span>
          <div className="wizard-loading-text">AI 正在分析定额匹配...</div>
          <div className="wizard-loading-sub">为 {unboundRows.length} 个清单项寻找最佳候选</div>
        </div>
      );
    }

    const current = matchItems[matchIdx];

    return (
      <div className="wizard-content-split">
        <div className="wizard-main">
          {/* Progress bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              {matchDoneCount}/{matchItems.length} 已处理
            </span>
            <Progress
              percent={matchItems.length > 0 ? Math.round((matchDoneCount / matchItems.length) * 100) : 0}
              size="small" style={{ flex: 1, margin: 0 }}
            />
          </div>

          {/* Item tabs */}
          <div className="wizard-match-tabs">
            {matchItems.map((m, i) => (
              <button
                key={m.boqItem.id}
                className={`wizard-match-tab ${i === matchIdx ? "active" : ""} ${m.status === "confirmed" ? "confirmed" : ""} ${m.status === "skipped" ? "skipped" : ""}`}
                onClick={() => setMatchIdx(i)}
              >
                {m.status === "confirmed" && <span className="material-symbols-outlined" style={{ fontSize: 14, color: "#22c55e" }}>check_circle</span>}
                {m.status === "skipped" && <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--text-muted)" }}>skip_next</span>}
                {m.boqItem.code}
              </button>
            ))}
          </div>

          {/* Current item detail */}
          {current && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>
                <Tag color="blue">{current.boqItem.code}</Tag> {current.boqItem.name}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 16 }}>
                {current.boqItem.quantity} {current.boqItem.unit}
                {current.boqItem.characteristics && ` · ${current.boqItem.characteristics}`}
              </div>

              {current.status === "confirmed" ? (
                <div className="wizard-match-done-badge green">
                  <span className="material-symbols-outlined">check_circle</span> 已确认绑定
                </div>
              ) : current.status === "skipped" ? (
                <div className="wizard-match-done-badge gray">
                  <span className="material-symbols-outlined">skip_next</span> 已跳过
                </div>
              ) : current.candidates.length === 0 ? (
                <div style={{ color: "var(--text-secondary)", padding: 20, textAlign: "center" }}>
                  未找到匹配的定额候选
                </div>
              ) : (
                <div className="wizard-candidate-list">
                  {current.candidates.map((c, ci) => (
                    <div
                      key={c.quota_item_id}
                      className={`wizard-candidate ${current.chosen === c.quota_item_id ? "selected" : ""}`}
                      onClick={() => handleMatchChoose(matchIdx, c.quota_item_id)}
                    >
                      <div className="wizard-candidate-header">
                        <div>
                          {ci === 0 && <Tag color="green" style={{ fontSize: 10 }}>AI 推荐</Tag>}
                          <Tag color="blue">{c.quota_code}</Tag>
                          <strong>{c.quota_name}</strong>
                          <span style={{ color: "var(--text-secondary)", marginLeft: 6 }}>{c.unit}</span>
                        </div>
                        <div className="wizard-candidate-radio">
                          {current.chosen === c.quota_item_id && <span className="material-symbols-outlined" style={{ color: "var(--primary)" }}>radio_button_checked</span>}
                          {current.chosen !== c.quota_item_id && <span className="material-symbols-outlined" style={{ color: "var(--text-muted)" }}>radio_button_unchecked</span>}
                        </div>
                      </div>
                      <Progress
                        percent={Math.round(c.confidence * 100)} size="small"
                        strokeColor={c.confidence > 0.7 ? "#22c55e" : c.confidence > 0.4 ? "#f59e0b" : "#ef4444"}
                      />
                      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>
                        {c.reasons.map((r, j) => <Tag key={j} color="default" style={{ marginTop: 2 }}>{r}</Tag>)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <AiInsightPanel
          projectId={projectId}
          contextType="match"
          contextData={{
            current_index: matchIdx + 1,
            total: matchItems.length,
            confirmed: matchConfirmedCount,
            skipped: matchDoneCount - matchConfirmedCount,
            current_item: current ? {
              code: current.boqItem.code,
              name: current.boqItem.name,
              unit: current.boqItem.unit,
              top_candidate: current.candidates[0] ? {
                quota_name: current.candidates[0].quota_name,
                confidence: current.candidates[0].confidence,
                reasons: current.candidates[0].reasons,
              } : null,
            } : null,
          }}
          title="AI 匹配分析"
          fallback={current && current.candidates.length > 0
            ? `正在处理第 ${matchIdx + 1}/${matchItems.length} 项。AI 推荐 ${current.candidates[0].quota_name}，置信度 ${Math.round(current.candidates[0].confidence * 100)}%。`
            : `正在处理第 ${matchIdx + 1}/${matchItems.length} 项。`
          }
          triggerKey={`match-${matchIdx}`}
        />
      </div>
    );
  }

  function renderStep3() {
    if (calcLoading || !calcResult) {
      return (
        <div className="wizard-loading">
          <span className="material-symbols-outlined wizard-loading-icon">calculate</span>
          <div className="wizard-loading-text">AI 正在执行计价计算...</div>
          <div className="wizard-loading-sub">综合分析直接费、管理费、利润与税金</div>
        </div>
      );
    }

    return (
      <div className="wizard-content-split">
        <div className="wizard-main">
          <h3 className="wizard-section-title">计算结果预览</h3>
          <div className="wizard-stat-grid">
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">¥{calcResult.total_direct.toLocaleString()}</div>
              <div className="wizard-stat-label">直接费</div>
            </div>
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">¥{calcResult.total_management.toLocaleString()}</div>
              <div className="wizard-stat-label">管理费</div>
            </div>
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">¥{calcResult.total_profit.toLocaleString()}</div>
              <div className="wizard-stat-label">利润</div>
            </div>
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">¥{calcResult.total_tax.toLocaleString()}</div>
              <div className="wizard-stat-label">税金</div>
            </div>
          </div>

          <div className="wizard-grand-total">
            <span>工程合计</span>
            <span className="wizard-grand-total-value">¥{calcResult.grand_total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</span>
          </div>

          {/* Line items */}
          <h3 className="wizard-section-title" style={{ marginTop: 20 }}>分项明细</h3>
          <div className="wizard-item-list">
            {calcResult.line_results.map((lr: LineCalcResult) => (
              <div key={lr.boq_item_id} className="wizard-item-row" style={{ justifyContent: "space-between" }}>
                <div>
                  <span style={{ fontWeight: 500 }}>{lr.boq_code}</span>
                  <span style={{ color: "var(--text-secondary)", marginLeft: 8 }}>{lr.boq_name}</span>
                </div>
                <strong>¥{lr.total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</strong>
              </div>
            ))}
          </div>
        </div>

        <AiInsightPanel
          projectId={projectId}
          contextType="calc"
          contextData={{
            line_count: calcResult.line_results.length,
            total_direct: calcResult.total_direct,
            total_management: calcResult.total_management,
            total_profit: calcResult.total_profit,
            total_tax: calcResult.total_tax,
            grand_total: calcResult.grand_total,
            direct_ratio: calcResult.grand_total > 0 ? Math.round(calcResult.total_direct / calcResult.grand_total * 100) : 0,
          }}
          title="AI 计算分析"
          fallback={`已完成 ${calcResult.line_results.length} 个清单项计价，合计 ¥${calcResult.grand_total.toLocaleString()}。直接费占比 ${calcResult.grand_total > 0 ? Math.round(calcResult.total_direct / calcResult.grand_total * 100) : 0}%。`}
          triggerKey={`calc-${calcResult.grand_total}`}
        />
      </div>
    );
  }

  function renderStep4() {
    if (valLoading || !validation) {
      return (
        <div className="wizard-loading">
          <span className="material-symbols-outlined wizard-loading-icon">verified</span>
          <div className="wizard-loading-text">AI 正在执行异常检测...</div>
          <div className="wizard-loading-sub">检查数据完整性与价格合理性</div>
        </div>
      );
    }

    return (
      <div className="wizard-content-split">
        <div className="wizard-main">
          <h3 className="wizard-section-title">校验结果</h3>
          <div className="wizard-stat-grid">
            <div className="wizard-stat-card">
              <div className="wizard-stat-value">{validation.total_issues}</div>
              <div className="wizard-stat-label">问题总数</div>
            </div>
            <div className="wizard-stat-card red">
              <div className="wizard-stat-value">{validation.errors}</div>
              <div className="wizard-stat-label">错误</div>
            </div>
            <div className="wizard-stat-card orange">
              <div className="wizard-stat-value">{validation.warnings}</div>
              <div className="wizard-stat-label">警告</div>
            </div>
          </div>

          {validation.total_issues === 0 ? (
            <div style={{ textAlign: "center", padding: 32 }}>
              <CheckCircleOutlined style={{ fontSize: 48, color: "#22c55e" }} />
              <div style={{ fontSize: 16, fontWeight: 600, color: "#22c55e", marginTop: 12 }}>校验通过，无异常</div>
              <div style={{ color: "var(--text-secondary)", marginTop: 4 }}>所有检查规则均已通过</div>
            </div>
          ) : (
            <div className="wizard-item-list" style={{ marginTop: 16 }}>
              {validation.issues.map((issue: ValidationIssue, i: number) => (
                <div key={i} className="wizard-issue-row">
                  <Tag color={issue.severity === "error" ? "red" : "orange"}>
                    {issue.severity === "error" ? "错误" : "警告"}
                  </Tag>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{issue.message}</div>
                    {issue.suggestion && (
                      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                        建议: {issue.suggestion}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <AiInsightPanel
          projectId={projectId}
          contextType="validation"
          contextData={{
            total_issues: validation.total_issues,
            errors: validation.errors,
            warnings: validation.warnings,
            issues: validation.issues.slice(0, 5).map((i) => ({
              severity: i.severity,
              message: i.message,
              suggestion: i.suggestion,
            })),
          }}
          title="AI 检测报告"
          fallback={validation.total_issues === 0
            ? "所有校验规则通过，组价流程已完成，可以安全提交。"
            : `检测发现 ${validation.errors} 个错误、${validation.warnings} 个警告。建议优先修复错误项。`
          }
          triggerKey={`val-${validation.total_issues}`}
        />
      </div>
    );
  }

  // ─── Footer Actions ──────────────────────────────────────────

  function renderFooterActions() {
    switch (step) {
      case 0:
        return (
          <>
            {unboundRows.length === 0 ? (
              <button className="btn-primary" onClick={runCalc}>
                跳过匹配，直接计算 <span className="material-symbols-outlined">arrow_forward</span>
              </button>
            ) : (
              <button className="btn-primary" onClick={startMatching}>
                开始智能匹配 ({unboundRows.length} 项) <span className="material-symbols-outlined">arrow_forward</span>
              </button>
            )}
          </>
        );
      case 1: {
        const current = matchItems[matchIdx];
        const allDone = matchDoneCount === matchItems.length;
        const canBatchApply = matchItems.some((m) => m.status === "ready" && !!m.chosen);
        return (
          <>
            {canBatchApply && (
              <button className="btn-secondary" onClick={handleBatchMatchAccept} disabled={matchApplyAllLoading}>
                {matchApplyAllLoading ? "批量处理中..." : "一键批量确认可选项"}
              </button>
            )}
            {current && current.status === "ready" && (
              <>
                <button className="btn-secondary" onClick={() => handleMatchSkip(matchIdx)}>
                  跳过
                </button>
                <button className="btn-primary" onClick={() => handleMatchAccept(matchIdx)} disabled={!current.chosen}>
                  <span className="material-symbols-outlined">check</span> 确认绑定
                </button>
              </>
            )}
            {allDone && (
              <button className="btn-primary" onClick={runCalc}>
                进入计算 <span className="material-symbols-outlined">arrow_forward</span>
              </button>
            )}
          </>
        );
      }
      case 2:
        return calcResult ? (
          <button className="btn-primary" onClick={runValidation}>
            执行异常检测 <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        ) : null;
      case 3:
        return (
          <button className="btn-primary" onClick={handleFinish}>
            <span className="material-symbols-outlined">check_circle</span> 完成组价
          </button>
        );
    }
  }
}
