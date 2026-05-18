/**
 * AgentTimeline — Sprint 9 Phase 1.2
 *
 * Horizontal time-axis visualization of an agent run. Each tool_call segment
 * shows duration; thinking blocks show as compact pulses. Click a segment to
 * inspect its args/result.
 */

import { useMemo, useState } from "react";
import { Drawer, Empty, Tag, Tooltip } from "antd";
import {
  RobotOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import type { AgentStepEvent } from "../hooks/useAgentStream";

interface Props {
  steps: AgentStepEvent[];
  running: boolean;
  /** Optional friendly labels for tool names. */
  toolLabels?: Record<string, string>;
  /** Optional icons for tool names. */
  toolIcons?: Record<string, React.ReactNode>;
}

interface Segment {
  id: string;
  kind: "thinking" | "tool" | "answer";
  label: string;
  startMs: number;
  endMs: number;
  status: "running" | "success" | "error";
  detail: string;
  raw: AgentStepEvent;
}

function buildSegments(steps: AgentStepEvent[]): Segment[] {
  const segs: Segment[] = [];
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (s.type === "thinking") {
      const start = s._ts_start ?? Date.now();
      const next = steps[i + 1];
      const end = next?._ts_start ?? Date.now();
      segs.push({
        id: `thinking-${i}`,
        kind: "thinking",
        label: "思考",
        startMs: start,
        endMs: end,
        status: "success",
        detail: s.content || "",
        raw: s,
      });
    } else if (s.type === "tool_call") {
      // Find paired tool_result.
      const result = steps.find(
        (r, j) =>
          j > i &&
          r.type === "tool_result" &&
          (r._id ? r._id === s._id : r.tool_name === s.tool_name),
      );
      const start = s._ts_start ?? Date.now();
      const end = result?._ts_end ?? Date.now();
      const isErr =
        typeof result?.tool_result === "string" &&
        /"error"|"failed"/.test(result.tool_result);
      segs.push({
        id: s._id || `tool-${i}`,
        kind: "tool",
        label: s.tool_name || "tool",
        startMs: start,
        endMs: end,
        status: !result ? "running" : isErr ? "error" : "success",
        detail: result?.tool_result || JSON.stringify(s.tool_args ?? {}),
        raw: s,
      });
    } else if (s.type === "answer") {
      const start = s._ts_start ?? Date.now();
      segs.push({
        id: `answer-${i}`,
        kind: "answer",
        label: "结论",
        startMs: start,
        endMs: start + 200,
        status: "success",
        detail: s.content || "",
        raw: s,
      });
    }
  }
  return segs;
}

export default function AgentTimeline({
  steps,
  running,
  toolLabels = {},
  toolIcons = {},
}: Props) {
  const [active, setActive] = useState<Segment | null>(null);

  const segments = useMemo(() => buildSegments(steps), [steps]);

  const { minMs, totalMs } = useMemo(() => {
    if (segments.length === 0) return { minMs: 0, totalMs: 1 };
    const min = Math.min(...segments.map((s) => s.startMs));
    const max = Math.max(...segments.map((s) => s.endMs), running ? Date.now() : 0);
    return { minMs: min, totalMs: Math.max(max - min, 1) };
  }, [segments, running]);

  if (segments.length === 0) {
    return (
      <div className="agent-timeline-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={running ? "Agent 正在启动..." : "暂无运行记录"}
        />
      </div>
    );
  }

  return (
    <>
      <div className="agent-timeline">
        <div className="agent-timeline-track">
          {segments.map((seg) => {
            const left = ((seg.startMs - minMs) / totalMs) * 100;
            const width = Math.max(((seg.endMs - seg.startMs) / totalMs) * 100, 1.5);
            const dur = ((seg.endMs - seg.startMs) / 1000).toFixed(2);
            const icon =
              seg.kind === "thinking" ? (
                <RobotOutlined />
              ) : seg.kind === "answer" ? (
                <CheckCircleOutlined />
              ) : seg.status === "running" ? (
                <LoadingOutlined spin />
              ) : seg.status === "error" ? (
                <CloseCircleOutlined />
              ) : (
                toolIcons[seg.label] || <ToolOutlined />
              );
            return (
              <Tooltip
                key={seg.id}
                title={
                  <div>
                    <div>
                      <strong>{toolLabels[seg.label] || seg.label}</strong>
                    </div>
                    <div>耗时 {dur}s</div>
                    <div style={{ opacity: 0.7, fontSize: 11 }}>点击查看详情</div>
                  </div>
                }
              >
                <button
                  className={`agent-timeline-seg agent-timeline-seg-${seg.kind} agent-timeline-status-${seg.status}`}
                  style={{ left: `${left}%`, width: `${width}%` }}
                  onClick={() => setActive(seg)}
                >
                  <span className="agent-timeline-icon">{icon}</span>
                  {width > 12 && (
                    <span className="agent-timeline-label">
                      {toolLabels[seg.label] || seg.label}
                    </span>
                  )}
                </button>
              </Tooltip>
            );
          })}
        </div>
        <div className="agent-timeline-axis">
          <span>0s</span>
          <span>{(totalMs / 1000).toFixed(1)}s</span>
        </div>
      </div>

      <Drawer
        open={!!active}
        onClose={() => setActive(null)}
        title={
          active
            ? `${active.kind === "tool" ? "工具调用 · " : ""}${
                toolLabels[active.label] || active.label
              }`
            : ""
        }
        placement="right"
        width={520}
      >
        {active && (
          <div className="agent-timeline-detail">
            <div style={{ marginBottom: 12 }}>
              <Tag color={active.status === "error" ? "red" : "blue"}>
                {active.status}
              </Tag>
              <Tag>耗时 {((active.endMs - active.startMs) / 1000).toFixed(2)}s</Tag>
            </div>
            {active.raw.tool_args && (
              <>
                <h4>输入</h4>
                <pre className="agent-timeline-pre">
                  {typeof active.raw.tool_args === "string"
                    ? active.raw.tool_args
                    : JSON.stringify(active.raw.tool_args, null, 2)}
                </pre>
              </>
            )}
            <h4>输出</h4>
            <pre className="agent-timeline-pre">{active.detail || "(空)"}</pre>
          </div>
        )}
      </Drawer>
    </>
  );
}
