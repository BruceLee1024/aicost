import { useEffect, useRef, useState } from "react";
import {
  Button, Input, Select, Spin, Switch, Tag, Collapse, message, Progress, Tooltip,
  Skeleton, Empty, Alert,
} from "antd";
import { BizTable } from "../components/BizTable";
import {
  RobotOutlined, SendOutlined, ThunderboltOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined, InfoCircleOutlined,
  ExperimentOutlined, AuditOutlined, DollarOutlined,
  BarChartOutlined, ApiOutlined, ReloadOutlined,
  DeleteOutlined, WarningOutlined, SearchOutlined,
  DatabaseOutlined, BookOutlined, SaveOutlined,
} from "@ant-design/icons";
import type {
  AgentStep, Project, PipelineResponse, BoqItem,
  CostStatsResponse,
} from "../api";
import { api } from "../api";
import MemoryPanel from "../components/MemoryPanel";
import SkillsPanel from "../components/SkillsPanel";

// ─── Agent name labels ──────────────────────────────────────────

const AGENT_LABELS: Record<string, string> = {
  delegate_valuation: "智能组价",
  delegate_validation: "数据审核",
  delegate_query: "数据查询",
  delegate_insight: "分析洞察",
  delegate_quota_match: "定额匹配",
  delegate_batch_review: "批量审查",
  delegate_boq_generate: "清单生成",
  delegate_rate_suggestion: "费率建议",
  delegate_chat: "项目问答",
  get_project_stats: "项目统计",
  get_divisions_summary: "分部汇总",
  list_unbound_items: "未绑定项",
  valuation_agent: "智能组价",
  validation_agent: "数据审核",
  query_agent: "数据查询",
  insight_agent: "分析洞察",
  quota_match_agent: "定额匹配",
  batch_review_agent: "批量审查",
  boq_agent: "清单生成",
  rate_suggestion_agent: "费率建议",
  chat_agent: "项目问答",
  orchestrator: "总调度",
};

const STAGE_ICONS: Record<string, React.ReactNode> = {
  quota_match_agent: <ApiOutlined />,
  valuation_agent: <DollarOutlined />,
  validation_agent: <AuditOutlined />,
  batch_review_agent: <AuditOutlined />,
  insight_agent: <BarChartOutlined />,
};

// ─── Smart Tool Result Renderer ──────────────────────────────────

function tryParseJson(s: string): unknown | null {
  try { return JSON.parse(s); } catch { return null; }
}

