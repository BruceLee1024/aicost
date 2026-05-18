# Sprint 9 — 产品与体验全面升级

> 状态：✅ 已完成 | 范围：Agent UX、智能开项 2.0、RAG 知识层、报告自动化 | 测试：30/30 通过

把"看得见"的 Agent 体验和"深能力"的 RAG / 报告联动，让用户从开项到报告每一步都能可控、可解释、可复用。

---

## 1. Phase 1 — Agent UX 基础

### 交付件

| 文件 | 作用 |
|---|---|
| `frontend/src/hooks/useAgentStream.ts` | 统一 SSE 控制 hook：取消、自动重试、思考流合并、工具时间戳 |
| `frontend/src/hooks/useAgentHistory.ts` | IndexedDB（兜底 localStorage）持久化最近 20 次 Agent 运行 |
| `frontend/src/hooks/useHotkey.ts` | 全局快捷键绑定，自动跳过输入框 |
| `frontend/src/components/AgentTimeline.tsx` | 横向时间轴可视化工具调用链；点击可看输入/输出 |
| `frontend/src/components/AgentRunControls.tsx` | 状态徽章 + 取消 + 重试 + 耗时秒表 |
| `frontend/src/components/ProjectSetupWizard.tsx` | 改造为基于 `useAgentStream` 的纯函数式组件 |

### 关键设计

- **AbortController 接入 fetch**：取消时直接断开网络流，无僵尸请求
- **指数退避重试**：`800ms × 2^attempt`，默认 2 次，AbortError 永不重试
- **Token 级合并**：连续的 `thinking` 事件自动拼接，避免 UI 抖动
- **工具配对**：`tool_call → tool_result` 用 `name + 序号` 配对，`_ts_start/_ts_end` 用于时间轴宽度
- **快捷键**：`Cmd/Ctrl+Enter` 提交（输入框内也生效），`Esc` 取消运行

### 友好错误映射

```ts
// useAgentStream.friendlyError()
"Failed to fetch"  → "网络连接失败，请检查后端服务"
"timeout"          → "请求超时，模型响应过慢"
"401"              → "未授权，请检查 API Key 配置"
"429"              → "请求过于频繁，请稍后重试"
"5xx"              → "服务器错误，请重试或查看后端日志"
```

---

## 2. Phase 2 — 智能开项向导 2.0（Propose-then-Commit）

### 核心改动：从「直接写库」到「草稿确认」

**之前**：Agent 调 `batch_create_boq_items` 直接写入数据库，用户事后才能改
**现在**：Agent 调 `propose_boq_items` 生成草稿 → 前端弹出 `<BoqDraftEditor>` → 用户编辑 → 提交才入库

### 交付件

| 文件 | 作用 |
|---|---|
| `backend/app/ai/tools/project_tools.py::propose_boq_items` | 新工具，**只返回草稿不写库**，read-only 可缓存 |
| `backend/app/ai/framework/draft_store.py` | 进程级 TTL 草稿缓存（默认 1h，最多 200 条），供跨请求读取 |
| `backend/app/api/routes/boq_drafts.py` | REST：`GET /boq-drafts`、`GET /boq-drafts/{token}`、`POST /commit`、`DELETE` |
| `frontend/src/components/BoqDraftEditor.tsx` | Drawer 形式的可编辑表格：增删改、批量分部、搜索、统计、提交/放弃 |
| `backend/app/ai/agents/v2/project_setup_agent.py` | 系统提示更新：默认走 `propose_boq_items`，仅当用户明确要"直接写入"时才用 `batch_create_boq_items` |

### Wizard 集成

```
用户输入 → Agent 流式执行 → 检测到 propose_boq_items 的 tool_result
        → 提取 draft_token → done 后自动弹出 BoqDraftEditor
        → 用户编辑 → 提交（commit endpoint）→ 写入并清除草稿
```

### 跨线程数据传递

`propose_boq_items` 在 orchestrator 工作线程里运行，`ctx.metadata` 在线程结束后丢失。**`draft_store` 是模块级单例**，token 在 SSE 里返回给前端，前端通过 `GET /boq-drafts/{token}` 取回完整草稿。

---

## 3. Phase 3 — RAG 知识层（持久化向量库）

### 交付件

| 文件 | 作用 |
|---|---|
| `backend/app/models/embedding.py` | `embeddings` 表：namespace + ref_id + sub_key + provider + dim + vector_json + meta + snippet |
| `backend/app/ai/framework/vector_store.py` | `VectorStore` 类：upsert / upsert_many / search / search_by_vector / count |
| `backend/app/services/project_indexer.py` | 单项目 / 全量索引到 `namespace=project` |
| `backend/app/ai/tools/rag_tools.py` | 三个 read_only 工具：`search_similar_projects`、`search_skill_chunks`、`get_price_trend` |
| `backend/app/api/routes/rag.py` | `GET /projects/{id}/similar`、`POST /projects/{id}/index`、`POST /projects/index/all`、`POST /skills/chunks/upload` |

### 设计取舍

