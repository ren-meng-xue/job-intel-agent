# Skill：部署

## 触发条件
部署上线、环境配置、数据库迁移时，读取本文件。

---

## 部署前 Checklist

```
- [ ] 所有环境变量已配置（对照 .env.example）⚠️ 风险：缺 Key 导致静默失败
- [ ] Alembic migration 已生成并 review
- [ ] 测试报告全部 ✅
- [ ] 安全审计通过（gstack /cso 置信度 ≥ 8/10）⚠️ 风险：OWASP Top 10 漏洞
- [ ] 用户回复「1」确认
```

---

## 环境变量清单（必须齐全）

```
# LLM
OPENAI_API_KEY=

# 爬取 & 搜索
FIRECRAWL_API_KEY=
TAVILY_API_KEY=

# 数据库
DATABASE_URL=
REDIS_URL=

# 存储（如用到）
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET_NAME=
```

---

## Docker Compose 启动顺序

```
1. postgres + redis（基础依赖）
2. alembic upgrade head（数据库迁移）
3. backend（FastAPI）
4. celery worker
5. frontend（Next.js）
```

**禁止跳过 migration 直接启动 backend。**

---

## 数据库迁移规范

```bash
# 生成迁移文件
alembic revision --autogenerate -m "描述"

# 迁移前必须 review 生成的文件，确认无误
# 再执行
alembic upgrade head
```

- 禁止直接修改数据库表结构
- 禁止删除迁移文件
- 每次迁移必须可回滚（检查 downgrade() 函数）

---

## 安全审计（gstack /cso）— 上线前必跑

运行 `gstack: /cso` 执行 OWASP Top 10 + STRIDE 威胁建模：

- SQL 注入 / XSS / IDOR / 未授权 API 端点
- 环境变量泄漏（hardcoded secrets 扫描）
- Celery 任务越权（job_id 归属校验）
- FastAPI 路由认证缺失检查

**置信度 < 8/10 的发现必须修复后才能继续部署。**

---

## 发布（gstack /ship）

运行 `gstack: /ship` 执行标准发布流程：
1. 运行完整测试套件（pytest + gstack /qa）
2. 创建 PR，自动生成 Release Notes
3. 等待用户回复「1」后合并

---

## 回滚方案

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>
```