function renderToolResultSmart(raw: string): React.ReactNode {
  const parsed = tryParseJson(raw);
  if (!parsed || typeof parsed !== "object") {
    // Plain text fallback
    return <pre className="orch-tool-result">{raw.length > 800 ? raw.slice(0, 800) + "..." : raw}</pre>;
  }

  const obj = parsed as Record<string, unknown>;

  // ── Unbound items list ──
  if (Array.isArray(obj.unbound_items)) {
    const items = obj.unbound_items as Array<Record<string, unknown>>;
    return (
      <div className="orch-result-card">
        <div className="orch-result-header">
          <WarningOutlined style={{ color: "#faad14" }} />
          <span>未绑定项汇总 ({items.length} 项)</span>
        </div>
        <BizTable
          showIndex
          dataSource={items}
          rowKey={(r: any) => String(r.id || r.code)}
          pagination={items.length > 10 ? { pageSize: 10, size: "small" } : false}
          columns={[
            { title: "编码", dataIndex: "code", width: 80 },
            { title: "名称", dataIndex: "name", ellipsis: true },
            { title: "单位", dataIndex: "unit", width: 60, align: "center" as const },
            { title: "工程量", dataIndex: "quantity", width: 80, align: "right" as const,
              render: (v: number) => v?.toFixed?.(1) ?? v },
            { title: "分部", dataIndex: "division", width: 120,
              render: (v: string) => <Tag>{v}</Tag> },
          ]}
        />
      </div>
    );
  }

  // ── Agent delegation result ──
  if (obj.agent && obj.answer !== undefined) {
    const success = obj.success as boolean;
    return (
      <div className="orch-result-card">
        <div className="orch-result-header">
          {success
            ? <CheckCircleOutlined style={{ color: "#52c41a" }} />
            : <CloseCircleOutlined style={{ color: "#ff4d4f" }} />}
          <Tag color={success ? "green" : "red"}>{AGENT_LABELS[String(obj.agent)] || obj.agent}</Tag>
          {obj.tool_calls_made != null && (
            <span style={{ color: "#94a3b8", fontSize: 12 }}>{String(obj.tool_calls_made)} 次调用</span>
          )}
        </div>
        <div className="orch-result-answer">{String(obj.answer)}</div>
        {obj.error && <div style={{ color: "#ff4d4f", fontSize: 12, marginTop: 4 }}>错误: {String(obj.error)}</div>}
      </div>
    );
  }

  // ── Bind / unbind result ──
  if (obj.action && (obj.action === "created" || obj.action === "updated" || obj.action === "deleted")) {
    return (
      <div className="orch-result-card">
        <div className="orch-result-header">
          <CheckCircleOutlined style={{ color: "#52c41a" }} />
          <Tag color="green">{String(obj.action)}</Tag>
          {obj.quota_code && <Tag color="blue">{String(obj.quota_code)}</Tag>}
        </div>
        <div style={{ fontSize: 13, color: "#e2e8f0" }}>{String(obj.message || obj.quota_name || "")}</div>
      </div>
    );
  }

  // ── Stats / summary objects ──
  if (obj.total_items != null || obj.bound_count != null || obj.total != null) {
    const entries = Object.entries(obj).filter(([, v]) => typeof v !== "object");
    return (
      <div className="orch-result-card">
        <div className="orch-result-stats">
          {entries.map(([k, v]) => (
            <div key={k} className="orch-stat-item">
              <span className="orch-stat-label">{k}</span>
              <span className="orch-stat-value">{String(v)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Error ──
  if (obj.error) {
    return (
      <div className="orch-result-card" style={{ borderColor: "rgba(255,77,79,0.3)" }}>
        <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
        <span style={{ color: "#ff4d4f", marginLeft: 8 }}>{String(obj.error)}</span>
      </div>
    );
  }

  // ── Generic JSON pretty-print ──
  const pretty = JSON.stringify(parsed, null, 2);
  return <pre className="orch-tool-result">{pretty.length > 1200 ? pretty.slice(0, 1200) + "\n..." : pretty}</pre>;
}

// ─── Orchestrator Panel ─────────────────────────────────────────

interface ConvTurn {
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  error?: string | null;
  savedMemories?: string[];
  timestamp: number;
}

function OrchestratorPanel({ projectId }: { projectId: number }) {
  const [conversation, setConversation] = useState<ConvTurn[]>([]);
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([]);
  const [running, setRunning] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [connError, setConnError] = useState(false);
  const [autoSave, setAutoSave] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Reset conversation when switching projects
  useEffect(() => {
    setConversation([]);
    setCurrentSteps([]);
    setInstruction("");
    setConnError(false);
  }, [projectId]);

  // Auto-scroll to bottom on new steps / turns
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation, currentSteps, running]);

  const handleNewChat = () => {
    if (running) return;
    setConversation([]);
    setCurrentSteps([]);
    setInstruction("");
    setConnError(false);
  };

  const handleRun = async () => {
    if (!instruction.trim()) { message.warning("请输入任务指令"); return; }
    if (running) return;

    const userTurn: ConvTurn = {
      role: "user",
      content: instruction.trim(),
      timestamp: Date.now(),
    };
    // Snapshot of history to send to backend (does NOT include the current user turn;
    // backend appends the new instruction itself).
    const historyForApi = conversation
      .filter((t) => !!t.content)
      .map((t) => ({ role: t.role, content: t.content }));

    setConversation((prev) => [...prev, userTurn]);
    setInstruction("");
    setCurrentSteps([]);
    setConnError(false);
    setRunning(true);

    const collected: AgentStep[] = [];
    let finalAnswer = "";
    let finalError: string | null = null;
    let finalSavedMemories: string[] = [];

    try {
      await api.orchestrateStream(
        projectId,
        userTurn.content,
        (step) => {
          if (step.type === "done") {
            if (step.error) finalError = step.error;
            if (step.answer) finalAnswer = step.answer;
            if (step.auto_saved_memories && step.auto_saved_memories.length > 0) {
              finalSavedMemories = step.auto_saved_memories;
            }
          } else {
            // Merge consecutive streaming "thinking" deltas into a single step
            // so a sentence streamed token-by-token doesn't render as many rows.
            if (step.type === "thinking") {
              const last = collected[collected.length - 1];
              if (last && last.type === "thinking") {
                last.content = (last.content || "") + (step.content || "");
                setCurrentSteps((prev) => {
                  const next = prev.slice();
                  const lastIdx = next.length - 1;
                  if (lastIdx >= 0 && next[lastIdx].type === "thinking") {
                    next[lastIdx] = { ...next[lastIdx], content: last.content };
                    return next;
                  }
                  return [...prev, step];
                });
              } else {
                collected.push({ ...step });
                setCurrentSteps((prev) => [...prev, { ...step }]);
              }
            } else {
              collected.push(step);
              setCurrentSteps((prev) => [...prev, step]);
              if (step.type === "answer" && step.content) {
                finalAnswer = step.content;
              }
            }
          }
        },
        {
          auto_save_memory: autoSave,
          conversation_history: historyForApi,
        },
      );

      const assistantTurn: ConvTurn = {
        role: "assistant",
        content: finalAnswer || (finalError ? `执行失败: ${finalError}` : "任务完成"),
        steps: collected,
        error: finalError,
        savedMemories: finalSavedMemories,
        timestamp: Date.now(),
      };
      setConversation((prev) => [...prev, assistantTurn]);
      setCurrentSteps([]);
    } catch (err) {
      setConnError(true);
      const assistantTurn: ConvTurn = {
        role: "assistant",
        content: `连接失败: ${String(err)}`,
        steps: collected,
        error: String(err),
        timestamp: Date.now(),
      };
      setConversation((prev) => [...prev, assistantTurn]);
      setCurrentSteps([]);
    } finally {
      setRunning(false);
    }
  };

  const quickActions = [
    { label: "全项目审查", instruction: "请对整个项目进行全面审查，检查所有绑定问题" },
    { label: "费用分析", instruction: "分析项目费用结构，找出异常和优化点" },
    { label: "未绑定项处理", instruction: "查找所有未绑定定额的清单项，并给出处理建议" },
    { label: "项目概况", instruction: "获取项目的整体概况和关键统计数据" },
  ];

  const renderStep = (step: AgentStep, i: number) => (
    <div key={i} className={`orch-step orch-step-${step.type}`}>
      {step.type === "thinking" && (
        <div className="orch-thinking">
          <RobotOutlined className="orch-step-icon" />
          <span>{step.content}</span>
        </div>
      )}
      {step.type === "tool_call" && (
        <div className="orch-delegation">
          <ThunderboltOutlined className="orch-step-icon" style={{ color: "#faad14" }} />
          <span>
            调用 <Tag color="blue">{AGENT_LABELS[step.tool_name] || step.tool_name}</Tag>
          </span>
        </div>
      )}
      {step.type === "tool_result" && (
        <Collapse
          size="small"
          className="orch-tool-collapse"
          items={[{
            key: "1",
            label: (
              <span className="orch-tool-label">
                <CheckCircleOutlined style={{ color: "#52c41a" }} />
                <span>{AGENT_LABELS[step.tool_name] || step.tool_name} 返回结果</span>
              </span>
            ),
            children: renderToolResultSmart(step.tool_result),
          }]}
        />
      )}
    </div>
  );

  const renderAssistantTurn = (turn: ConvTurn, idx: number) => {
    const stepsBeforeAnswer = (turn.steps || []).filter((s) => s.type !== "answer");
    const toolCallCount = (turn.steps || []).filter((s) => s.type === "tool_result").length;
    return (
      <div className="chat-row chat-row-assistant" key={`a-${idx}`}>
        <div className="chat-avatar chat-avatar-assistant">
          <RobotOutlined />
        </div>
        <div className="chat-bubble chat-bubble-assistant">
          {stepsBeforeAnswer.length > 0 && (
            <div className="chat-steps">
              {stepsBeforeAnswer.map(renderStep)}
            </div>
          )}
          <div className={`chat-answer ${turn.error ? "chat-answer-error" : ""}`}>
            {turn.error
              ? <><CloseCircleOutlined style={{ color: "#ff4d4f" }} /> <span>{turn.content}</span></>
              : <span>{turn.content}</span>
            }
          </div>
          {toolCallCount > 0 && (
            <div className="chat-meta">
              <span>{toolCallCount} 次工具调用</span>
            </div>
          )}
          {turn.savedMemories && turn.savedMemories.length > 0 && (
            <div className="chat-saved-memories">
              <SaveOutlined style={{ color: "#52c41a" }} />
              <span>已沉淀 {turn.savedMemories.length} 条记忆:</span>
              {turn.savedMemories.map((k) => (
                <Tag key={k} color="green" style={{ marginInlineEnd: 0 }}>{k}</Tag>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderUserTurn = (turn: ConvTurn, idx: number) => (
    <div className="chat-row chat-row-user" key={`u-${idx}`}>
      <div className="chat-bubble chat-bubble-user">
        {turn.content}
      </div>
      <div className="chat-avatar chat-avatar-user">你</div>
    </div>
  );

  const isEmpty = conversation.length === 0 && !running;

  return (
    <div className="orch-panel">
      <div className="orch-panel-header">
        <RobotOutlined style={{ fontSize: 20, color: "#4096ff" }} />
        <span className="orch-panel-title">AI 调度中心</span>
        <Tag color="purple">Orchestrator</Tag>
        {conversation.length > 0 && (
          <Tag color="default">{Math.ceil(conversation.length / 2)} 轮</Tag>
        )}
        <div style={{ flex: 1 }} />
        <Tooltip title="运行结束后，LLM 会自动从本次对话提取关键事实保存到记忆库（会覆盖服务端 AI_AUTO_SAVE_MEMORY 默认值）">
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "2px 10px",
              borderRadius: 6,
              background: autoSave ? "rgba(82,196,26,0.12)" : "transparent",
              border: "1px solid rgba(148,163,184,0.2)",
              fontSize: 12,
            }}
          >
            <SaveOutlined style={{ color: autoSave ? "#52c41a" : "#94a3b8" }} />
            <span style={{ color: autoSave ? "#52c41a" : "#94a3b8" }}>自动沉淀</span>
            <Switch
              size="small"
              checked={autoSave}
              onChange={setAutoSave}
              disabled={running}
            />
          </span>
        </Tooltip>
        {conversation.length > 0 && (
          <Button size="small" icon={<DeleteOutlined />} onClick={handleNewChat} disabled={running}>
            新对话
          </Button>
        )}
      </div>

      {isEmpty && (
        <div className="orch-quick-actions">
          {quickActions.map((qa) => (
            <button
              key={qa.label}
              className="orch-quick-btn"
              onClick={() => { setInstruction(qa.instruction); }}
              disabled={running}
            >
              <ThunderboltOutlined />
              <span>{qa.label}</span>
            </button>
          ))}
        </div>
      )}

      <div className="orch-chat" ref={scrollRef}>
        {isEmpty && (
          <div className="orch-empty">
            <RobotOutlined style={{ fontSize: 48, opacity: 0.15 }} />
            <p>输入任务指令，Orchestrator 将自动分解并委派给 9 个专业子 Agent 协同完成</p>
            <p style={{ fontSize: 12, opacity: 0.6, marginTop: -4 }}>
              支持多轮对话 · 上下文自动保留
            </p>
          </div>
        )}
        {conversation.map((turn, i) =>
          turn.role === "user" ? renderUserTurn(turn, i) : renderAssistantTurn(turn, i)
        )}
        {running && (
          <div className="chat-row chat-row-assistant">
            <div className="chat-avatar chat-avatar-assistant">
              <RobotOutlined />
            </div>
            <div className="chat-bubble chat-bubble-assistant">
              {currentSteps.length > 0 && (
                <div className="chat-steps">
                  {currentSteps.filter((s) => s.type !== "answer").map(renderStep)}
                </div>
              )}
              <div className="chat-thinking-indicator">
                <Spin size="small" />
                <span>Orchestrator 正在协调子 Agent...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {connError && (
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          message="连接失败"
          description="无法连接到 Orchestrator 服务。请检查后端服务是否启动，然后重试。"
          style={{ margin: "0 20px 12px" }}
        />
      )}

      <div className="orch-input-bar">
        <Input.TextArea
          placeholder={conversation.length === 0
            ? "输入任务指令，Orchestrator 将自动分解并委派给专业子 Agent 执行..."
            : "继续对话..."}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleRun(); } }}
          disabled={running}
          autoSize={{ minRows: 2, maxRows: 4 }}
        />
        <Button
          type="primary"
          size="large"
          icon={running ? <Spin size="small" /> : <SendOutlined />}
          onClick={handleRun}
          disabled={running || !instruction.trim()}
          className="orch-send-btn"
        >
          {running ? "执行中..." : "发送"}
        </Button>
      </div>
    </div>
  );
}

// ─── Pipeline Panel ─────────────────────────────────────────────

function PipelinePanel({ projectId }: { projectId: number }) {
  const [pipelineType, setPipelineType] = useState<"audit" | "pricing">("audit");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [boqItems, setBoqItems] = useState<BoqItem[]>([]);
  const [selectedBoqItem, setSelectedBoqItem] = useState<number | null>(null);
  const [loadingBoq, setLoadingBoq] = useState(false);

  useEffect(() => {
    if (pipelineType === "pricing") {
      setLoadingBoq(true);
      api.listBoqItems(projectId).then((items) => {
        setBoqItems(items);
        if (items.length > 0 && !selectedBoqItem) setSelectedBoqItem(items[0].id);
      }).catch(() => {
        setBoqItems([]);
      }).finally(() => setLoadingBoq(false));
    }
  }, [pipelineType, projectId]);

  const handleRun = async () => {
    setRunning(true);
    setResult(null);
    setPipelineError(null);
    try {
      if (pipelineType === "audit") {
        const res = await api.runAuditPipeline(projectId);
        setResult(res);
      } else if (selectedBoqItem) {
        const res = await api.runPricingPipeline(projectId, selectedBoqItem);
        setResult(res);
      } else {
        message.warning("请先选择一个清单项");
        setRunning(false);
        return;
      }
    } catch (err) {
      setPipelineError(String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="pipeline-panel">
      <div className="pipeline-panel-header">
        <ExperimentOutlined style={{ fontSize: 20, color: "#722ed1" }} />
        <span className="pipeline-panel-title">多 Agent 流水线</span>
        <Tag color="purple">Pipeline</Tag>
      </div>

      <div className="pipeline-controls">
        <Select
          value={pipelineType}
          onChange={(v) => { setPipelineType(v); setResult(null); setPipelineError(null); }}
          style={{ width: 200 }}
          options={[
            { value: "audit", label: "项目审计 Pipeline (3阶段)" },
            { value: "pricing", label: "定价 Pipeline (3阶段)" },
          ]}
          disabled={running}
        />
        {pipelineType === "pricing" && (
          <Select
            value={selectedBoqItem}
            onChange={setSelectedBoqItem}
            style={{ width: 300 }}
            placeholder="选择清单项..."
            loading={loadingBoq}
            showSearch
            optionFilterProp="label"
            options={boqItems.map((b) => ({
              value: b.id,
              label: `${b.code} — ${b.name} (${b.unit})`,
            }))}
            disabled={running}
            notFoundContent={loadingBoq ? <Spin size="small" /> : <Empty description="无清单项" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          />
        )}
        <Button
          type="primary"
          icon={running ? <Spin size="small" /> : <ThunderboltOutlined />}
          onClick={handleRun}
          disabled={running || (pipelineType === "pricing" && !selectedBoqItem)}
        >
          {running ? "执行中..." : "启动 Pipeline"}
        </Button>
      </div>

      {!running && !result && !pipelineError && (
        <div className="pipeline-empty">
          <ExperimentOutlined style={{ fontSize: 48, opacity: 0.12 }} />
          <p>选择 Pipeline 类型并点击「启动」，多个 Agent 将依次执行协作</p>
          <div className="pipeline-stages-preview">
            {pipelineType === "audit" ? (
              <div className="pipeline-preview-flow">
                <span className="pipeline-preview-node"><AuditOutlined /> 批量审查</span>
                <span className="pipeline-preview-arrow">→</span>
                <span className="pipeline-preview-node"><BarChartOutlined /> 分析洞察</span>
                <span className="pipeline-preview-arrow">→</span>
                <span className="pipeline-preview-node"><CheckCircleOutlined /> 数据审核</span>
              </div>
            ) : (
              <div className="pipeline-preview-flow">
                <span className="pipeline-preview-node"><SearchOutlined /> 定额匹配</span>
                <span className="pipeline-preview-arrow">→</span>
                <span className="pipeline-preview-node"><DollarOutlined /> 智能组价</span>
                <span className="pipeline-preview-arrow">→</span>
                <span className="pipeline-preview-node"><AuditOutlined /> 数据审核</span>
              </div>
            )}
          </div>
        </div>
      )}

      {running && (
        <div className="pipeline-running">
          <Spin size="large" />
          <p>Pipeline 正在依次执行各阶段，请稍候...</p>
          <div className="pipeline-running-tip">通常需要 10-30 秒，取决于项目规模</div>
        </div>
      )}

      {pipelineError && !running && (
        <Alert
          type="error"
          showIcon
          message="Pipeline 执行失败"
          description={pipelineError}
          action={<Button size="small" onClick={handleRun}>重试</Button>}
          style={{ margin: "16px 20px" }}
        />
      )}

      {result && (
        <div className="pipeline-result">
          <div className="pipeline-summary">
            <div className={`pipeline-status ${result.success ? "pipeline-success" : "pipeline-failed"}`}>
              {result.success
                ? <><CheckCircleOutlined /> 全部完成</>
                : <><CloseCircleOutlined /> 执行失败</>}
            </div>
            <div className="pipeline-meta">
              <span><ClockCircleOutlined /> {result.total_duration_s.toFixed(1)}s</span>
              <span>{result.stages.length} 个阶段</span>
            </div>
          </div>

          <div className="pipeline-stages">
            {result.stages.map((stage) => (
              <div
                key={stage.index}
                className={`pipeline-stage ${stage.success ? "stage-ok" : "stage-fail"}`}
              >
                <div className="stage-header">
                  <div className="stage-index">{stage.index + 1}</div>
                  <div className="stage-info">
                    <div className="stage-name">
                      {STAGE_ICONS[stage.agent] || <RobotOutlined />}
                      <span>{AGENT_LABELS[stage.agent] || stage.agent}</span>
                    </div>
                    <div className="stage-meta">
                      <Tag color={stage.success ? "green" : "red"}>
                        {stage.success ? "成功" : "失败"}
                      </Tag>
                      <span>{stage.duration_s.toFixed(1)}s</span>
                      <span>{stage.tool_calls} 次工具调用</span>
                    </div>
                  </div>
                </div>
                <Collapse
                  size="small"
                  items={[{
                    key: "1",
                    label: "查看结果",
                    children: <pre className="stage-answer">{stage.answer}</pre>,
                  }]}
                />
              </div>
            ))}
          </div>

          {result.final_answer && (
            <div className="pipeline-final-answer">
              <h4>最终结论</h4>
              <div className="pipeline-final-text">{result.final_answer}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Cost Dashboard Panel ───────────────────────────────────────

function CostDashboard() {
  const [stats, setStats] = useState<CostStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(7);

  const loadStats = async () => {
    setLoading(true);
    try {
      const res = await api.getTraceStats({ days });
      setStats(res);
    } catch {
      message.error("加载成本统计失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadStats(); }, [days]);

  return (
    <div className="cost-dashboard">
      <div className="cost-dashboard-header">
        <BarChartOutlined style={{ fontSize: 20, color: "#13c2c2" }} />
        <span className="cost-dashboard-title">成本看板</span>
        <Tag color="cyan">Observability</Tag>
        <div style={{ flex: 1 }} />
        <Select
          value={days}
          onChange={setDays}
          style={{ width: 120 }}
          options={[
            { value: 1, label: "最近 1 天" },
            { value: 7, label: "最近 7 天" },
            { value: 30, label: "最近 30 天" },
          ]}
        />
        <Button icon={<ReloadOutlined />} onClick={loadStats} loading={loading} />
      </div>

      {loading && !stats && (
        <div className="cost-skeleton">
          <div className="cost-cards">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="cost-card">
                <Skeleton.Input active size="small" style={{ width: 80, marginBottom: 8 }} />
                <Skeleton.Input active size="large" style={{ width: 100, marginBottom: 4 }} />
                <Skeleton.Input active size="small" style={{ width: 120 }} />
              </div>
            ))}
          </div>
          <div style={{ padding: "0 20px" }}>
            <Skeleton active paragraph={{ rows: 4 }} />
          </div>
        </div>
      )}

      {!loading && stats && stats.total_traces === 0 && (
        <div className="cost-empty">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无 Agent 调用记录"
          >
            <p style={{ color: "var(--text-muted)", fontSize: 12 }}>
              使用 Orchestrator 或 Pipeline 执行任务后，成本数据将自动记录在这里
            </p>
          </Empty>
        </div>
      )}

      {stats && stats.total_traces > 0 && (
        <>
          <div className="cost-cards">
            <div className="cost-card">
              <div className="cost-card-label">总调用次数</div>
              <div className="cost-card-value">{stats.total_traces}</div>
              <div className="cost-card-sub">
                成功 {stats.successful_traces} / 失败 {stats.failed_traces}
              </div>
            </div>
            <div className="cost-card">
              <div className="cost-card-label">总 Token 消耗</div>
              <div className="cost-card-value">
                {stats.total_tokens > 1_000_000
                  ? `${(stats.total_tokens / 1_000_000).toFixed(1)}M`
                  : stats.total_tokens > 1000
                    ? `${(stats.total_tokens / 1000).toFixed(1)}K`
                    : stats.total_tokens}
              </div>
              <div className="cost-card-sub">
                输入 {(stats.total_input_tokens / 1000).toFixed(0)}K / 输出 {(stats.total_output_tokens / 1000).toFixed(0)}K
              </div>
            </div>
            <div className="cost-card">
              <div className="cost-card-label">预估成本</div>
              <div className="cost-card-value">
                ${(stats.total_cost_cents / 100).toFixed(2)}
              </div>
              <div className="cost-card-sub">{stats.total_cost_cents.toFixed(1)} 美分</div>
            </div>
            <div className="cost-card">
              <div className="cost-card-label">平均延迟</div>
              <div className="cost-card-value">
                {stats.avg_duration_ms > 1000
                  ? `${(stats.avg_duration_ms / 1000).toFixed(1)}s`
                  : `${stats.avg_duration_ms}ms`}
              </div>
              <div className="cost-card-sub">{stats.total_tool_calls} 次工具调用</div>
            </div>
          </div>

          {stats.by_agent.length > 0 && (
            <div className="cost-section">
              <h4>按 Agent 分布</h4>
              <BizTable
                dataSource={stats.by_agent}
                rowKey="agent_name"
                pagination={false}
                columns={[
                  {
                    title: "Agent",
                    dataIndex: "agent_name",
                    render: (name: string) => (
                      <span>
                        <RobotOutlined style={{ marginRight: 6 }} />
                        {AGENT_LABELS[name] || name}
                      </span>
                    ),
                  },
                  { title: "调用次数", dataIndex: "trace_count", width: 90 },
                  {
                    title: "Token",
                    dataIndex: "total_tokens",
                    width: 100,
                    render: (v: number) => v > 1000 ? `${(v / 1000).toFixed(1)}K` : v,
                  },
                  {
                    title: "成本",
                    dataIndex: "total_cost_cents",
                    width: 90,
                    render: (v: number) => `$${(v / 100).toFixed(3)}`,
                  },
                  {
                    title: "成功率",
                    dataIndex: "success_rate",
                    width: 100,
                    render: (v: number) => (
                      <Progress
                        percent={Math.round(v * 100)}
                        size="small"
                        status={v >= 0.9 ? "success" : v >= 0.7 ? "normal" : "exception"}
                        style={{ width: 80 }}
                      />
                    ),
                  },
                  {
                    title: "平均延迟",
                    dataIndex: "avg_duration_ms",
                    width: 100,
                    render: (v: number) => v > 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`,
                  },
                ]}
              />
            </div>
          )}

          {stats.by_day.length > 0 && (
            <div className="cost-section">
              <h4>按日趋势</h4>
              <div className="cost-day-bars">
                {(() => {
                  const maxTokens = Math.max(...stats.by_day.map((x) => x.total_tokens), 1);
                  return stats.by_day.map((d) => (
                    <Tooltip key={d.date} title={`${d.date}: ${d.trace_count}次, ${d.total_tokens} tokens, $${(d.total_cost_cents/100).toFixed(3)}`}>
                      <div className="cost-day-bar">
                        <div
                          className="cost-day-fill"
                          style={{ height: `${Math.max(4, (d.total_tokens / maxTokens) * 80)}px` }}
                        />
                        <span className="cost-day-label">{d.date.slice(5)}</span>
                      </div>
                    </Tooltip>
                  ));
                })()}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────

export default function AICommandCenter() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"orchestrator" | "pipeline" | "memory" | "skills" | "cost">("orchestrator");
  const [loadingProjects, setLoadingProjects] = useState(true);

  useEffect(() => {
    setLoadingProjects(true);
    api.listProjects().then((res) => {
      setProjects(res.items);
      if (res.items.length > 0) setSelectedProject(res.items[0].id);
    }).catch(() => {
      message.error("加载项目列表失败");
    }).finally(() => setLoadingProjects(false));
  }, []);

  return (
    <div className="page-container ai-command-center">
      <div className="page-header">
        <div className="page-header-left">
          <span className="material-symbols-outlined" style={{ fontSize: 28 }}>smart_toy</span>
          <div>
            <h2>AI 调度中心</h2>
            <p>Orchestrator 多 Agent 协同 · Pipeline 流水线 · 成本看板</p>
          </div>
        </div>
        <div className="page-header-right">
          <Select
            value={selectedProject}
            onChange={setSelectedProject}
            style={{ width: 260 }}
            placeholder="选择项目"
            loading={loadingProjects}
            showSearch
            optionFilterProp="label"
            options={projects.map((p) => ({ value: p.id, label: `${p.name} (ID: ${p.id})` }))}
            notFoundContent={loadingProjects ? <Spin size="small" /> : <Empty description="无项目" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          />
        </div>
      </div>

      <div className="ai-cc-tabs">
        <button
          className={`ai-cc-tab ${activeTab === "orchestrator" ? "active" : ""}`}
          onClick={() => setActiveTab("orchestrator")}
        >
          <RobotOutlined />
          <span>Orchestrator</span>
        </button>
        <button
          className={`ai-cc-tab ${activeTab === "pipeline" ? "active" : ""}`}
          onClick={() => setActiveTab("pipeline")}
        >
          <ExperimentOutlined />
          <span>Pipeline</span>
        </button>
        <button
          className={`ai-cc-tab ${activeTab === "memory" ? "active" : ""}`}
          onClick={() => setActiveTab("memory")}
        >
          <DatabaseOutlined />
          <span>记忆库</span>
        </button>
        <button
          className={`ai-cc-tab ${activeTab === "skills" ? "active" : ""}`}
          onClick={() => setActiveTab("skills")}
        >
          <BookOutlined />
          <span>知识库</span>
        </button>
        <button
          className={`ai-cc-tab ${activeTab === "cost" ? "active" : ""}`}
          onClick={() => setActiveTab("cost")}
        >
          <BarChartOutlined />
          <span>成本看板</span>
        </button>
      </div>

      <div className="ai-cc-content">
        {!selectedProject && (activeTab === "orchestrator" || activeTab === "pipeline") ? (
          <div className="ai-cc-no-project">
            <InfoCircleOutlined style={{ fontSize: 48, opacity: 0.2 }} />
            <p>请先选择一个项目</p>
          </div>
        ) : (
          <>
            {activeTab === "orchestrator" && selectedProject && (
              <OrchestratorPanel projectId={selectedProject} />
            )}
            {activeTab === "pipeline" && selectedProject && (
              <PipelinePanel projectId={selectedProject} />
            )}
            {activeTab === "memory" && (
              <MemoryPanel projectId={selectedProject} />
            )}
            {activeTab === "skills" && <SkillsPanel />}
            {activeTab === "cost" && <CostDashboard />}
          </>
        )}
      </div>
    </div>
  );
}
