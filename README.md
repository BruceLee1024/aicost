# 🏗️ 智慧建筑造价系统

[![License](https://img.shields.io/badge/License-Non--Commercial-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg)](https://react.dev/)

> 🤖 **AI 驱动的建筑造价全流程管理平台**  
> 从图纸识别到清单生成、定额绑定、单价分析、成本核算的智能化闭环解决方案

## 📋 项目概览

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| **前端** | React + TypeScript + Ant Design | Vite, TailwindCSS, Material Symbols |
| **后端** | FastAPI + SQLAlchemy | Python 3.12, SQLite, Pydantic |
| **AI** | 多模型支持 | OpenAI Compatible, 自定义 LLM |
| **数据** | 结构化造价数据 | BOQ 清单、定额库、材料价格 |

## ✨ 核心特性

<table>
<tr>
<td width="50%">

### 📐 图纸 AI 识别

- 🎯 **智能识别**：上传结构平面图，AI 自动识别柱、梁、墙、板等构件
- 📊 **可视化标注**：边界框 + 置信度实时显示
- 🛠️ **手动调整**：修正/新增/删除/合并构件
- 📤 **一键导出**：识别结果直接生成 BOQ 清单

### � 计价管理

- 🔍 **单价分析**：人工/材料/机械费用完整分解
- 🔗 **定额绑定**：智能匹配 + 系数调整
- 💹 **实时价格**：市场价动态查询
- 📈 **可视化**：成本构成图表展示

### 📈 报表中心

- �📊 **项目总览**：造价汇总 + 进度追踪
- ✅ **绑定进度**：清单项绑定完成度
- ⚠️ **异常报告**：AI 审核问题汇总
- 📉 **历史对比**：成本趋势分析

</td>
<td width="50%">

### 📊 清单管理

- ✏️ **CRUD 操作**：项目级 BOQ 清单完整管理
- 📥 **批量导入**：支持 Excel 快速导入
- 🔗 **定额绑定**：清单项关联定额库
- 🤖 **AI 匹配**：智能推荐最佳定额

### 🤖 AI 助手

- 💬 **智能问答**：基于项目上下文的专业对话
- 💡 **优化建议**：供应商切换、材料替代方案
- 🔄 **多轮对话**：上下文记忆 + 工具调用
- 🔌 **多模型支持**：OpenAI / Claude / 自定义 LLM

### ⚙️ 系统配置

- 📐 **费率规则**：管理费、利润、税金配置
- 🔑 **AI 配置**：Provider、API Key、模型选择
- 💰 **价格库**：材料价格维护与更新
- 👥 **权限管理**：用户角色与访问控制

</td>
</tr>
</table>

## 🏗️ 技术架构

```mermaid
graph TB
    subgraph Frontend["🎨 前端层 (React + TypeScript)"]
        A1[Dashboard 仪表盘]
        A2[Projects 项目管理]
        A3[Drawings 图纸识别]
        A4[Pricing 计价管理]
        A5[Reports 报表中心]
    end
    
    subgraph Backend["⚙️ 后端层 (FastAPI)"]
        B1[Projects API]
        B2[BOQ API]
        B3[Pricing Engine]
        B4[AI Chat Service]
        B5[Validation Service]
    end
    
    subgraph AI["🤖 AI 服务层"]
        C1[OpenAI Provider]
        C2[Custom LLM]
        C3[Agent System]
    end
    
    subgraph Data["💾 数据层 (SQLite)"]
        D1[(Projects)]
        D2[(BOQ Items)]
        D3[(Bindings)]
        D4[(Calc Results)]
    end
    
    Frontend -->|REST API| Backend
    Backend -->|LLM Calls| AI
    Backend -->|ORM| Data
```

### 技术栈详情

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **前端框架** | React 18 + TypeScript | 类型安全的组件化开发 |
| **UI 库** | Ant Design + TailwindCSS | 企业级组件 + 原子化样式 |
| **状态管理** | React Hooks | 轻量级状态管理 |
| **构建工具** | Vite | 极速开发体验 |
| **后端框架** | FastAPI | 高性能异步 API |
| **ORM** | SQLAlchemy | 类型安全的数据库操作 |
| **数据库** | SQLite | 轻量级嵌入式数据库 |
| **AI 集成** | LangChain-like | 自研 Agent 框架 |
| **API 文档** | OpenAPI (Swagger) | 自动生成交互式文档 |

## 📦 项目结构

```
building cost/
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   ├── components/     # 通用组件
│   │   ├── api.ts          # API 接口定义
│   │   └── index.css       # 全局样式
│   └── package.json
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── ai/             # AI 服务
│   └── requirements.txt
├── docs/                     # 文档
├── docker-compose.yml        # 开发环境
└── README.md
```

## 🚀 快速开始

### 📋 环境要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.12+ | 后端运行环境 |
| Node.js | 18+ | 前端构建工具 |
| Git | 最新版 | 版本控制 |
| 操作系统 | macOS / Linux / Windows | 跨平台支持 |

### ⚡ 一键启动（推荐）

```bash
# 1. 克隆项目
git clone <repo-url>
cd "building cost"

# 2. 启动后端（新终端）
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

### 🌐 访问应用

| 服务 | 地址 | 说明 |
|------|------|------|
| 🎨 **前端应用** | http://localhost:5173 | React 用户界面 |
| ⚙️ **后端 API** | http://localhost:8000 | FastAPI 服务 |
| 📚 **API 文档** | http://localhost:8000/docs | Swagger UI |
| 🔧 **ReDoc** | http://localhost:8000/redoc | 备用文档 |

### 🤖 配置 AI（可选）

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：
```env
# OpenAI 配置
AI_PROVIDER=openai
AI_API_KEY=sk-your-api-key-here
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o

# 或使用兼容的本地模型
AI_PROVIDER=openai
AI_BASE_URL=http://localhost:11434/v1
AI_MODEL=qwen2.5:14b
```

3. 重启后端服务即可生效

## 📊 项目规模

### 代码统计

```
📦 总计 28,434 行代码
├── 🐍 Python         9,534 行  (后端逻辑 + AI 服务)
├── 📘 TypeScript/TSX 7,000 行  (前端组件 + API)
└── 🎨 CSS           11,900 行  (样式系统)
```

### 模块分布

| 模块 | 文件数 | 核心功能 |
|------|--------|----------|
| **后端 API** | 25+ | 路由、服务、模型定义 |
| **前端页面** | 12+ | Dashboard、项目、计价、图纸 |
| **AI 服务** | 8+ | Provider、Agent、工具调用 |
| **数据模型** | 15+ | SQLAlchemy ORM |
| **测试用例** | 10+ | 单元测试 + 集成测试 |

### 功能覆盖

- ✅ 7 个主要页面（Dashboard、项目、图纸、计价、报表、规则、设置）
- ✅ 30+ REST API 端点
- ✅ 15+ 数据库表
- ✅ 5+ AI Agent 工具
- ✅ 响应式设计（支持桌面端 + 平板）

## 🧪 开发指南

### 添加新页面
1. 在 `frontend/src/pages/` 创建组件
2. 在 `App.tsx` 添加路由
3. 在 `NAV_ITEMS` 添加导航项
4. 编写 CSS 样式（遵循 `dr-` 前缀规范）

### API 开发
1. 在 `backend/app/models/` 定义数据模型
2. 在 `backend/app/api/routes/` 添加路由
3. 在 `backend/app/services/` 实现业务逻辑
4. 更新 `frontend/src/api.ts` 接口定义

### AI 功能扩展
- 继承 `BaseAIProvider` 实现新 Provider
- 在 `agents/` 目录添加新 Agent
- 使用 `generate_with_tools()` 支持工具调用

## 📝 版本历史

<details>
<summary><b>🎯 Sprint 7 (2026-03) - 图纸识别与性能优化</b></summary>

- ✅ **图纸 AI 识别**：DrawingRecognition 页面，SVG 蓝图可视化
- ✅ **性能优化**：Dashboard 加载速度提升 5x（轻量级 API）
- ✅ **AI 统一**：全站 AI 助手接入真实后端（api.aiChat）
- ✅ **动态化**：UnitPriceAnalysis 替换所有 mock 数据
- 📦 代码量：+2,500 行

</details>

<details>
<summary><b>🤖 Sprint 6 (2025-02) - AI Agent 系统</b></summary>

- ✅ **智能估价**：AI Agent 自动定额匹配 + 绑定
- ✅ **工具调用**：7 个工具（search_quotas, bind_quota, calculate 等）
- ✅ **流式响应**：SSE 实时步骤展示
- ✅ **AgentPanel**：侧边栏 AI 交互组件
- 📦 代码量：+3,200 行

</details>

<details>
<summary><b>💰 Sprint 5 (2025-02) - 单价分析重构</b></summary>

- ✅ **页面重构**：UnitPriceAnalysis 完整改版
- ✅ **计算溯源**：费用分解可视化（人材机）
- ✅ **共享组件**：PageBreadcrumb 统一面包屑
- ✅ **详情优化**：ProjectDetail 数据流优化
- 📦 代码量：+1,800 行

</details>

<details>
<summary><b>📊 Sprint 4 (2025-01) - 计价管理</b></summary>

- ✅ **计价模块**：PricingManagement 完整实现
- ✅ **定额绑定**：BoqTab 绑定 UI + 批量操作
- ✅ **价格快照**：历史价格记录
- ✅ **批量操作**：多选 + 批量绑定/解绑
- 📦 代码量：+2,400 行

</details>

<details>
<summary><b>🗂️ Sprint 3 (2024-12) - 项目与清单</b></summary>

- ✅ **项目管理**：CRUD + 列表/详情页
- ✅ **BOQ 清单**：清单项管理 + 导入导出
- ✅ **数据验证**：前后端校验规则
- ✅ **Excel 支持**：批量导入清单
- 📦 代码量：+3,500 行

</details>

<details>
<summary><b>🎨 Sprint 2 (2024-11) - UI 基础</b></summary>

- ✅ **Dashboard**：数据总览 + 卡片布局
- ✅ **路由系统**：React Router 配置
- ✅ **主题系统**：暗色主题 + CSS 变量
- ✅ **响应式**：移动端适配
- 📦 代码量：+4,200 行

</details>

<details>
<summary><b>🚀 Sprint 1 (2024-10) - 项目初始化</b></summary>

- ✅ **架构设计**：前后端分离 + RESTful API
- ✅ **数据库**：SQLAlchemy ORM + SQLite
- ✅ **开发环境**：Docker Compose + 热重载
- ✅ **CI/CD**：代码规范 + 自动化测试
- 📦 代码量：+5,000 行（基础框架）

</details>

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 **非商用许可证** — 仅供学习、研究、演示使用，禁止任何商业用途。如需商用授权，请联系项目维护者。

## 📞 联系与支持

### 👨‍💻 项目维护者

- **姓名**：Bruce
- **角色**：全栈开发 + AI 架构
- **邮箱**：[your-email]

### 🔗 相关链接

- 📦 **项目仓库**：[GitHub Repo](repo-url)
- 📚 **在线文档**：[Documentation](docs-url)
- 🐛 **问题反馈**：[Issues](issues-url)
- 💬 **讨论区**：[Discussions](discussions-url)

### 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！贡献前请阅读 [贡献指南](#-贡献指南)。

### ⭐ 支持项目

如果这个项目对你有帮助，请考虑：

- ⭐ 给项目点个 Star
- 🔄 分享给更多开发者
- 💡 提出改进建议
- 🐛 报告 Bug

---

<div align="center">

**Built with ❤️ by Bruce**

*仅供学习研究使用 · 禁止商业用途*

</div>
