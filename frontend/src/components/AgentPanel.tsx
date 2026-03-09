import { useEffect, useRef, useState } from "react";
import { Button, Input, Spin, Tag, Collapse, message } from "antd";
import {
  RobotOutlined,
  SearchOutlined,
  LinkOutlined,
  CalculatorOutlined,
  DisconnectOutlined,
  UnorderedListOutlined,
  DollarOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { AgentStep, BoqItem } from "../api";
import { api } from "../api";

interface Props {
  projectId: number;
  boqItem: BoqItem;
  open: boolean;
  onClose: () => void;
  onBindingsChanged: () => void;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  search_quotas: <SearchOutlined />,
  get_quota_detail: <InfoCircleOutlined />,
  bind_quota: <LinkOutlined />,
  unbind_quota: <DisconnectOutlined />,
  list_current_bindings: <UnorderedListOutlined />,
  calculate_cost: <CalculatorOutlined />,
  get_material_prices: <DollarOutlined />,
};

const TOOL_LABELS: Record<string, string> = {
  search_quotas: "搜索定额",
  get_quota_detail: "查看定额详情",
  bind_quota: "绑定定额",
  unbind_quota: "解除绑定",
  list_current_bindings: "查看已绑定",
  calculate_cost: "计算费用",
  get_material_prices: "查询材料价",
};

function formatToolResult(result: string): React.ReactNode {
  try {
    const data = JSON.parse(result);
    if (data.error) {
      return <span className="agent-tool-error">{data.error}</span>;
    }
    if (data.results) {
      return (
        <div className="agent-tool-results">
          {data.results.length === 0 ? (
            <span className="agent-tool-empty">无匹配结果</span>
          ) : (
            <table className="agent-mini-table">
              <thead>
                <tr>
                  <th>编码</th>
                  <th>名称</th>
                  <th>单位</th>
                  <th>匹配度</th>
                </tr>
              </thead>
              <tbody>
                {data.results.slice(0, 5).map((r: Record<string, unknown>, i: number) => (
                  <tr key={i}>
                    <td><code>{String(r.quota_code ?? "")}</code></td>
                    <td>{String(r.name ?? "")}</td>
                    <td>{String(r.unit ?? "")}</td>
                    <td>
                      <Tag color={Number(r.relevance ?? 0) > 0.5 ? "green" : "orange"}>
                        {(Number(r.relevance ?? 0) * 100).toFixed(0)}%
                      </Tag>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      );
    }
    if (data.bindings) {
      return (
        <div className="agent-tool-results">
          {data.bindings.length === 0 ? (
            <span className="agent-tool-empty">暂无绑定</span>
          ) : (
            <table className="agent-mini-table">
              <thead>
                <tr>
                  <th>编码</th>
                  <th>名称</th>
                  <th>系数</th>
                </tr>
              </thead>
              <tbody>
                {data.bindings.map((b: Record<string, unknown>, i: number) => (
                  <tr key={i}>
                    <td><code>{String(b.quota_code ?? "")}</code></td>
                    <td>{String(b.quota_name ?? "")}</td>
                    <td>{String(b.coefficient ?? 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      );
    }
    if (data.action) {
      return (
        <span className="agent-tool-action">
          <CheckCircleOutlined style={{ color: "#52c41a", marginRight: 6 }} />
          {data.message}
        </span>
      );
    }
    if (data.total !== undefined) {
      return (
        <div className="agent-calc-result">
          <div className="agent-calc-row"><span>直接费</span><strong>¥{Number(data.direct_cost).toFixed(2)}</strong></div>
          <div className="agent-calc-row"><span>管理费</span><strong>¥{Number(data.management_fee).toFixed(2)}</strong></div>
          <div className="agent-calc-row"><span>利润</span><strong>¥{Number(data.profit).toFixed(2)}</strong></div>
          <div className="agent-calc-row"><span>规费</span><strong>¥{Number(data.regulatory_fee).toFixed(2)}</strong></div>
          <div className="agent-calc-row"><span>税金</span><strong>¥{Number(data.tax).toFixed(2)}</strong></div>
          <div className="agent-calc-row agent-calc-total"><span>合价</span><strong>¥{Number(data.total).toFixed(2)}</strong></div>
          <div className="agent-calc-row agent-calc-total"><span>综合单价</span><strong>¥{Number(data.unit_price).toFixed(2)}</strong></div>
        </div>
      );
    }
    return <pre className="agent-tool-json">{JSON.stringify(data, null, 2)}</pre>;
  } catch {
    return <span>{result}</span>;
  }
}

export default function AgentPanel({ projectId, boqItem, open, onClose, onBindingsChanged }: Props) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [running, setRunning] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [done, setDone] = useState(false);
  const [finalAnswer, setFinalAnswer] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps]);

  useEffect(() => {
    if (!open) {
      setSteps([]);
      setDone(false);
      setFinalAnswer("");
      setInstruction("");
    }
  }, [open, boqItem.id]);

  const handleRun = async () => {
    setRunning(true);
    setDone(false);
    setSteps([]);
    setFinalAnswer("");

    try {
      await api.agentValuateStream(projectId, boqItem.id, instruction, (step) => {
        if (step.type === "done") {
          setDone(true);
          setFinalAnswer(step.answer || "");
          if (step.bindings_changed) {
            onBindingsChanged();
          }
          if (step.error) {
            message.warning(`Agent 警告: ${step.error}`);
          }
        } else {
          setSteps((prev) => [...prev, step]);
        }
      });
    } catch (err) {
      message.error("Agent 连接失败");
    } finally {
      setRunning(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="agent-panel-backdrop" onClick={onClose} />
      <div className="agent-panel">
      <div className="agent-panel-header">
        <div className="agent-panel-title">
          <RobotOutlined style={{ fontSize: 18, color: "#4096ff" }} />
          <span>智能组价 Agent</span>
          <Tag color="blue">Tool Calling</Tag>
        </div>
        <button className="agent-panel-close" onClick={onClose}>×</button>
      </div>

      <div className="agent-boq-info">
        <div className="agent-boq-row">
          <Tag color="blue">{boqItem.code}</Tag>
          <strong>{boqItem.name}</strong>
        </div>
        <div className="agent-boq-row">
          <span>特征：{boqItem.characteristics || "—"}</span>
          <span>单位：{boqItem.unit}</span>
          <span>工程量：{boqItem.quantity}</span>
        </div>
      </div>

      <div className="agent-input-bar">
        <Input
          placeholder={'可选：补充说明，如"使用C30混凝土定额"、"需要加模板定额"'}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onPressEnter={handleRun}
          disabled={running}
          prefix={<ThunderboltOutlined />}
        />
        <Button
          type="primary"
          icon={running ? <Spin size="small" /> : <SendOutlined />}
          onClick={handleRun}
          disabled={running}
        >
          {running ? "推理中..." : "开始组价"}
        </Button>
      </div>

      <div className="agent-steps" ref={scrollRef}>
        {steps.length === 0 && !running && (
          <div className="agent-empty">
            <RobotOutlined style={{ fontSize: 40, opacity: 0.3 }} />
            <p>点击「开始组价」，Agent 将自动搜索定额、绑定并计算</p>
          </div>
        )}
        {steps.map((step, i) => (
          <div key={i} className={`agent-step agent-step-${step.type}`}>
            {step.type === "thinking" && (
              <div className="agent-thinking">
                <RobotOutlined className="agent-step-icon" />
                <span>{step.content}</span>
              </div>
            )}
            {step.type === "tool_result" && (
              <Collapse
                size="small"
                className="agent-tool-collapse"
                items={[
                  {
                    key: "1",
                    label: (
                      <span className="agent-tool-label">
                        {TOOL_ICONS[step.tool_name] || <InfoCircleOutlined />}
                        <span>{TOOL_LABELS[step.tool_name] || step.tool_name}</span>
                        {step.tool_args && Object.keys(step.tool_args).length > 0 && (
                          <code className="agent-tool-args-brief">
                            {Object.entries(step.tool_args)
                              .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
                              .join(", ")}
                          </code>
                        )}
                      </span>
                    ),
                    children: formatToolResult(step.tool_result),
                  },
                ]}
                defaultActiveKey={
                  ["bind_quota", "calculate_cost"].includes(step.tool_name) ? ["1"] : []
                }
              />
            )}
            {step.type === "answer" && (
              <div className="agent-answer">
                <CheckCircleOutlined className="agent-step-icon" style={{ color: "#52c41a" }} />
                <div className="agent-answer-text">{step.content}</div>
              </div>
            )}
          </div>
        ))}
        {running && (
          <div className="agent-step agent-step-loading">
            <Spin size="small" />
            <span>Agent 正在思考...</span>
          </div>
        )}
      </div>

      {done && finalAnswer && (
        <div className="agent-final">
          <CheckCircleOutlined style={{ color: "#52c41a" }} />
          <span>组价完成</span>
        </div>
      )}
    </div>
    </>
  );
}
