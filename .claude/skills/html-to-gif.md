# Skill：HTML 录屏转 GIF / 视频

## 触发条件
用户要求将 HTML 页面、UI 原型、交互演示录制为 GIF 或视频时，读取本文件。

---

## 工具链

| 工具 | 用途 | 安装 |
|------|------|------|
| **Playwright** | 浏览器自动化，打开 HTML 并操控页面切换、录制视频 | `npx playwright install chromium`（若无） |
| **ffmpeg** | 视频 → GIF 转换、压缩优化 | `brew install ffmpeg` |

---

## 流程

```
1. 确认录制范围与时间分配（哪些屏幕 / 每屏停留多久）
2. 编写 Playwright 录制脚本
3. 执行脚本，生成 .webm 视频
4. ffmpeg 转 GIF（优化体积 + 控制质量）
5. 验证 GIF，展示给用户
```

---

## Step 1：确认时间线与交互步骤

动手前和用户确认：
- **要录制哪些页面/状态**（如：登录 → 注册 tab → 首页 → 报告）
- **每屏停留时长**（推荐 1.5-4s，重点页面多留）
- **目标时长**（15-20s 快节奏 / 30-45s 完整演示）
- **触发哪些交互**（点击、切换 tab、滚动等）
- **输出格式**（GIF / MP4 / WebM）

---

## Step 2：编写 Playwright 录制脚本

关键模板：

```javascript
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: '/tmp/playwright-videos' }  // 录视频
  });
  const page = await context.newPage();

  const htmlPath = '/absolute/path/to/file.html';
  await page.goto(`file://${htmlPath}`);

  // 按时间线操控页面
  await page.waitForTimeout(1500);                    // 默认状态停留
  await page.evaluate(() => switchAuthTab('register')); // 切换 tab
  await page.waitForTimeout(2000);
  await page.evaluate(() => switchAuthTab('login'));
  await page.waitForTimeout(1000);
  await page.evaluate(() => showScreen('home'));
  // ... 继续其他屏幕

  await browser.close();
  // 视频文件在 context.close() 后写入磁盘
})();
```

**注意事项：**
- `recordVideo.dir` 必须是已存在的目录
- 视频在 `browser.close()` 后才会最终写入
- viewport 建议 1280x800（16:10 适合网页嵌入）
- 路径必须用绝对路径，`file://` 协议

---

## Step 3：执行脚本

```bash
node /tmp/record-demo.js
```

执行后记录视频输出路径，通常是 `/tmp/playwright-videos/<random>.webm`。

---

## Step 4：ffmpeg 转 GIF

```bash
ffmpeg -i /tmp/playwright-videos/<video>.webm \
  -vf "fps=12,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" \
  /output/path/demo.gif
```

**参数说明：**

| 参数 | 含义 | 调整建议 |
|------|------|----------|
| `fps=12` | 12 帧/秒 | 8-15，越低文件越小 |
| `scale=900:-1` | 宽度 900px，高度按比例 | 按目标嵌入宽度调整 |
| `max_colors=128` | 调色板最多 128 色 | 64-256，越低越小但有色差 |
| `dither=bayer:bayer_scale=3` | 抖动算法减少色带 | bayer 比 floyd_steinberg 更适合 UI |

**减小体积技巧：**
- 降 fps：`fps=10` 或 `fps=8`
- 缩尺寸：`scale=700:-1`
- 减色：`max_colors=64`
- 裁切：加 `crop=w:h:x:y` 去掉不必要的区域

---

## Step 5：验证

- 浏览器打开 GIF 文件确认动画流畅
- 检查文件大小（目标 < 5MB，适合网页嵌入）
- 确认所有关键屏幕和交互都已录到

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 视频只录了一部分 | `browser.close()` 前没等够 | 最后加 `await page.waitForTimeout(1000)` |
| GIF 太大（>10MB） | 颜色/帧率过高 | 降 fps 到 8，max_colors 到 64 |
| CSS 动画不流畅 | fps 太低 | fps 提升到 15 |
| `file://` 页面资源加载失败 | 相对路径问题 | HTML 内所有资源用绝对路径或 CDN |

---

## 禁止事项

- 禁止跳过用户确认时间线直接录制
- 禁止用截图逐帧拼接代替视频录制（会丢失 CSS 动画）
- 禁止使用默认 viewport 太小（至少 1280x720）
