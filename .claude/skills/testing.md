# Skill：测试

## 触发条件
编写测试、输出测试报告时，读取本文件。

---

## TDD 循环（superpowers tdd）

调用 `superpowers: tdd` skill，强制执行 RED → GREEN → REFACTOR：

1. **RED**：先写失败的测试，确认它能捕捉到目标行为（运行看到红色才算）
2. **GREEN**：写最小实现让测试通过，不过度设计
3. **REFACTOR**：在测试保持绿色的前提下优化代码

**禁止先写实现再补测试。**

---

## 测试分层

| 层级 | 覆盖范围 | 工具 |
|---|---|---|
| 单元测试 | services/ 业务逻辑 | pytest |
| 集成测试 | API 路由 + DB | pytest + httpx |
| E2E 测试 | 完整用户流程 | gstack |

---

## 测试报告格式

复用 TODO 格式，每条打结果：

```
测试报告：
- ✅ JD 爬取 & 解析（Boss / 拉勾 / 猎聘）
- ✅ Human-in-the-Loop 确认节点响应
- ❌ Agent 调研超时处理（超时未返回降级结果）⚠️ 待修复
```

---

## 必测场景

每个功能上线前必须覆盖：

- **Happy Path** — 正常流程走通
- **Empty State** — 空输入 / 空结果
- **Error State** — 网络失败 / 第三方 API 超时
- **边界值** — 极长 JD、特殊字符、超大 PDF

---

## E2E 验证（gstack /qa）

涉及前端的功能必须运行 `gstack: /qa`，使用真实 Chromium 浏览器：

1. **JobInputForm 提交流程**：粘贴 JD URL → 触发爬取 → 进度流显示
2. **简历上传流程**：拖拽 PDF → 解析状态 → 成功反馈
3. **Human-in-the-Loop 确认弹窗**：职位确认 → 研究方向选择
4. **ReportCard 渲染**：六模块数据完整展示
5. **三态验证**：loading / error / empty 全部覆盖
6. **改动前后对比**：用 `ui_diff_check` 截图 before / after

gstack /qa 发现 bug → 自动修复 → 重新运行直到全绿。

---

## 强约束

- 测试有 ❌ 时禁止继续推进
- 每个新功能必须新增测试，不允许只改代码不加测试
- 禁止 mock 掉核心外部依赖（Firecrawl、Tavily）的集成测试
