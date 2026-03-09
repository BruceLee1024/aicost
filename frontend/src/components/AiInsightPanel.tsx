import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  projectId: number;
  contextType: string;
  contextData: Record<string, unknown>;
  title?: string;
  /** Static fallback text when AI is unavailable */
  fallback?: string;
  /** Trigger re-fetch when this key changes */
  triggerKey?: string | number;
}

/**
 * Reusable AI insight panel that fetches analysis from the backend.
 * Shows shimmer loading, then AI text or static fallback.
 */
export default function AiInsightPanel({
  projectId, contextType, contextData, title = "AI 分析", fallback, triggerKey,
}: Props) {
  const [insight, setInsight] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setInsight(null);

    api.aiAnalyze(projectId, contextType, contextData)
      .then((res) => {
        if (!cancelled) {
          setInsight(res.insight ?? fallback ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) setInsight(fallback ?? null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [projectId, contextType, triggerKey]);

  return (
    <div className="wizard-ai-panel">
      <div className="wizard-ai-header">
        <span className="material-symbols-outlined">psychology</span>
        {title}
      </div>
      <div className="wizard-ai-body">
        {loading ? (
          <div>
            <div className="ai-insight-shimmer" />
            <div className="ai-insight-shimmer" />
            <div className="ai-insight-shimmer" />
          </div>
        ) : insight ? (
          <div style={{ whiteSpace: "pre-wrap" }}>{insight}</div>
        ) : (
          <div style={{ color: "var(--text-muted)" }}>暂无分析</div>
        )}
      </div>
    </div>
  );
}
