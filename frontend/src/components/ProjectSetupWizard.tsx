import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Space,
  Steps,
  Tag,
} from "antd";
import {
  RocketOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
} from "@ant-design/icons";
import { useAgentStream } from "../hooks/useAgentStream";
import { useAgentHistory } from "../hooks/useAgentHistory";
import { useHotkey } from "../hooks/useHotkey";
import AgentRunControls from "./AgentRunControls";
import AgentTimeline from "./AgentTimeline";
import BoqDraftEditor from "./BoqDraftEditor";

interface Props {
  projectId: number;
  onComplete?: () => void;
}

type Stage = "input" | "running" | "done";

const TEMPLATES = [
  {
    label: "住宅楼",
    text: "5层框架结构住宅楼，建筑面积约3000m²，地下1层车库。基础采用独立基础，主体C30混凝土、HRB400钢筋。外墙面砖，内墙乳胶漆，铝合金门窗。",
  },
  {
    label: "办公楼",
    text: "10层框架-剪力墙结构办公楼，建筑面积约8000m²。基础为筏板基础，主体C35混凝土、HRB400钢筋。玻璃幕墙外立面，精装修交付。",
  },
  {
    label: "商业综合体",
    text: "地上4层地下2层商业综合体，总建筑面积约15000m²。钢筋混凝土框架结构，C40混凝土，大跨度梁。地面石材铺装，吊顶装修，自动扶梯4部。",
  },
];

