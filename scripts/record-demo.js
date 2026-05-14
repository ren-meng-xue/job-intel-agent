const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  // 确保录制目录存在
  const videoDir = '/tmp/playwright-videos';
  if (!fs.existsSync(videoDir)) fs.mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: videoDir, size: { width: 1280, height: 800 } }
  });
  const page = await context.newPage();

  const htmlPath = '/Users/xuebao/learn/AI项目/job-intel-agent/ui-prototype.html';
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle' });

  // 等待页面初始化完成
  await page.waitForTimeout(500);

  // ─── ① 登录 Tab（默认展示）─── 1.5s
  await page.waitForTimeout(1500);

  // ─── ① 切换到注册 Tab ─── 2s
  await page.evaluate(() => switchAuthTab('register'));
  await page.waitForTimeout(2000);

  // ─── ① 切回登录 Tab ─── 1s
  await page.evaluate(() => switchAuthTab('login'));
  await page.waitForTimeout(1000);

  // ─── ② 首页输入 ─── 1.5s
  await page.evaluate(() => showScreen('home'));
  await page.waitForTimeout(1500);

  // ─── ③ 解析中 ─── 2s
  await page.evaluate(() => showScreen('parsing'));
  await page.waitForTimeout(2000);

  // ─── ④ 确认JD弹窗 ─── 2s
  await page.evaluate(() => showScreen('confirm'));
  await page.waitForTimeout(2000);

  // ─── ⑤ 选择方向 ─── 2s
  await page.evaluate(() => showScreen('directions'));
  await page.waitForTimeout(2000);

  // ─── ⑥ 调研进行中 ─── 2s
  await page.evaluate(() => showScreen('researching'));
  await page.waitForTimeout(2000);

  // ─── ⑦ 报告完成 ─── 滚动展示 4s
  await page.evaluate(() => showScreen('report'));
  await page.waitForTimeout(500);
  // 平滑滚动到报告底部
  await page.evaluate(async () => {
    const delay = (ms) => new Promise(r => setTimeout(r, ms));
    const scrollStep = 40;
    const scrollInterval = 60;
    const maxScroll = document.body.scrollHeight - window.innerHeight;
    let current = 0;
    while (current < maxScroll) {
      current = Math.min(current + scrollStep, maxScroll);
      window.scrollTo(0, current);
      await delay(scrollInterval);
    }
  });
  await page.waitForTimeout(500);

  // 关闭浏览器，视频写入磁盘
  await browser.close();
  console.log('录制完成。视频目录:', videoDir);
})();
