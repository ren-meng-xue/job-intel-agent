# JD 输入方式 Tab 重设计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `JobInputForm.tsx` 的「URL 主 + 隐藏手动面板」改为三 Tab 并列（🔗 粘贴链接 / 📋 输入内容 / 📸 上传截图），URL 失败时自动切换至「输入内容」Tab 并展示黄色容错提示。

**Architecture:** 纯前端组件重构，无后端变更。将 `showManualInput: boolean` 状态替换为 `activeTab: 'url' | 'text' | 'image'`，新增 `isFallback: boolean` 标记自动切换场景。SSE 逻辑不变，`awaiting_manual_input` 事件触发 Tab 自动切换。

**Tech Stack:** Next.js 14 App Router + TypeScript + Tailwind CSS（inline className，无新依赖）

---

## 文件变更总览

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `frontend/src/components/JobInputForm.tsx` | 唯一改动文件，全量重写 JSX + 状态 |

---

## Task 1：重构 State，移除 `showManualInput`

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`（状态声明部分，约第 22-35 行）

- [ ] **Step 1：替换状态声明**

将现有：
```ts
const [showManualInput, setShowManualInput] = useState(false);
const [pendingJobId, setPendingJobId] = useState<string | null>(null);
```
替换为：
```ts
type Tab = 'url' | 'text' | 'image';
const [activeTab, setActiveTab] = useState<Tab>('url');
const [isFallback, setIsFallback] = useState(false);   // true = 由 URL 失败自动切换
const [pendingJobId, setPendingJobId] = useState<string | null>(null);
```

- [ ] **Step 2：更新 SSE 事件处理器中的 `awaiting_manual_input` 分支**

找到 `subscribeToJob` 函数内的 `awaiting_manual_input` 分支（约第 72-77 行），改为：
```ts
} else if (event.type === "awaiting_manual_input") {
  cleanupSSE();
  setLoading(false);
  setManualLoading(false);
  setPendingJobId(id);
  setActiveTab('text');   // 自动切到文本 Tab
  setIsFallback(true);    // 标记为容错模式，展示黄色 banner
  setError("");
}
```

- [ ] **Step 3：新增 Tab 切换 handler**

在 `handleUrlSubmit` 之前插入：
```ts
function handleTabChange(tab: Tab) {
  setActiveTab(tab);
  setIsFallback(false);  // 用户主动切换时清除容错 banner
  setError("");
  setManualError("");
}
```

---

## Task 2：实现 Tab 栏 UI

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`（JSX return 部分）

- [ ] **Step 1：用 Tab 栏替换顶部结构**

将整个 `return (...)` 块替换为以下结构（下面 Task 3–5 会填充各 Tab 内容）：

```tsx
return (
  <div className="space-y-4">
    {/* Tab 导航栏 */}
    <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
      {(
        [
          { key: 'url',   icon: '🔗', label: '粘贴链接' },
          { key: 'text',  icon: '📋', label: '输入内容' },
          { key: 'image', icon: '📸', label: '上传截图' },
        ] as { key: Tab; icon: string; label: string }[]
      ).map(({ key, icon, label }) => (
        <button
          key={key}
          type="button"
          onClick={() => handleTabChange(key)}
          className={`flex-1 flex flex-col items-center py-2 px-1 rounded-lg text-xs font-medium transition-all ${
            activeTab === key
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <span className="text-sm mb-0.5">{icon}</span>
          {label}
        </button>
      ))}
    </div>

    {/* Tab 内容区（Task 3–5 填充） */}
    {activeTab === 'url'   && <UrlTab />}
    {activeTab === 'text'  && <TextTab />}
    {activeTab === 'image' && <ImageTab />}
  </div>
);
```

> 注意：`<UrlTab />`、`<TextTab />`、`<ImageTab />` 是下面三个 Task 内定义的内联函数组件占位符，最终实现时直接内联 JSX，不抽为独立文件（避免 prop drilling）。

---

## Task 3：实现「粘贴链接」Tab 内容

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`

- [ ] **Step 1：将 URL Tab 内联 JSX 替换到 return 块中**

把 `{activeTab === 'url' && <UrlTab />}` 替换为：

```tsx
{activeTab === 'url' && (
  <div className="space-y-3">
    {loading ? (
      <div className="py-4">
        <AICoreLoader
          size="md"
          label="AI 正在解析职位描述..."
          subLabel="抓取页面信息 → LLM 提取关键字段"
        />
      </div>
    ) : (
      <form onSubmit={handleUrlSubmit} className="space-y-3">
        <input
          type="url"
          placeholder="粘贴 JD 链接（Boss直聘 / 拉勾 / 猎聘等）"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <ResumeUpload onFileSelect={setResumeFile} />
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}
        <button
          type="submit"
          disabled={loading || !url}
          className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
        >
          开始分析
        </button>
      </form>
    )}
  </div>
)}
```

