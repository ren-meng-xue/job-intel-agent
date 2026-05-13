# Skill：部署

## 触发条件
部署上线、环境配置、数据库迁移时，读取本文件。

---

## 部署前 Checklist

```
- [ ] 所有环境变量已配置（对照 .env.example）⚠️ 风险：缺 Key 导致静默失败
- [ ] Alembic migration 已生成并 review
- [ ] 测试报告全部 ✅
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

## 回滚方案

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>
```
