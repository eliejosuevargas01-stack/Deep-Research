# 测试与基础设施 Spec（S0 基础层）

> 生成时间：2026-10-06  
> 对应 spec：§10 管道审计质量，§6 安全边界，§8 集成管道

---

## 一、测试结构总览

```
tests/
├── __init__.py
├── test_backend.py              # 后端 API 单元测试（214 LOC）
├── test_e2e_criteria.py         # E2E 质量指标断言
├── test_postgres.py             # PostgreSQL 连接与健康检查
├── integration/
│   ├── __init__.py
│   └── test_full_pipeline.py    # 完整管道集成测试
└── unit/
    └── workers/
        └── test_workers_and_auditor.py  # 工作器+审计单元
```

---

## 二、各测试文件说明

### tests/test_backend.py（214 LOC）

**覆盖范围：**
- 认证流程（JWT session / Bearer token / API key）
- CSRF token 校验
- Research 创建、状态机流转（scouting → in_progress → completed）
- Settings 接口（加密凭据的 encrypt/decrypt/mask）
- Research Point 依赖关系校验
- 管道各阶段状态转换

**信任级别：🟡**  
- 最近有改动（git diff 显示），需回归验证
- 部分断言依赖 mock LLM，未测真实管道

---

### tests/test_e2e_criteria.py

**覆盖范围：**
- QA_MATRIX.md 中定义的端到端质量指标
- 报告完整性断言（字数、引用数、heading 覆盖）
- Evidence grounding 检验

**信任级别：🟡**  
- 指标定义完整，但执行需真实 LLM 环境

---

### tests/test_postgres.py

**覆盖范围：**
- PostgreSQL 连接字符串有效性
- Alembic migration 状态
- AsyncSession 生命周期

**信任级别：🟢**  
- 纯基础设施测试，无业务逻辑

---

### tests/integration/test_full_pipeline.py

**覆盖范围：**
- 完整管道：scout → persona workers → audit → writer
- 模拟外部搜索（Jina proxy / SERPAPI）
- 状态持久化验证
- 错误恢复（timeout / worker failure）

**信任级别：🟡**  
- 最近有改动（git diff 显示）
- 依赖外部 LLM 服务，本地 CI 可能跳过

---

### tests/unit/workers/test_workers_and_auditor.py

**覆盖范围：**
- 单个 persona worker 输出格式
- Auditor 评分逻辑
- Retry loop 行为（MAX_AUDIT_ATTEMPTS）

**信任级别：🟡**  
- 单元测试粒度，但 mock 覆盖不完整

---

## 三、CI/CD 配置

### .github/workflows/ci.yml

```yaml
matrix:
  python-version: ["3.11"]
steps:
  - pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80
  - docker build -t deep-research-backend .
```

**说明：**
- Python 3.11 单版本矩阵
- 覆盖率门槛：80%
- 仅后端 Docker build，不含前端

---

## 四、基础设施 Spec

| 项目 | 状态 | 说明 |
|------|------|------|
| PostgreSQL 16 | 🟢 | docker-compose db 服务 |
| Alembic migrations | 🟢 | 5 次迁移（含 jina_proxy_worker） |
| Nginx（前端） | 🟢 | frontend/nginx.conf |
| Docker multi-stage | 🟡 | 后端 Dockerfile 多阶段，frontend Dockerfile 独立 |
| Env var 管理 | 🟡 | .env.example 与 .env 不同步风险 |

---

## 五、Gap 与 TODO

1. **Frontend 无独立测试**：frontend/tests/frontend.test.mjs 存在但未纳入 CI
2. **Integration test 依赖外部服务**：Jina proxy / SERPAPI key 需注入
3. **E2E test 需真实 LLM**：QA_MATRIX.md §10 断言在 mock 环境下无法完全验证
4. **覆盖率 gaps**：app/services/llm.py（578 LOC）和 app/services/search.py（353 LOC）测试覆盖不足

---

## 六、参考

- `QA_MATRIX.md` — 质量验收完整矩阵
- `app/CRITERIA.md` — 前端验收标准
- `contracts.md §10–11` — 管道与审计契约
