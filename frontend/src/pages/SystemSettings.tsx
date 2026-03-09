import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button, Card, Collapse, InputNumber, Select, Space, Switch, Tag,
  Input, Tooltip,
} from "antd";
import {
  ApiOutlined, CheckCircleOutlined, CloseCircleOutlined,
  LoadingOutlined, ThunderboltOutlined,
} from "@ant-design/icons";
import type { AISettingsPayload, AITestConnectionResponse } from "../api";
import { api } from "../api";

const AI_PROVIDERS = [
  { key: "deepseek" as const, label: "DeepSeek", icon: "🤖" },
  { key: "qwen" as const, label: "通义千问 (Qwen)", icon: "🧠" },
  { key: "kimi" as const, label: "Kimi (Moonshot)", icon: "🌙" },
  { key: "glm" as const, label: "智谱 GLM", icon: "💎" },
  { key: "openai" as const, label: "OpenAI", icon: "⚡" },
];

type TestStatus = { loading: boolean; result: AITestConnectionResponse | null };

export default function SystemSettings() {
  const { message } = AntApp.useApp();
  const [aiSettings, setAiSettings] = useState<AISettingsPayload | null>(null);
  const [saving, setSaving] = useState(false);
  const [testStatus, setTestStatus] = useState<Record<string, TestStatus>>({});

  useEffect(() => {
    api.getAISettings().then(setAiSettings).catch(() =>
      message.error("加载 AI 配置失败"),
    );
  }, []);

  const handleField = (
    providerKey: keyof AISettingsPayload["providers"],
    field: "api_key" | "base_url" | "model",
    value: string,
  ) => {
    if (!aiSettings) return;
    setTestStatus((prev) => ({ ...prev, [providerKey]: { loading: false, result: null } }));
    setAiSettings({
      ...aiSettings,
      providers: {
        ...aiSettings.providers,
        [providerKey]: { ...aiSettings.providers[providerKey], [field]: value },
      },
    });
  };

  const handleSave = async () => {
    if (!aiSettings) return;
    setSaving(true);
    try {
      const res = await api.updateAISettings(aiSettings);
      setAiSettings(res);
      message.success("AI 配置已保存");
    } catch {
      message.error("保存失败");
    }
    setSaving(false);
  };

  const handleTest = async (providerKey: string) => {
    if (!aiSettings) return;
    const cfg = aiSettings.providers[providerKey as keyof AISettingsPayload["providers"]];
    if (!cfg.api_key.trim()) { message.warning("请先输入 API Key"); return; }
    setTestStatus((prev) => ({ ...prev, [providerKey]: { loading: true, result: null } }));
    try {
      const res = await api.testAIConnection({
        provider: providerKey, api_key: cfg.api_key, base_url: cfg.base_url, model: cfg.model,
      });
      setTestStatus((prev) => ({ ...prev, [providerKey]: { loading: false, result: res } }));
      if (res.success) message.success(`${providerKey} 连接成功 (${res.latency_ms}ms)`);
      else message.error(`连接失败: ${res.error}`);
    } catch {
      setTestStatus((prev) => ({
        ...prev,
        [providerKey]: { loading: false, result: { success: false, latency_ms: 0, reply: "", error: "请求失败" } },
      }));
    }
  };

  if (!aiSettings) {
    return <div style={{ padding: 40, color: "var(--text-secondary)" }}>加载中...</div>;
  }

  const activeProvider = aiSettings.provider;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "32px 24px" }}>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, fontSize: 20 }}>
          <ApiOutlined /> AI 模型配置
        </h2>
        <p style={{ color: "var(--text-secondary)", margin: "4px 0 0", fontSize: 13 }}>
          配置国产大模型 API Key，选择当前使用的供应商。修改后需点击保存。
        </p>
      </div>

      {/* Global controls */}
      <Card size="small" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "16px 32px", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>当前供应商</div>
            <Select
              value={aiSettings.provider}
              onChange={(v) => setAiSettings({ ...aiSettings, provider: v })}
              style={{ width: 200 }}
              options={[
                { label: "🚫 禁用 AI", value: "disabled" },
                ...AI_PROVIDERS.map((p) => ({ label: `${p.icon} ${p.label}`, value: p.key })),
              ]}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>超时 (秒)</div>
            <InputNumber
              value={aiSettings.timeout_seconds}
              min={5} max={120}
              onChange={(v) => setAiSettings({ ...aiSettings, timeout_seconds: v ?? 20 })}
              style={{ width: 80 }}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>审计日志</div>
            <Switch
              checked={aiSettings.enable_audit_logs}
              onChange={(v) => setAiSettings({ ...aiSettings, enable_audit_logs: v })}
            />
          </div>
        </div>
      </Card>

      {/* Provider cards */}
      <Collapse
        defaultActiveKey={activeProvider !== "disabled" ? [activeProvider] : []}
        style={{ marginBottom: 20 }}
        items={AI_PROVIDERS.map((p) => {
          const isActive = activeProvider === p.key;
          const cfg = aiSettings.providers[p.key];
          const ts = testStatus[p.key];
          const hasKey = !!cfg.api_key.trim();

          return {
            key: p.key,
            label: (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 16 }}>{p.icon}</span>
                <span style={{ fontWeight: 600 }}>{p.label}</span>
                {isActive && <Tag color="green" style={{ marginLeft: 4 }}>当前</Tag>}
                {ts?.result && !ts.loading && (
                  ts.result.success
                    ? <Tag color="success" icon={<CheckCircleOutlined />} style={{ marginLeft: "auto" }}>已连通 {ts.result.latency_ms}ms</Tag>
                    : <Tag color="error" icon={<CloseCircleOutlined />} style={{ marginLeft: "auto" }}>失败</Tag>
                )}
                {!ts?.result && hasKey && !ts?.loading && (
                  <Tag style={{ marginLeft: "auto" }}>未测试</Tag>
                )}
              </div>
            ),
            children: (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {/* API Key + test button */}
                <div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>API Key</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Input.Password
                      placeholder={`输入 ${p.label} 的 API Key`}
                      value={cfg.api_key}
                      onChange={(e) => handleField(p.key, "api_key", e.target.value)}
                      style={{ flex: 1, maxWidth: 480 }}
                    />
                    <Tooltip title={hasKey ? "发送测试消息验证连通性" : "请先输入 API Key"}>
                      <Button
                        icon={ts?.loading ? <LoadingOutlined /> : <ThunderboltOutlined />}
                        onClick={() => handleTest(p.key)}
                        loading={ts?.loading}
                        disabled={!hasKey}
                        type={ts?.result?.success ? "default" : "primary"}
                        ghost={!ts?.result?.success}
                      >
                        测试连接
                      </Button>
                    </Tooltip>
                  </div>
                </div>

                {/* Base URL + Model */}
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>Base URL</div>
                    <Input placeholder="API 地址" value={cfg.base_url}
                      onChange={(e) => handleField(p.key, "base_url", e.target.value)} />
                  </div>
                  <div style={{ width: 200 }}>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>模型名称</div>
                    <Input placeholder="模型 ID" value={cfg.model}
                      onChange={(e) => handleField(p.key, "model", e.target.value)} />
                  </div>
                </div>

                {/* Test result */}
                {ts?.result && !ts.loading && (
                  <div style={{
                    padding: "10px 14px", borderRadius: 8, fontSize: 13,
                    background: ts.result.success ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                    border: `1px solid ${ts.result.success ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
                  }}>
                    {ts.result.success ? (
                      <div>
                        <span style={{ color: "#22c55e", fontWeight: 600 }}><CheckCircleOutlined /> 连接成功</span>
                        <span style={{ color: "var(--text-secondary)", marginLeft: 12 }}>延迟 {ts.result.latency_ms}ms</span>
                        {ts.result.reply && (
                          <div style={{ marginTop: 6, color: "var(--text-secondary)" }}>模型回复：{ts.result.reply}</div>
                        )}
                      </div>
                    ) : (
                      <div>
                        <span style={{ color: "#ef4444", fontWeight: 600 }}><CloseCircleOutlined /> 连接失败</span>
                        {ts.result.latency_ms > 0 && (
                          <span style={{ color: "var(--text-secondary)", marginLeft: 12 }}>耗时 {ts.result.latency_ms}ms</span>
                        )}
                        {ts.result.error && (
                          <div style={{ marginTop: 6, color: "var(--text-secondary)", wordBreak: "break-all" }}>错误：{ts.result.error}</div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Quick set as active */}
                {!isActive && hasKey && (
                  <Button size="small" type="link" style={{ padding: 0, width: "fit-content" }}
                    onClick={() => setAiSettings({ ...aiSettings, provider: p.key })}>
                    设为当前供应商
                  </Button>
                )}
              </div>
            ),
          };
        })}
      />

      <Space>
        <Button type="primary" size="large" loading={saving} onClick={handleSave}>保存配置</Button>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>测试连接无需保存，修改配置后需保存才生效</span>
      </Space>
    </div>
  );
}
