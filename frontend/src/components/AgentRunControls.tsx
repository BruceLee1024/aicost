/**
 * AgentRunControls — Sprint 9 Phase 1.1
 *
 * Compact toolbar that shows the current state of a useAgentStream() run:
 *   - status pill (idle / running / retrying / done / error / cancelled)
 *   - elapsed clock
 *   - tool-call counter
 *   - Cancel button while running
 *   - Retry button when failed
 */

import { Button, Tooltip } from "antd";
import {
  StopOutlined,
  ReloadOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import type { StreamState } from "../hooks/useAgentStream";

interface Props {
  state: StreamState;
  elapsed: number;
  toolCallCount: number;
  retryCount: number;
  error?: string;
  onCancel?: () => void;
  onRetry?: () => void;
}

const STATE_LABEL: Record<StreamState, string> = {
  idle: "待机",
  running: "运行中",
  retrying: "重试中",
  done: "已完成",
  error: "失败",
  cancelled: "已取消",
};

const STATE_ICON: Record<StreamState, React.ReactNode> = {
  idle: <ClockCircleOutlined />,
  running: <LoadingOutlined spin />,
  retrying: <LoadingOutlined spin />,
  done: <CheckCircleOutlined />,
  error: <ExclamationCircleOutlined />,
  cancelled: <StopOutlined />,
};

export default function AgentRunControls({
  state,
  elapsed,
  toolCallCount,
  retryCount,
  error,
  onCancel,
  onRetry,
}: Props) {
  if (state === "idle") return null;
  const isRunning = state === "running" || state === "retrying";

  return (
    <>
      <div className="agent-run-controls">
        <span className={`agent-run-status agent-run-status-${state}`}>
          {STATE_ICON[state]}
          <span>{STATE_LABEL[state]}</span>
          {state === "retrying" && retryCount > 0 && <span>({retryCount})</span>}
        </span>

        <Tooltip title="累计耗时">
          <span className="agent-run-elapsed">
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            {elapsed}s
          </span>
        </Tooltip>

        {toolCallCount > 0 && (
          <Tooltip title="工具调用次数">
            <span className="agent-run-elapsed">
              <ToolOutlined style={{ marginRight: 4 }} />
              {toolCallCount}
            </span>
          </Tooltip>
        )}

        <span className="agent-run-spacer" />

        {isRunning && onCancel && (
          <Button size="small" icon={<StopOutlined />} onClick={onCancel} danger>
            取消
          </Button>
        )}
        {state === "error" && onRetry && (
          <Button
            size="small"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={onRetry}
          >
            重试
          </Button>
        )}
      </div>

      {state === "error" && error && (
        <div className="agent-error-banner">
          <ExclamationCircleOutlined style={{ marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Agent 运行失败</div>
            <div style={{ opacity: 0.85 }}>{error}</div>
          </div>
        </div>
      )}
    </>
  );
}
