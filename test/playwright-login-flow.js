const fs = require("fs");
const path = require("path");
const { chromium } = require("/Users/xuebao/.agents/skills/gstack/node_modules/playwright");

const ROOT = path.resolve(__dirname, "..");
const ARTIFACT_DIR = path.join(__dirname, "artifacts", "login-flow");
const VIDEO_DIR = path.join(ARTIFACT_DIR, "videos");
const SCREENSHOT_DIR = path.join(ARTIFACT_DIR, "screenshots");
const REPORT_PATH = path.join(ARTIFACT_DIR, "report.json");

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3001";
const API_URL = process.env.API_URL || "http://localhost:8001";
const TEST_EMAIL = process.env.TEST_EMAIL;
const TEST_PASSWORD = process.env.TEST_PASSWORD;
const JD_URL =
  process.env.TEST_JD_URL ||
  "https://resources.workable.com/software-engineer-job-description";
const TEST_RESUME_PATH = process.env.TEST_RESUME_PATH;

function ensureDirs() {
  fs.mkdirSync(VIDEO_DIR, { recursive: true });
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

function writeReport(report) {
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
}

async function main() {
  ensureDirs();

  const report = {
    startedAt: new Date().toISOString(),
    status: "running",
    root: ROOT,
    frontendUrl: FRONTEND_URL,
    apiUrl: API_URL,
    steps: [],
    errors: [],
    artifacts: {
      report: REPORT_PATH,
      videosDir: VIDEO_DIR,
      screenshotsDir: SCREENSHOT_DIR,
    },
  };

  let browser;
  let context;
  let page;

  try {
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 800 } },
    });
    page = await context.newPage();

    page.on("console", (message) => {
      if (message.type() === "error") {
        report.errors.push({
          source: "browser-console",
          text: message.text(),
        });
      }
    });

    page.on("pageerror", (error) => {
      report.errors.push({
        source: "pageerror",
        text: error.message,
      });
    });

    page.on("requestfailed", (request) => {
      report.errors.push({
        source: "requestfailed",
        url: request.url(),
        failure: request.failure()?.errorText,
      });
    });

    report.steps.push({ name: "backend health", status: "running" });
    const healthResponse = await page.request.get(`${API_URL}/health`);
    report.steps[report.steps.length - 1] = {
      name: "backend health",
      status: healthResponse.ok() ? "passed" : "failed",
      httpStatus: healthResponse.status(),
      body: await healthResponse.text(),
    };
    if (!healthResponse.ok()) {
      throw new Error(`后端健康检查失败：HTTP ${healthResponse.status()}`);
    }

    report.steps.push({ name: "open auth page", status: "running" });
    const authResponse = await page.goto(`${FRONTEND_URL}/auth`, {
      waitUntil: "domcontentloaded",
      timeout: 30_000,
    });
    await page.waitForTimeout(1200);
    const authScreenshot = path.join(SCREENSHOT_DIR, "auth-page.png");
    await page.screenshot({ path: authScreenshot, fullPage: true });
    const authStatus = authResponse ? authResponse.status() : null;
    report.steps[report.steps.length - 1] = {
      name: "open auth page",
      status: authStatus && authStatus < 400 ? "passed" : "failed",
      httpStatus: authStatus,
      url: page.url(),
      screenshot: authScreenshot,
    };
    if (!authStatus || authStatus >= 400) {
      throw new Error(`登录页不可用：HTTP ${authStatus}`);
    }

    if (!TEST_EMAIL || !TEST_PASSWORD) {
      throw new Error("缺少 TEST_EMAIL 或 TEST_PASSWORD 环境变量");
    }

    report.steps.push({ name: "login", status: "running" });
    const loginForm = page.locator("form").filter({
      has: page.locator("#login-email"),
    });
    await loginForm.getByLabel("邮箱").fill(TEST_EMAIL);
    await loginForm.getByLabel("密码").fill(TEST_PASSWORD);
    await loginForm.getByRole("button", { name: "登录" }).click();
    await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 30_000 });
    report.steps[report.steps.length - 1] = {
      name: "login",
      status: "passed",
      url: page.url(),
    };

    report.steps.push({ name: "submit jd", status: "running" });
    const submitStepIndex = report.steps.length - 1;
    await page.getByPlaceholder("粘贴 JD 链接（Boss / 拉勾 / 猎聘）").fill(JD_URL);
    if (TEST_RESUME_PATH) {
      await page.locator('input[type="file"]').setInputFiles(TEST_RESUME_PATH);
      report.steps.push({
        name: "select resume",
        status: "passed",
        path: TEST_RESUME_PATH,
      });
    }
    await page.getByRole("button", { name: "开始分析" }).click();
    await page.waitForURL(/\/report\/.+step=parsing/, { timeout: 30_000 });
    const parsingUrl = page.url();
    report.steps[submitStepIndex] = {
      name: "submit jd",
      status: "passed",
      url: parsingUrl,
    };

    report.steps.push({ name: "parse jd", status: "running" });
    await Promise.race([
      page.waitForURL(/step=confirm/, { timeout: 180_000 }),
      page
        .locator("text=JD 解析失败")
        .waitFor({ state: "visible", timeout: 180_000 })
        .then(() => {
          throw new Error("JD 解析失败");
        }),
    ]);
    const confirmScreenshot = path.join(SCREENSHOT_DIR, "confirm-step.png");
    await page.screenshot({ path: confirmScreenshot, fullPage: true });
    report.steps[report.steps.length - 1] = {
      name: "parse jd",
      status: "passed",
      url: page.url(),
      screenshot: confirmScreenshot,
    };

    report.status = "passed";
  } catch (error) {
    report.status = "failed";
    report.errors.push({
      source: "test-runner",
      text: error instanceof Error ? error.message : String(error),
    });
    process.exitCode = 1;
  } finally {
    report.finishedAt = new Date().toISOString();
    if (context) await context.close();
    if (browser) await browser.close();
    writeReport(report);
    console.log(`报告: ${REPORT_PATH}`);
    console.log(`视频目录: ${VIDEO_DIR}`);
  }
}

main();
