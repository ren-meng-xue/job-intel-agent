# Skill：前端设计

## 触发条件
涉及 UI 设计、页面布局、组件开发、交互逻辑时，读取本文件。

---

## 流程

```
1. 头脑风暴（布局方案 + 交互状态）
2. 实现组件
3. 启动 dev server，用 gstack 验证
4. 生成 TODO 清单 + 截图证据
5. 等待用户回复「1」
6. commit
```

---

## Step 1：头脑风暴

实现前输出：
- 页面/组件布局方案（ASCII 草图或文字描述）
- 关键交互状态清单：loading / empty / error / success
- 响应式断点处理方式（mobile / desktop）

---

## Step 2：实现规范

- 组件放 `src/components/`，页面放 `src/app/`
- 样式只用 Tailwind CSS，**禁止内联 style**
- Loading / Error / Empty 三态必须实现，不允许只做 happy path
- 文案不硬编码在 JSX 里，提取为常量

---

## Step 3：gstack 验证（必须执行）

```
1. 打开目标页面，截图确认布局
2. 模拟关键交互（点击、表单提交、状态切换）
3. 验证 mobile / desktop 两个断点
4. 有改动时用 ui_diff_check 对比 before / after
```

**禁止跳过 gstack 直接 commit。截图是验证证据。**

---

## TODO 清单示例

```
TODO:
- [ ] JD 输入框组件 ⚠️ 风险：粘贴长 URL 的截断处理
- [ ] 简历上传拖拽区域
- [ ] Human-in-the-Loop 确认弹窗
- [ ] 报告页 6 模块布局
- [ ] Loading / Error / Empty 三态
- [ ] gstack 验证通过
```

---

## 禁止事项

- 禁止跳过 gstack 验证直接 commit
- 禁止只实现 happy path
- 禁止用内联 style 覆盖 Tailwind
