/** Playwright 视频录制 — 完整 job-intel-agent 端到端测试（图片上传模式）*/
import { chromium } from 'playwright';
import path from 'path';

const BASE        = 'http://localhost:3001';
const EMAIL       = '917596600@qq.com';
const PASSWORD    = 'qq1.2.3.';
const JOB_IMAGE   = '/Users/xuebao/Desktop/1.png';
const RESUME_PDF  = '/Users/xuebao/Desktop/任孟雪WEB前端工程师.pdf';
const VIDEO_DIR   = '/tmp/playwright-videos';

function log(msg) {
  console.log(`[${new Date().toLocaleTimeString()}] ${msg}`);
}

async function main() {
  const browser = await chromium.launch({
    headless: false,
    slowMo: 600,
    args: ['--no-proxy-server'], // 强制不走系统代理，避免 localhost 被代理拦截
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: {
      dir: VIDEO_DIR,
      size: { width: 1440, height: 900 },
    },
  });

  const page = await context.newPage();

  try {
    // ── 登录 ──
    log('Step 1: 打开登录页');
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const emailInput = page.locator('#login-email');
    await emailInput.waitFor({ state: 'visible', timeout: 10000 });
    await emailInput.fill(EMAIL);
    await page.waitForTimeout(400);

    await page.locator('#login-password').fill(PASSWORD);
    await page.waitForTimeout(400);

    // 点击表单内的"登录"按钮（submit 按钮）
    await page.locator('button[type="submit"]:has-text("登录")').click();
    await page.waitForURL(`${BASE}/`, { timeout: 40000 });
    await page.waitForTimeout(1200);
    log(`✅ 登录成功 → ${page.url()}`);

    // ── 切换到「上传截图」Tab ──
    log('Step 2: 点击「上传截图」Tab');
    await page.locator('button:has-text("上传截图")').click();
    await page.waitForTimeout(800);

    // ── 上传 JD 截图 ──
    log('Step 3: 上传 JD 截图');
    // 先点"+"按钮触发文件选择框可见（输入框本身 hidden，直接 setInputFiles）
    const imageInput = page.locator('input[accept="image/*"]');
    await imageInput.setInputFiles(JOB_IMAGE);
    await page.waitForTimeout(1500);
    log('✅ JD 截图已上传');

    // ── 上传简历 PDF ──
    log('Step 4: 上传简历 PDF');
    const resumeInput = page.locator('input[accept=".pdf,.docx"]');
    await resumeInput.setInputFiles(RESUME_PDF);
    await page.waitForTimeout(1500);
    log('✅ 简历已上传');

    // ── 提交 ──
    log('Step 5: 点击「开始分析」');
    const submitBtn = page.locator('button:has-text("开始分析")');
    await submitBtn.waitFor({ state: 'visible', timeout: 10000 });
    await submitBtn.click();
    await page.waitForTimeout(2000);

    // ── 等待跳转到确认页 ──
    log('Step 6: 等待 JD 解析完成 → 进入确认页（最多 60 秒）');
    try {
      await page.waitForURL('**/report/**?step=confirm', { timeout: 60000 });
      log(`✅ 进入确认页 → ${page.url()}`);
    } catch {
      log(`⚠️ 当前 URL: ${page.url()}`);
    }
    await page.waitForTimeout(1500);

    // ── 等确认页职位数据加载完 ──
    log('Step 7: 等待确认页职位信息加载...');
    const confirmBtn = page.locator('button:has-text("确认，开始调研")');
    try {
      // 页面进入 confirm 后会先展示 loading，等按钮出现最多 25 秒
      await confirmBtn.waitFor({ state: 'visible', timeout: 25000 });
      const btnText = await confirmBtn.textContent();
      log(`✅ 确认按钮已就绪: "${btnText?.trim()}"`);
    } catch (e) {
      log(`❌ 确认按钮未出现，保存截图调试`);
      await page.screenshot({ path: '/tmp/playwright-debug-confirm.png' });
      log(`当前 URL: ${page.url()}`);
    }

    // 停顿让视频清楚呈现确认页数据
    await page.waitForTimeout(2000);

    log('Step 7b: 点击「确认，开始调研 →」');
    await confirmBtn.click();
    log('✅ 已点击确认按钮，等待跳转...');
    await page.waitForTimeout(2000);

    // ── 等待进入方向选择页 ──
    log('Step 8: 等待进入方向选择页');
    try {
      await page.waitForURL('**/report/**?step=directions', { timeout: 20000 });
      log(`✅ 进入方向选择页 → ${page.url()}`);
    } catch {
      log(`⚠️ 未跳转到 directions，当前 URL: ${page.url()}`);
      await page.screenshot({ path: '/tmp/playwright-debug-directions.png' });
    }
    await page.waitForTimeout(1500);

    // ── 开始调研 ──
    log('Step 9: 点击「开始调研」');
    const researchBtn = page.locator('button:has-text("开始调研")');
    await researchBtn.waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);
    await researchBtn.click();
    await page.waitForTimeout(2000);

    // ── 等待 HiTL 面板出现（调研完成后，AI 会暂停让用户确认草稿）──
    log('Step 10: 等待调研完成 & 「确认，保存报告 →」按钮出现（最多 10 分钟）...');
    const saveBtn = page.locator('button:has-text("确认，保存报告")');
    try {
      await saveBtn.waitFor({ state: 'visible', timeout: 600000 });
      log('✅ 报告草稿已就绪，HiTL 面板出现');
    } catch {
      log(`⚠️ 等待超时，当前 URL: ${page.url()}`);
      await page.screenshot({ path: '/tmp/playwright-debug-hitl.png' });
    }

    // 停顿让视频能看清草稿内容
    await page.waitForTimeout(3000);

    // 滚动到按钮（草稿预览可能把按钮推到屏幕外）
    await saveBtn.scrollIntoViewIfNeeded();
    await page.waitForTimeout(1000);

    log('Step 11: 点击「确认，保存报告 →」');
    await saveBtn.click();
    log('✅ 已点击保存报告');
    await page.waitForTimeout(2000);

    // ── 等待跳转到报告完成页 ──
    log('Step 12: 等待跳转到报告完成页...');
    try {
      await page.waitForURL('**/report/**?step=done', { timeout: 30000 });
      log('✅ 报告已完成！');
    } catch {
      log(`⚠️ 当前 URL: ${page.url()}`);
    }
    await page.waitForTimeout(4000);
    log('🎬 录制完成');

  } finally {
    await context.close();
    await browser.close();
  }

  // 输出视频路径
  const fs = await import('fs');
  const videos = fs.readdirSync(VIDEO_DIR).filter(f => f.endsWith('.webm'));
  if (videos.length > 0) {
    // 取最新的视频（按修改时间排序）
    const sorted = videos
      .map(f => ({ f, mtime: fs.statSync(path.join(VIDEO_DIR, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
    const videoPath = path.join(VIDEO_DIR, sorted[0].f);
    log(`🎬 视频文件: ${videoPath}`);
    return videoPath;
  }
  log('⚠️ 未找到视频文件');
  return null;
}

const video = await main();
if (video) {
  console.log(`\nFILE:${video}`);
}