---

## Task 4：实现「输入内容」Tab 内容

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`

- [ ] **Step 1：将 Text Tab 内联 JSX 替换到 return 块中**

把 `{activeTab === 'text' && <TextTab />}` 替换为：

```tsx
{activeTab === 'text' && (
  <div className="space-y-3">
    {/* 容错 banner：仅当由 URL 失败自动切换时显示 */}
    {isFallback && (
      <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
        <span className="mt-0.5 flex-shrink-0">⚠️</span>
        <span>未能从该链接自动提取内容，请直接粘贴职位描述文本</span>
      </div>
    )}

    {manualLoading ? (
      <div className="py-2">
        <DataStreamLoader label="正在提取职位信息…" particleCount={8} />
      </div>
    ) : (
      <div className="space-y-3">
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="将 JD 全文粘贴到此处..."
          rows={6}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
        <ResumeUpload onFileSelect={setResumeFile} />
        {manualError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{manualError}</p>
        )}
        <button
          type="button"
          onClick={handleManualSubmit}
          disabled={!rawText.trim()}
          className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
        >
          开始分析
        </button>
      </div>
    )}
  </div>
)}
```

- [ ] **Step 2：确认 `handleManualSubmit` 中的文本分支逻辑不变**

确认以下逻辑仍在 `handleManualSubmit` 中（无需修改）：
```ts
if (hasImages) {
  const job = await createJobFromImages(images, rid);
  id = job.id;
} else if (pendingJobId) {
  await submitRawContent(pendingJobId, rawText.trim());
  id = pendingJobId;
} else {
  const job = await createJobFromText(rawText.trim(), rid);
  id = job.id;
}
```
当 `isFallback=true` 时 `pendingJobId` 一定不为 null，走 `submitRawContent` 分支，正确。

---

## Task 5：实现「上传截图」Tab 内容

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`

- [ ] **Step 1：将 Image Tab 内联 JSX 替换到 return 块中**

把 `{activeTab === 'image' && <ImageTab />}` 替换为：

```tsx
{activeTab === 'image' && (
  <div className="space-y-3">
    {manualLoading ? (
      <div className="py-2">
        <DataStreamLoader label="正在提取职位信息…" particleCount={8} />
      </div>
    ) : (
      <div className="space-y-3">
        <p className="text-sm font-medium text-gray-700">上传 JD 截图（最多 3 张）</p>
        <div className="flex flex-wrap gap-2">
          {imagePreviews.map((src, i) => (
            <div key={i} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt={`截图 ${i + 1}`}
                className="h-20 w-20 rounded object-cover border border-gray-200"
              />
              <button
                type="button"
                onClick={() => removeImage(i)}
                className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white text-xs leading-none"
              >
                ×
              </button>
            </div>
          ))}
          {images.length < 3 && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex h-20 w-20 items-center justify-center rounded border-2 border-dashed border-gray-300 text-2xl text-gray-400 hover:border-blue-400 hover:text-blue-400"
            >
              +
            </button>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleImageSelect}
        />
        <ResumeUpload onFileSelect={setResumeFile} />
        {manualError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{manualError}</p>
        )}
        <button
          type="button"
          onClick={handleManualSubmit}
          disabled={images.length === 0}
          className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
        >
          开始分析
        </button>
      </div>
    )}
  </div>
)}
```

---

## Task 6：最终整合 & 清理

**Files:**
- Modify: `frontend/src/components/JobInputForm.tsx`

- [ ] **Step 1：删除已无引用的代码**

删除以下内容（已被 Tab 结构替代）：
- `showManualInput` 相关的所有引用（state 声明、`setShowManualInput` 调用）
- 原 `{!showManualInput && <p>没有链接？...</p>}` 段落
- 原 `{showManualInput && <div className="rounded-xl border border-amber-200 ...">` 整个手动面板块

- [ ] **Step 2：TypeScript 编译检查**

```bash
cd frontend && pnpm tsc --noEmit
```
预期：0 错误。若有类型报错，修复后重试。

- [ ] **Step 3：启动开发服务器验证**

```bash
cd frontend && pnpm dev
```
打开 http://localhost:3000，手动验证：
1. 默认显示「粘贴链接」Tab，URL 输入框可用
2. 点击「输入内容」Tab → 切换到文本框，无 banner
3. 点击「上传截图」Tab → 显示图片上传区
4. 切回「粘贴链接」Tab → URL 输入框恢复
5. （如可测试）提交一个无效 URL → 应自动切换到「输入内容」Tab 并显示黄色 banner

- [ ] **Step 4：Commit**

```bash
git add frontend/src/components/JobInputForm.tsx
git commit -m "feat: JD 输入改为三 Tab（链接/文本/截图）+ URL 失败容错自动切换"
```
