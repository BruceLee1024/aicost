# 系统设计：AI 原生工程计价软件（MVP）
版本：0.2（可开发草案）
创建日期：2026-03-02
关联文档：`docs/prd/PRD-AI原生工程计价软件.md`

## 1. 设计目标
- 计价结果必须确定性、可复现、可追溯。
- AI 负责“识别/推荐/解释”，规则引擎负责“计算与约束”。
- 支持版本化与增量重算，适配高频变更场景。

## 2. 总体架构
采用分层架构：
- 接入层（Web/API）
- 领域服务层（项目、清单、匹配、计价、版本、导出）
- AI 服务层（解析、推荐、解释）
- 规则与计算层（规则包、公式、费率、取费、税金）
- 数据层（业务库 + 文档对象存储 + 向量索引 + 审计日志）

核心原则：
- 金额计算仅在规则与计算层完成。
- AI 输出不得直接写入金额字段，必须经过“建议→确认→计算”流程。

## 3. 核心模块设计
### 3.1 项目与规则包模块
职责：
- 管理项目、规则包、参数快照、生效版本。

关键能力：
- 项目创建时绑定规则包版本（不可隐式漂移）。
- 规则包变更触发“新版本快照”，历史版本可回放。

### 3.2 数据导入模块
职责：
- 导入清单、定额库、材料价、取费参数。

流程：
1) 文件上传与解析
2) 字段映射（自动 + 人工确认）
3) 数据清洗（单位标准化、编码规范化）
4) 导入校验（必填、重复、非法值）
5) 入库并生成 source_version

### 3.3 清单建模模块
职责：
- 维护清单层级、清单项、属性、状态与人工确认项。

能力：
- 分部/分项/清单项树结构管理
- 批量编辑、批量标记、回滚
- 关联资料证据锚点（页码、行号、单元格）

### 3.4 定额匹配模块（AI + 规则）
职责：
- 给清单项推荐定额候选，并输出理由与置信度。

策略：
- 召回：关键词/语义相似 + 类目过滤 + 单位过滤
- 重排：特征词匹配、历史确认先验、单位一致性惩罚
- 输出：TopN 候选 + reason_codes + confidence

确认机制：
- 用户确认后写入 `line_item_quota_binding`
- 未确认状态不进入最终计价

### 3.5 计价计算引擎（确定性）
职责：
- 根据绑定关系和规则包计算人材机、措施费、取费、税金与汇总。

特性：
- 纯函数化输入输出（便于测试与回放）
- 全量计算 + 增量计算（受影响链路重算）
- 每个结果携带 provenance（公式、输入、版本）

### 3.6 校验与风险模块
职责：
- 结构化校验 + 风险提示队列。

校验类型：
- 单位冲突、缺数量、缺材料价、费率异常、重复项、未确认匹配。

输出：
- 校验码、严重等级、定位对象、修复建议。

### 3.7 版本与差异模块
职责：
- 生成版本快照并比较差异。

差异维度：
- 清单差异（增删改）
- 匹配差异（定额子目变化）
- 价格差异（材料价/费率变化）
- 汇总差异（分部/专业/总价）

### 3.8 导出模块
职责：
- 按模板导出成果与差异报告（Excel/PDF）。

要求：
- 导出文件包含版本号、生成时间、规则包版本。

## 4. AI 架构设计
## 4.1 AI 任务拆解
1) 文档结构化（清单字段识别）
2) 定额匹配推荐
3) 差异解释生成
4) 自然语言导航（定位未确认项/异常项）

## 4.2 任务分工原则
- RAG：用于“找依据、做解释、做导航”。
- 规则引擎：用于“计算金额与费率”。
- Agent：用于多步骤编排（如“导入→建议→校验→报告”），不负责数值最终裁决。

## 4.3 AI Guardrails
- 禁止 AI 直接产出最终金额写库。
- 所有 AI 输出必须附来源与置信度。
- 低置信度自动进入人工确认队列。

## 5. 数据模型（MVP）
建议核心表（示意）：
- `projects`：项目主表
- `rule_packages` / `rule_package_versions`
- `sources` / `source_versions`（导入文件及版本）
- `boq_items`（清单项）
- `quota_items`（定额条目）
- `material_prices`（材料价格记录）
- `line_item_quota_binding`（清单项与定额绑定）
- `calc_runs`（计算任务）
- `calc_results`（结果明细）
- `result_provenance`（结果溯源）
- `validation_issues`（校验问题）
- `snapshots`（版本快照）
- `diff_reports`（差异报告）
- `audit_logs`（审计日志）

