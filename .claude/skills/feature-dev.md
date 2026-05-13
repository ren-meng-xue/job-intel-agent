# Skill：功能开发

## 触发条件
开发新功能、新 API、新模块时，读取本文件。

---

## 流程（严格按顺序，不可跳步）

```
0. 需求澄清（superpowers brainstorming）
1. 头脑风暴
2. 实现
3. 生成 TODO 清单
4. 测试 → 测试报告
5. 代码审查（gstack /review）
6. 更新 Changelog 并展示
7. 等待用户回复「1」
8. commit → push
```

---

## 编码规范（所有代码必须遵守）

- 所有注释使用**简体中文**
- 函数、类、模块顶部写一行中文说明其职责
- 复杂逻辑行内加中文注释，说明「为什么」而非「是什么」
- 禁止写无意义注释（如 `# 定义变量 x`）

---

## Step 0：需求澄清（superpowers brainstorming）

调用 `superpowers: brainstorming` skill，通过苏格拉底式提问明确功能边界：
- 待解决的核心问题是什么？
- 谁是用户，他们的成功标准是什么？
- 有哪些约束和非目标？

输出分段规格书：**Problem / Solution / Constraints / Acceptance Criteria**，
用户确认后再进入 Step 1。**功能模糊时必须执行，不允许跳过。**

---

## Step 1：头脑风暴

实现前必须输出：
- 可能的实现方案（2-3 个）
- 每个方案的风险点
- 推荐方案及理由

**不允许跳过直接写代码。**

---

## Step 3：TODO 清单格式

```
TODO:
- [ ] 任务描述（一句话，≤20 字）⚠️ 风险：具体原因
- [ ] 任务描述
- [ ] 任务描述
```

规则：
- 每条一句话，精简
- 有风险的条目标注 `⚠️ 风险：原因`
- 顺序按执行依赖排列

---

## Step 4：测试报告格式

```
测试报告：
- ✅ 任务描述
- ✅ 任务描述
- ❌ 任务描述（失败原因）
```

测试有 ❌ 时，禁止继续推进，必须先修复。

---

## Step 5：代码审查（gstack /review）

提交前运行 `gstack: /review`：
- 检查代码质量、潜在安全隐患、性能问题
- 自动修复发现的问题
- 审查通过后才能进入 Step 6

---

## Step 6：Changelog 格式

路径：`changelogs/YYYY-MM-DD.md`

```markdown
- [x] 🚀 实现了 XXX 功能
- [x] 🐛 修复了 XXX 问题
- [x] ♻️ 重构了 XXX 模块
- [x] 📝 更新了 XXX 配置
```

Emoji：🚀 新功能 / 🐛 修复 / ♻️ 重构 / 📝 文档配置

写完后展示给用户，等回复「1」才能 commit。

---

## 并行子任务（superpowers subagent-driven-development）

开发多个相互独立的模块时（如 LangGraph 各 Node 并行开发），
调用 `superpowers: subagent-driven-development`：
- 将任务分解为 2-5 分钟微任务
- 每个子代理持有精确的文件路径 + 完整代码片段
- 两阶段审查：规格符合性 → 代码质量
- 适用场景：开发 Agent Graph 多个节点、前后端并行开发
