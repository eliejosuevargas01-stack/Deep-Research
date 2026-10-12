# 仓库地图（S0 基础层）

> 生成时间：2026-10-06  
> 分支：main  
> Git 状态：有未提交修改（见文末"已修改文件"节）

---

## 一、Git 状态

```
M  .reversa/active-requirements.json
M  app/models/domain_models.py
M  app/prompts/*.md（auditor/historian/futurist/pragmatist/skeptic/writer）
M  app/routers/settings.py
M  app/schemas/__init__.py
M  app/services/audit.py
M  app/services/llm.py
M  app/services/pipeline/audit_stage.py, scout.py, worker.py
M  app/services/search.py
M  app/services/settings.py
M  app/services/workers/base.py
M  frontend/src/main.tsx, research-utils.ts, types.ts
M  tests/integration/test_full_pipeline.py
M  tests/test_backend.py
?? _reversa_forward/001-jina-proxy-worker/
?? alembic/versions/0005_jina_proxy_worker.py
```

---

## 二、文档矩阵（canonical docs）

| 文件 | 内容概述 | 与 spec 编号对应 |
|------|---------|----------------|
| `GOAL.md` | 项目目标：Deep Research 多智能体研究管道，含 S0–S3 分层 | 整体蓝图 |
| `contracts.md` | API 契约、数据模型约束、安全边界定义 | §1–§11 |
| `workflow.md` | 管道工作流：scout → writer → audit → report | §8–§10 |
| `plan.md` | 实现计划：阶段划分与里程碑 | S0–S3 |
| `QA_MATRIX.md` | 质量验收矩阵：每项 spec 的测试覆盖状态 | §1–§11 |
| `TASKS.md` | 待办任务清单（含优先级和状态） | — |
| `README.md` | 快速入门与部署说明 | — |
| `app/CRITERIA.md` | 前端质量验收标准 | 前端 spec |
| `frontend/DESIGN.md` | 设计系统规范（tokens/colors/layout） | 前端 spec |
| `frontend/PLAN.md` | 前端实现计划 | 前端 spec |

---

## 三、模块 → 文件 → LOC → 对应 spec

### app/（后端核心）

| 路径 | LOC | spec 对应 | 信任级别 |
|------|-----|----------|---------|
| `app/main.py` | 81 | §7 路由注册 | 🟢 |
| `app/core/config.py` | 57 | §6 配置管理 | 🟢 |
| `app/core/security.py` | 114 | §6 安全 | 🟢 |
| `app/db/database.py` | 48 | §2 DB 连接 | 🟢 |
| `app/models/domain_models.py` | 128 | §2 数据模型 | 🟢 |
| `app/routers/research.py` | 427 | §8–§10 研究管道 | 🟢 |
| `app/routers/settings.py` | 99 | §3 设置 | 🟢 |
| `app/routers/auth.py` | 49 | §6 认证 | 🟢 |
| `app/schemas/__init__.py` | 157 | §2 数据校验 | 🟢 |
| `app/services/llm.py` | 578 | §8 LLM 调用 | 🟡 |
| `app/services/search.py` | 353 | §9 搜索管道 | 🟡 |
| `app/services/settings.py` | 421 | §3 设置服务 | 🟡 |
| `app/services/research.py` | 161 | §8–§10 研究服务 | 🟡 |
| `app/services/pipeline/worker.py` | 198 | §9 管道工作器 | 🟡 |
| `app/services/pipeline/scout.py` | 144 | §8 scout 阶段 | 🟡 |
| `app/services/pipeline/writer.py` | 78 | §10 writer 阶段 | 🟡 |
| `app/services/pipeline/audit_stage.py` | 146 | §10 审计阶段 | 🟡 |
| `app/services/pipeline/point_executor.py` | 76 | §9 执行单元 | 🟡 |
| `app/services/workers/base.py` | 83 | §9 工作器基类 | 🟡 |
| `app/services/workers/personas.py` | 72 | §9 角色工作器 | 🟡 |
| `app/services/workers/scout.py` | 38 | §8 scout 工作器 | 🟡 |
| `app/services/workers/writer.py` | 39 | §10 writer 工作器 | 🟡 |
| `app/tools/outbound.py` | 51 | §6 SSRF 防护 | 🔴 |
| `app/tools/search_pipeline.py` | 230 | §9 搜索工具 | 🟡 |
| `app/services/audit.py` | 52 | §10 审计服务 | 🟡 |
| `app/services/audit_agent.py` | 51 | §10 审计 Agent | 🟡 |
| `app/services/crypto.py` | 32 | §6 加密服务 | 🟢 |
| `app/services/webhook.py` | 56 | §10 webhook | 🟡 |
| `app/tools/__init__.py` | — | — | 🟢 |

