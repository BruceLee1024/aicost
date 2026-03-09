import { useEffect, useRef, useState } from "react";
import { api } from "../api";

interface Props {
  projectId: number;
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  { icon: "trending_up", text: "项目整体进展如何？" },
  { icon: "link_off", text: "哪些清单项还未绑定？" },
  { icon: "paid", text: "费用构成是否合理？" },
  { icon: "warning", text: "有哪些校验问题？" },
];

export default function AiPanel({ projectId }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    if (!open) setOpen(true);
    const userMsg: ChatMsg = { role: "user", content: msg };
    const history = [...messages, userMsg];
    setMessages(history);
    setLoading(true);

    try {
      const res = await api.aiChat(
        projectId,
        msg,
        messages.map((m) => ({ role: m.role, content: m.content })),
      );
      if (res.reply) {
        setMessages([...history, { role: "assistant", content: res.reply }]);
      } else {
        setMessages([...history, { role: "assistant", content: "AI 服务未配置。请在「系统设置」中配置 API Key 后即可使用智能助手。" }]);
      }
    } catch {
      setMessages([...history, { role: "assistant", content: "请求失败，请稍后重试。" }]);
    }
    setLoading(false);
  };

  const msgCount = messages.filter((m) => m.role === "assistant").length;

  return (
    <>
      {/* Floating toggle button */}
      {!open && (
        <button className="ai-fab" onClick={() => setOpen(true)}>
          <span className="ai-fab-icon material-symbols-outlined">auto_awesome</span>
          {msgCount > 0 && <span className="ai-fab-badge">{msgCount}</span>}
        </button>
      )}

      {/* Floating panel */}
      <div className={`ai-float-panel${open ? " ai-float-open" : ""}`}>
        {/* Header */}
        <div className="ai-float-header">
          <div className="ai-float-header-left">
            <div className="ai-float-logo">
              <span className="material-symbols-outlined">auto_awesome</span>
            </div>
            <div>
              <div className="ai-float-title">AI 助手</div>
              <div className="ai-float-subtitle">
                {loading ? "思考中..." : "随时为您分析项目"}
              </div>
            </div>
          </div>
          <div className="ai-float-header-actions">
            {messages.length > 0 && (
              <button
                className="ai-float-btn-icon"
                title="清空对话"
                onClick={() => setMessages([])}
              >
                <span className="material-symbols-outlined">delete_sweep</span>
              </button>
            )}
            <button className="ai-float-btn-icon" onClick={() => setOpen(false)} title="收起">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Chat body */}
        <div className="ai-float-body" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="ai-float-welcome">
              <div className="ai-float-welcome-icon">
                <span className="material-symbols-outlined">psychology_alt</span>
              </div>
              <div className="ai-float-welcome-title">Hi, 我是您的 AI 造价助手</div>
              <div className="ai-float-welcome-desc">
                了解您的项目数据，试试下面的问题：
              </div>
              <div className="ai-float-quick-grid">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p.text}
                    className="ai-float-quick-card"
                    onClick={() => sendMessage(p.text)}
                  >
                    <span className="material-symbols-outlined ai-float-quick-icon">{p.icon}</span>
                    <span>{p.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <div key={i} className={`ai-float-msg ${m.role}`}>
                  {m.role === "assistant" && (
                    <div className="ai-float-msg-avatar">
                      <span className="material-symbols-outlined">auto_awesome</span>
                    </div>
                  )}
                  <div className="ai-float-msg-bubble">{m.content}</div>
                </div>
              ))}
              {loading && (
                <div className="ai-float-msg assistant">
                  <div className="ai-float-msg-avatar">
                    <span className="material-symbols-outlined">auto_awesome</span>
                  </div>
                  <div className="ai-float-msg-bubble">
                    <span className="ai-float-typing"><span /><span /><span /></span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input */}
        <div className="ai-float-input-wrap">
          <div className="ai-float-input-row">
            <input
              className="ai-float-input"
              placeholder="问我任何项目相关的问题..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") sendMessage(); }}
              disabled={loading}
            />
            <button
              className="ai-float-send"
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
            >
              <span className="material-symbols-outlined">arrow_upward</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
