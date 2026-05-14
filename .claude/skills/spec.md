# Skill：Spec 设计文档

## 触发条件
开发**任何新功能、新 API、新模块**之前，必须先执行本 skill，完成 spec 后才能进入 `feature-dev.md` 流程。

---

## 流程（严格按顺序，不可跳步）

```
1. 读取项目上下文（相关文件、最近 commit、现有模型/接口）
2. 头脑风暴：提出 2-3 个方案 + 每个方案的风险 + 推荐
3. 用户确认方案
4. 写 spec 文件 → docs/specs/YYYY-MM-DD-<feature>/spec.md
5. 生成流程图 → docs/specs/YYYY-MM-DD-<feature>/flow.html
6. 展示 spec 路径，提示用户 review
7. 用户确认后，转入 feature-dev.md 流程
```

**不允许跳过 spec 直接写代码。**

---

## Step 2：头脑风暴输出格式

```
方案 A：XXX
- 实现思路：
- 风险：

方案 B：XXX
- 实现思路：
- 风险：

推荐方案：A / B，理由：
```

---

## Step 4：Spec 文件结构

保存路径：`docs/specs/YYYY-MM-DD-<feature>/spec.md`

```markdown
# Spec: [功能名称]

**日期：** YYYY-MM-DD
**状态：** Draft / Approved
**关联流程图：** [flow.html](./flow.html)

---

## 目标

一句话说清楚这个功能解决什么问题、对谁有价值。

---

## 核心流程

（文字描述主流程，配合 flow.html 阅读）

---

## 技术方案

- **采用方案：** XXX
- **关键决策理由：** XXX
- **依赖的现有模块：** XXX

---

## API 设计

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/xxx | ... |

请求体：
```json
{}
```

响应：
```json
{}
```

---

## 数据模型

新增 / 修改的字段（需走 Alembic 迁移）：

| 表 | 字段 | 类型 | 说明 |
|----|------|------|------|

---

## 边界 & 不做的事

- ✅ 做：XXX
- ❌ 不做：XXX（原因）

---

## TODO 清单

- [ ] 任务描述（≤20 字）⚠️ 风险：XXX
- [ ] 任务描述

---

## 测试计划

- 正常路径：XXX
- 边界用例：XXX
- 错误路径：XXX
```

---

## Step 5：流程图生成规范

生成 `flow.html`，产物为**可直接浏览器打开的自包含 HTML 文件**，零外部依赖。

### 节点形状（遵循 superpowers Graphviz 约定）

| 形状 | 含义 |
|------|------|
| 菱形 | 决策节点（yes / no 分支） |
| 圆角矩形 | 操作步骤 |
| 双圆 | 开始 / 结束 |
| 八边形（红色） | 警告 / 禁止操作 |
| 椭圆 | 状态描述 |
| 纯文本节点 | 命令行指令 |

### 视觉设计规范

**生成前先明确（Design Thinking）：**
- 这张图要让读者理解什么流程？谁来看（开发者 / 产品 / 用户）？
- 选择一个明确的风格并贯彻到底（技术文档风 / 产品原型风 / 极简风）
- 这张图和默认灰色方块图的差异在哪里？

**Typography（字体）**
- 节点文字：`'Inter', system-ui, sans-serif`
- 命令节点：`'SF Mono', 'Fira Code', monospace`
- 字号分层：标题 14px / 正文 12px / 标签 10px

**Color & Theme（配色，使用 CSS Variables）**
```css
--bg: #0f172a;
--surface: #1e293b;
--border: #334155;
--text: #f1f5f9;
--muted: #94a3b8;
--action: #3b82f6;      /* 操作节点 */
--success: #10b981;     /* 成功 / 结束节点 */
--warning: #f59e0b;     /* 警告节点 */
--danger: #ef4444;      /* 禁止 / 错误节点 */
--decision: #8b5cf6;    /* 决策菱形 */
--start: #06b6d4;       /* 开始节点 */
```

**Motion（动画）**
- 节点入场：`fadeInUp 0.4s ease` + `animation-delay` 交错（每个节点延迟 80ms）
- 连接线：`stroke-dashoffset` 动画，线条从起点到终点逐渐绘出
- hover：节点 `scale(1.04)` + `box-shadow` glow 效果

**Spatial Composition（布局）**
- 主干流程纵向居中
- 分支节点左右对称排列，用对角线箭头体现流动感
- 节点间距均匀（SVG viewBox 内 padding ≥ 40px）
- 背景：深色渐变 mesh 或细微噪点纹理，不用纯色

**连接线 & 标签**
- 箭头：SVG bezier 曲线（`<path>` + `stroke-linecap: round`）
- 分支标签（yes / no）：小圆角 badge，背景色与决策节点呼应
- 箭头末端：实心三角 `marker-end`

**严禁出现**
- 默认灰色方块 + 黑色直线
- 无字体、无配色的纯功能图
- 白底蓝字渐变（AI 滥用配色）
- 所有节点大小一致、无视觉层级
- 节点文字溢出或重叠

---

## 完成标志

spec 文件 + flow.html 均已生成，展示给用户确认，
用户回复确认后方可进入 `feature-dev.md` 流程。