- **存哪儿**：SQLite + JSON-encoded vectors。10K 量级以下的纯 Python 余弦扫描足够（~30ms）。把接口收窄到 `VectorStore.search` 一处，未来切 pgvector / Qdrant 不影响调用方
- **混 provider 处理**：行级 `provider` 字段 + 查询时 `WHERE provider=...`。从 `hash:256` 切到 `openai:1536` 不需要 migration
- **dimension 兼容**：列里存 `dim`，查询时按 `dim==len(qvec)` 过滤，避免误匹配
- **切块策略**：`/skills/chunks/upload` 用滑窗（默认 800 字 + 80 字重叠），`re.sub(\s+, " ")` 归一化空白

### `get_price_trend` 输出示例

```json
{
  "name": "钢筋",
  "months_window": 12,
  "samples": 36,
  "overall_avg": 4500.0,
  "latest": 4700.0,
  "deviation_from_avg_pct": 4.44,
  "momentum_3m_vs_prior_pct": 5.21,
  "series": [{"month": "2025-01", "samples": 3, "avg": 4400, ...}]
}
```

---

## 4. Phase 4 — 报告自动化（Word + AI 叙述）

### 交付件

| 文件 | 作用 |
|---|---|
| `backend/app/services/report_docx_service.py` | python-docx 实现的 DOCX 渲染：封面 / 费用汇总 / 分部分项 / 清单明细 |
| `backend/app/services/report_narrative_service.py` | LLM 生成的"## 执行摘要 / ## 分部分析 / ## 风险与建议"三段式 |
| `backend/app/api/routes/reports.py` | `format` 参数扩展为 `pdf \| excel \| docx`，新增 `narrative=true` 开关 |
| `frontend/src/components/ReportView.tsx` | 三个新按钮：导出 Word / Word + AI 摘要 / 原 PDF |

### Narrative Fallback

LLM 不可用时自动降级到模板摘要（`_fallback_narrative`），保证报告永远能拿到"摘要+分析+建议"三段，不会因 AI 故障而断功能。Narrative 还内联调用 `search_similar_projects` 把"相似历史项目"块拼到摘要尾部。

---

## 5. 测试覆盖

`backend/tests/test_sprint9.py` — 30 个测试用例，全部通过：

| 类 | 用例数 | 覆盖 |
|---|---|---|
| `TestProposeBoqItems` | 6 | propose 工具：写不写库、JSON 解析、限额、缺字段、round-trip |
| `TestDraftStore` | 2 | TTL 缓存：put/get/pop、按项目过滤 |
| `TestDraftAPI` | 4 | REST：get / commit / 404 / 400 / 放弃 |
| `TestVectorStore` | 4 | upsert / replace 语义、exclude_ref_ids、count |
| `TestProjectIndexer` | 1 | 全量重索引后排序合理 |
| `TestRagTools` | 3 | similar_projects 自排除、price_trend 空数据 / 含数据 |
| `TestRagApi` | 2 | similar 端点、skill 上传 + 检索 round-trip |
| `TestDocxRenderer` | 2 | DOCX 是合法 ZIP、narrative 内容写入 |
| `TestNarrativeService` | 1 | LLM 禁用时 fallback |
| `TestReportExportRoute` | 2 | docx 端点、不支持的格式 400 |
| 其他 | 3 | 工具注册、agent 配置、tool_names 顺序 |

```bash
cd backend && venv/bin/python -m pytest tests/test_sprint9.py -q
# 30 passed
```

---

## 6. 风险与后续

| 风险 / 待办 | 处置 |
|---|---|
| **预存的 `test_project_setup_agent_config` 失败** | 与 Sprint 9 无关，原 prompt 改动遗留，期望 max_turns=25 但代码=15。建议下次清理 |
| **草稿 SSE 提取依赖 tool_result 文本截断** | orchestrator 当前对 `tool_result` 截断 500 字符，刚好覆盖 `draft_token`。若 token 格式变长需同步调整 |
| **向量库无 ANN 索引** | 当前是顺序扫描；超过 ~50K 向量时建议切 pgvector |
| **未做项目入库后自动索引** | 创建 / 编辑 project 后未自动 `index_project()`，需手动调 `/projects/index/all`。可后续加 ORM event hook |
| **AI 叙述未做缓存** | 每次导出都会调 LLM，金额上有成本；若用户高频导出，可加 `report_narrative` 表缓存 |

---

## 7. 触达入口速查

```
[前端]
  ProjectSetupWizard                  → /api/projects/{id}/orchestrate/stream (SSE)
  BoqDraftEditor (Drawer)             → /api/projects/{id}/boq-drafts/{token}
  ReportView 「Word + AI 摘要」按钮      → /api/projects/{id}/report/export?format=docx&narrative=true

[后端工具]
  propose_boq_items                   ← ProjectSetupAgent 默认调用
  search_similar_projects             ← 任何 Agent 可调用，目前在 narrative 内联使用
  search_skill_chunks                 ← chat_agent / valuation_agent 可继承调用
  get_price_trend                     ← insight_agent / 报告 narrative 可用

[后端 API]
  /projects/{id}/similar              GET  返回 top_n 个相似项目
  /projects/{id}/index                POST 单项目重索引
  /projects/index/all                 POST 全量重索引
  /skills/chunks/upload               POST 上传规范文本切块入库
  /projects/{id}/boq-drafts           GET  列出草稿
  /projects/{id}/boq-drafts/{token}   GET / DELETE
  /projects/{id}/boq-drafts/{token}/commit POST 写入数据库
  /projects/{id}/report/export        GET  ?format=pdf|excel|docx&narrative=true
```