关键关系：
- 一个 `project` 对应多个 `snapshot`
- 每次导入创建一个 `source_version`
- `calc_results` 必须关联 `calc_run_id` 与 `snapshot_id`

## 6. 关键接口（示例）
### 6.1 项目与规则
- `POST /api/projects`
- `POST /api/projects/{id}/rule-package:bind`

### 6.2 导入
- `POST /api/imports/boq`
- `POST /api/imports/quota`
- `POST /api/imports/material-prices`

### 6.3 匹配与确认
- `POST /api/boq-items/{id}/quota-candidates`
- `POST /api/boq-items/{id}/quota-binding:confirm`
- `POST /api/boq-items/quota-binding:batch-confirm`

### 6.4 计算与校验
- `POST /api/projects/{id}/calculate`
- `GET /api/calc-runs/{id}/results`
- `GET /api/projects/{id}/validation-issues`

### 6.5 版本与差异
- `POST /api/projects/{id}/snapshots`
- `POST /api/projects/{id}/diff`

### 6.6 导出
- `POST /api/exports/valuation-report`
- `POST /api/exports/diff-report`

## 7. 计算与重算机制
### 7.1 全量计算
触发条件：
- 首次计算
- 规则包大版本变化

### 7.2 增量重算
触发条件：
- 清单项数量变化
- 定额绑定变化
- 材料价更新
- 局部费率参数变化

实现思路：
- 建立依赖图（boq_item -> binding -> material/rule）
- 仅重算受影响节点并向上汇总

## 8. 审计与可追溯设计
每条结果必须能追溯：
- 输入数据：清单项、定额条目、材料价记录
- 规则来源：规则包版本、公式版本
- 操作轨迹：确认人、确认时间、变更前后值

审计日志建议字段：
- actor、action、resource_type、resource_id、before_json、after_json、timestamp

## 9. 技术选型建议（MVP）
- 前端：React + TypeScript（便于构建复杂表格与批量操作）
- 后端：Python FastAPI 或 Node.js NestJS（二选一，优先团队熟悉）
- 数据库：PostgreSQL
- 缓存/队列：Redis（异步导入与计算任务）
- 文件存储：S3 兼容对象存储（本地可 MinIO）
- 向量检索：pgvector 或独立向量库（用于定额检索与解释）

## 10. 测试与质量保障
- 单元测试：公式、费率、取费顺序、四舍五入规则
- 集成测试：导入→匹配→计算→导出闭环
- 回归测试：基准项目快照比对（金额偏差阈值为 0）
- AI 评测：匹配准确率@TopN、低置信度召回率、解释可用性抽检

## 11. 部署与环境
- 单租户私有部署优先（满足工程数据敏感场景）
- 组件可拆分部署：API、Worker、DB、Object Storage
- 关键配置外置：规则包、导出模板、提示词模板

## 12. 迭代计划（与 PRD 对齐）
- 阶段 1：导入 + 清单建模 + 手工绑定 + 确定性计算
- 阶段 2：AI 候选推荐 + 证据链展示 + 导出
- 阶段 3：快照对比 + 增量重算 + 风险队列

## 13. 开放问题
- 首发地区规则包优先级（决定规则实现范围）
- 需要兼容的外部软件与模板标准
- 是否要求离线推理（影响模型与部署方案）

## 14. 技术栈定稿（MVP）
- 后端：Python 3.11 + FastAPI + Pydantic v2
- ORM：SQLAlchemy 2.x
- 数据库：PostgreSQL（本地开发可 SQLite）
- 测试：pytest
- 任务队列：预留 Redis + worker（后续接入）

## 15. 后端目录结构（已落地）
- `backend/app/main.py`：应用入口与路由注册
- `backend/app/api/routes/`：各业务模块路由
- `backend/app/models/`：ORM 模型
- `backend/app/schemas/`：请求/响应模型
- `backend/app/services/`：领域服务（含计价引擎）
- `backend/app/db/`：数据库连接与会话
- `backend/sql/`：初始 DDL 草案
- `backend/tests/`：单元测试

## 16. MVP 最小接口清单（第一阶段）
- `GET /healthz`：健康检查
- `POST /api/projects`：创建项目
- `GET /api/projects`：查询项目
- `POST /api/calculate/run`：运行最小计价计算（示例）