export default function ProjectSetupWizard({ projectId, onComplete }: Props) {
  const [description, setDescription] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const startedAtRef = useRef<number>(0);

  const stream = useAgentStream();
  const history = useAgentHistory("setup");
  const [draftToken, setDraftToken] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [committed, setCommitted] = useState(false);

  const stage: Stage =
    stream.state === "idle"
      ? "input"
      : stream.state === "running" || stream.state === "retrying"
        ? "running"
        : "done";

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [stream.steps]);

  // Detect propose_boq_items tool_result events → extract draft_token
  useEffect(() => {
    for (let i = stream.steps.length - 1; i >= 0; i--) {
      const s = stream.steps[i];
      if (s.type === "tool_result" && s.tool_name === "propose_boq_items") {
        try {
          const parsed = JSON.parse(s.tool_result || "{}");
          if (parsed.draft_token && parsed.draft_token !== draftToken) {
            setDraftToken(parsed.draft_token);
            setCommitted(false);
          }
        } catch {
          /* ignore */
        }
        break;
      }
    }
  }, [stream.steps, draftToken]);

  // Auto-open editor when stream finishes with a draft pending
  useEffect(() => {
    if (stream.state === "done" && draftToken && !committed) {
      setEditorOpen(true);
    }
  }, [stream.state, draftToken, committed]);

  // Persist completed runs to history
  useEffect(() => {
    if (stream.state === "done" || stream.state === "error") {
      if (description && stream.steps.length > 0) {
        void history.save({
          scope: "setup",
          projectId,
          instruction: description,
          steps: stream.steps,
          finalAnswer: stream.finalAnswer,
          startedAt: startedAtRef.current || Date.now(),
          durationMs: stream.elapsed * 1000,
          status: stream.state === "error" ? "error" : "done",
          error: stream.error || undefined,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.state]);

  const handleStart = () => {
    if (!description.trim()) return;
    startedAtRef.current = Date.now();
    void stream.run({
      url: `/projects/${projectId}/orchestrate/stream`,
      body: { instruction: `智能开项：${description.trim()}` },
    });
  };

  const handleRetry = () => handleStart();

  // Hotkeys: Cmd/Ctrl+Enter to submit (in textarea), Esc to cancel
  useHotkey("mod+enter", handleStart, { allowInInput: true });
  useHotkey("escape", () => stream.cancel(), {
    enabled: stage === "running",
  });

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  const currentStep = stage === "input" ? 0 : stage === "running" ? 1 : 2;

  // ── Memoize legacy step view (compatibility with existing UI) ──
  const legacySteps = useMemo(
    () =>
      stream.steps.map((s) => ({
        type: s.type,
        content: s.content,
        tool_name: s.tool_name,
        tool_result: s.tool_result,
      })),
    [stream.steps],
  );

  const elapsed = stream.elapsed;
  const toolCallCount = stream.toolCallCount;
  const finalAnswer = stream.finalAnswer;
  const error = stream.error;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Steps
        current={currentStep}
        size="small"
        status={stream.state === "error" ? "error" : undefined}
        items={[
          { title: "工程描述", icon: <FileTextOutlined /> },
          {
            title: stage === "running" ? `AI 生成中 (${formatElapsed(elapsed)})` : "AI 生成",
            icon: stage === "running" ? <LoadingOutlined /> : <RocketOutlined />,
          },
          { title: "完成", icon: <CheckCircleOutlined /> },
        ]}
      />

      {stage === "input" && (
        <Card size="small" title="描述你的工程">
          {/* Quick templates */}
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)", marginRight: 8 }}>
              快速模板：
            </span>
            <Space size={4} wrap>
              {TEMPLATES.map((t) => (
                <Tag
                  key={t.label}
                  style={{ cursor: "pointer" }}
                  color={description === t.text ? "blue" : undefined}
                  onClick={() => setDescription(t.text)}
                >
                  <ThunderboltOutlined /> {t.label}
                </Tag>
              ))}
            </Space>
          </div>

          <Input.TextArea
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={
              "请描述工程信息，例如：\n\n" +
              "5层框架结构住宅楼，建筑面积约3000m²，地下1层车库，\n" +
              "基础采用独立基础，主体为C30混凝土，HRB400钢筋，\n" +
              "外墙面砖，内墙乳胶漆，铝合金门窗。"
            }
          />
          <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {description.length > 0 ? `${description.length} 字` : ""}
              <span style={{ marginLeft: 12, opacity: 0.6 }}>
                <kbd>⌘/Ctrl</kbd> + <kbd>Enter</kbd> 提交
              </span>
            </span>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={handleStart}
              disabled={!description.trim()}
            >
              开始智能开项
            </Button>
          </div>

          {history.records.length > 0 && (
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                <HistoryOutlined /> 最近运行（点击复用）
              </div>
              <Space size={4} wrap>
                {history.records.slice(0, 5).map((r) => (
                  <Tag
                    key={r.id}
                    style={{ cursor: "pointer", maxWidth: 240 }}
                    onClick={() => setDescription(r.instruction.replace(/^智能开项：/, ""))}
                  >
                    {r.status === "done" ? "✅" : r.status === "error" ? "❌" : "⏸"}{" "}
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-block", maxWidth: 200, verticalAlign: "bottom" }}>
                      {r.instruction.slice(0, 32)}
                    </span>
                  </Tag>
                ))}
              </Space>
            </div>
          )}
        </Card>
      )}

      {(stage === "running" || stage === "done") && (
        <>
          <AgentRunControls
            state={stream.state}
            elapsed={elapsed}
            toolCallCount={toolCallCount}
            retryCount={stream.retryCount}
            error={error}
            onCancel={stream.cancel}
            onRetry={handleRetry}
          />

          {/* Phase 1.2: Tool-call timeline */}
          <AgentTimeline
            steps={stream.steps}
            running={stage === "running"}
          />

          {/* Steps log */}
          <Card size="small" title="执行日志">
            <div ref={logRef} style={{ maxHeight: 280, overflow: "auto" }}>
              {legacySteps.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "4px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                    fontSize: 12,
                  }}
                >
                  {s.tool_name && (
                    <Tag color="blue" style={{ fontSize: 11 }}>
                      {s.tool_name}
                    </Tag>
                  )}
                  <span style={{ color: "var(--text-secondary)" }}>
                    {s.content?.slice(0, 200) || s.tool_result?.slice(0, 200) || s.type}
                  </span>
                </div>
              ))}
              {legacySteps.length === 0 && stage === "running" && (
                <div style={{ color: "var(--text-muted)", padding: 12 }}>等待 AI 响应...</div>
              )}
            </div>
          </Card>

          {/* Final result */}
          {stage === "done" && (
            <Card
              size="small"
              title={
                stream.state === "error"
                  ? "❌ 执行出错"
                  : stream.state === "cancelled"
                    ? "⏸ 已取消"
                    : `✅ 智能开项完成 (${formatElapsed(elapsed)}, ${toolCallCount} 次工具调用)`
              }
              style={{
                borderColor: stream.state === "error"
                  ? "rgba(255,77,79,0.3)"
                  : stream.state === "cancelled"
                    ? "rgba(140,140,140,0.3)"
                    : "rgba(82,196,26,0.3)",
              }}
            >
              <div
                style={{
                  whiteSpace: "pre-wrap",
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: "var(--text-primary)",
                }}
              >
                {finalAnswer || "（无回复）"}
              </div>
              {draftToken && !committed && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginTop: 12 }}
                  message="检测到清单草稿"
                  description="AI 已生成可编辑草稿，请预览/调整后再提交写入项目。"
                  action={
                    <Button
                      type="primary"
                      onClick={() => setEditorOpen(true)}
                    >
                      预览 / 编辑草稿
                    </Button>
                  }
                />
              )}
              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <Button onClick={() => { stream.reset(); setDraftToken(null); setCommitted(false); }}>
                  重新开项
                </Button>
                {draftToken && !committed && (
                  <Button onClick={() => setEditorOpen(true)}>
                    打开草稿编辑器
                  </Button>
                )}
                {onComplete && (
                  <Button type="primary" onClick={onComplete}>
                    查看清单
                  </Button>
                )}
              </div>
            </Card>
          )}
        </>
      )}

      <BoqDraftEditor
        open={editorOpen}
        projectId={projectId}
        token={draftToken}
        onClose={() => setEditorOpen(false)}
        onCommitted={() => {
          setCommitted(true);
          setEditorOpen(false);
        }}
      />
    </div>
  );
}