**app/ 合计 LOC：4,115**

---

### frontend/（前端核心）

| 路径 | LOC | spec 对应 | 信任级别 |
|------|-----|----------|---------|
| `frontend/src/main.tsx` | 2,697 | §7 前端入口+UI | 🟡 |
| `frontend/src/types.ts` | 87 | §2 类型定义 | 🟢 |
| `frontend/src/api.ts` | 132 | §7 API 调用 | 🟢 |
| `frontend/src/ui.tsx` | 85 | §7 UI 组件 | 🟡 |
| `frontend/src/research-utils.ts` | 561 | §8 研究工具函数 | 🟡 |
| `frontend/src/routes.ts` | 33 | §7 路由配置 | 🟢 |
| `frontend/src/style.css` | 2,090 | §前端设计规范 | 🟢 |
| `frontend/src/components.css` | 347 | §前端组件样式 | 🟢 |
| `frontend/src/tokens.css` | 272 | §前端设计 tokens | 🟢 |

**frontend/src/ 合计 LOC：6,304**

---

### tests/（测试）

| 路径 | LOC | 覆盖范围 | 信任级别 |
|------|-----|---------|---------|
| `tests/test_backend.py` | 214 | 后端 API 单元测试 | 🟡 |
| `tests/test_e2e_criteria.py` | — | E2E 质量指标 | 🟡 |
| `tests/test_postgres.py` | — | PostgreSQL 连接 | 🟢 |
| `tests/integration/test_full_pipeline.py` | — | 完整管道集成测试 | 🟡 |
| `tests/unit/workers/test_workers_and_auditor.py` | — | 工作器+审计单元 | 🟡 |

---

## 四、信令标记说明

| 标记 | 含义 | 应用对象 |
|------|------|---------|
| 🟢 **可信任** | 代码与文档均经过 review，无已知问题 | config, security, database, schemas |
| 🟡 **需审查** | 功能正确但存在已知 gap 或近期改动 | llm service, search, pipeline workers |
| 🔴 **不可信任** | 存在安全问题或逻辑缺陷 | outbound SSRF guard（URL 解析漏洞） |

---

## 五、已知 Gap

1. **app/tools/outbound.py**: `validate_public_url` 对某些边缘 URL（如 `http://[::1]`）存在绕过风险（🔴）
2. **app/services/llm.py**: LiteLLM 安全传输补丁不完整，某些分支未覆盖（🟡）
3. **app/services/pipeline/scout.py:65–67**: 死代码——第二条 `raise RuntimeError` 永远不可达
4. **tests/**: 覆盖率门槛 80%（CI），但当前实测略低于此值（需验证）

---

## 六、docker-compose / Dockerfile

| 文件 | 行数 | 说明 |
|------|------|------|
| `docker-compose.yml` | 35 | db+backend+frontend 三服务编排 |
| `Dockerfile` | 61 | 后端构建（多阶段） |
| `frontend/Dockerfile` | 38 | 前端 Nginx 生产镜像 |
| `requirements.txt` | 30 | Python 依赖（含 litellm, aiohttp, cryptography） |
