const fs = require("fs");
const path = require("path");
const { chromium } = require("/Users/xuebao/.agents/skills/gstack/node_modules/playwright");

const ARTIFACT_DIR = path.join(__dirname, "artifacts", "full-flow");
const VIDEO_DIR = path.join(ARTIFACT_DIR, "videos");
const SCREENSHOT_DIR = path.join(ARTIFACT_DIR, "screenshots");
const REPORT_PATH = path.join(ARTIFACT_DIR, "report.json");

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3001";
const API_URL = process.env.API_URL || "http://localhost:8001";
const TEST_EMAIL = "test_final@example.com";
const TEST_PASSWORD = "password123";
const JD_URL = "https://www.zhipin.com/job_detail/c6643409d590546d0nZ439y_EFtZ.html?securityId=CR6vV4PAkIDzV-W1DbYX5w9StZcNiPaMN9IC-vMZlQWF7b1DdDFO_shC644MkBbgkTAKd_sQtdZXKk23TffMtpx9OcQoA4TjIf8wpd6BrmiRmnNcHyl2OnOhnnXBPWlT7W0iu5okLQQSU5A0QhYMNJMnmY9bANiZS2xnoA48BnARMu1r8B6ivf0srxHyhVffBwFUYRZZ4xlqJ6f9P6x9yc2bDqTo5OquTAzYrX6acnQ_QlGEprlNzxWcR9Qw2jL0En618xIamokOPcKdnvPy5IycJQ3f4R_S_q-X_jfTeM4VTajoDG0K6Af7dxu1E8Kkhtpk1NBGqZF7r4gtMO50AzOTozjCFFFeadjKf6BZGy_Cyh5_NBJ7ijWK1aD9uRPyRSiDW-1tsalg53fQd2TLJ7JuBeY~&ka=company_more_job_c6643409d590546d0nZ439y_EFtZ";
const TEST_RESUME_PATH = "/Users/xuebao/learn/面试/任孟雪WEB前端工程师.pdf";

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
    steps: [],
    errors: [],
  };

  let browser;
  let context;
  let page;

  try {
    browser = await chromium.launch({ headless: false });
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 800 } },
    });
    page = await context.newPage();

    // Log console errors
    page.on("console", (msg) => {
      console.log(`[Browser] ${msg.type()}: ${msg.text()}`);
      if (msg.type() === "error") report.errors.push({ source: "console", text: msg.text() });
    });
    page.on("pageerror", (err) => report.errors.push({ source: "pageerror", text: err.message }));

    // 1. Check Backend Health
    console.log("Checking backend health...");
    const health = await page.request.get(`${API_URL}/health`);
    if (!health.ok()) throw new Error(`Backend health check failed: ${health.status()}`);

    // 2. Auth Page
    console.log("Opening auth page...");
    await page.goto(`${FRONTEND_URL}/auth`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    
    // Hide the sidebar to prevent any blocking
    await page.evaluate(() => {
      const aside = document.querySelector('aside');
      if (aside) aside.style.display = 'none';
      const container = document.querySelector('div.grid');
      if (container) container.style.gridTemplateColumns = '1fr';
    });
    
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "01-auth.png") });

    // 3. Login
    console.log(`Logging in as ${TEST_EMAIL}...`);
    await page.waitForSelector('input[id="login-email"]', { state: 'visible', timeout: 30000 });
    
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "01-login-filled.png") });
    
    // Use Enter key to submit, or click the correct submit button
    console.log("Submitting login form...");
    // Find the button inside the form specifically
    const submitButton = page.locator('form button[type="submit"]');
    await submitButton.click({ force: true });

    try {
      await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 30000 });
      console.log("Logged in successfully.");
    } catch (e) {
      console.log("Click did not work, trying Enter key...");
      await page.keyboard.press('Enter');
      await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 30000 });
    }
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "02-home.png") });

    // 4. Submit JD
    console.log("Submitting JD...");
    await page.fill("input[placeholder*='粘贴 JD 链接']", JD_URL);
    await page.waitForTimeout(500);
    if (fs.existsSync(TEST_RESUME_PATH)) {
      await page.setInputFiles("input[type='file']", TEST_RESUME_PATH);
    }
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "02-jd-filled.png") });
    await page.click("button:has-text('开始分析')");
    await page.waitForURL(/\/report\/.+step=parsing/, { timeout: 30000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "03-parsing.png") });

    // 5. Wait for Confirm
    console.log("Waiting for JD parsing to complete...");
    try {
      await page.waitForURL(/step=confirm/, { timeout: 180000 });
    } catch (e) {
      console.log("URL did not change to confirm, refreshing...");
      await page.reload();
      await page.waitForURL(/step=confirm/, { timeout: 30000 });
    }
    
    console.log("Ensuring confirm card is visible...");
    await page.waitForSelector("text=职位名称", { state: 'visible', timeout: 60000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "04-confirm.png") });
    await page.click("button:has-text('确认，开始调研')");

    // 6. Select Directions
    console.log("Selecting directions...");
    try {
      await page.waitForURL(/step=directions/, { timeout: 60000 });
    } catch (e) {
      console.log("URL did not change to directions, refreshing...");
      await page.reload();
      await page.waitForURL(/step=directions/, { timeout: 30000 });
    }
    await page.waitForSelector("text=选择调研方向", { state: 'visible', timeout: 30000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "05-directions.png") });
    await page.click("button:has-text('开始调研')");

    // 7. Researching
    console.log("Researching...");
    try {
      await page.waitForURL(/step=researching/, { timeout: 60000 });
    } catch (e) {
      console.log("URL did not change to researching, refreshing...");
      await page.reload();
      await page.waitForURL(/step=researching/, { timeout: 30000 });
    }
    await page.waitForSelector("text=调研 & 报告生成中", { state: 'visible', timeout: 30000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "06-researching.png") });
    
    // Wait for final report
    console.log("Waiting for research to complete (this may take a few minutes)...");
    try {
      await page.waitForURL(/step=done/, { timeout: 600000 }); // 10 minutes
    } catch (e) {
      console.log("Report not done yet, refreshing...");
      await page.reload();
      await page.waitForURL(/step=done/, { timeout: 600000 });
    }
    await page.waitForTimeout(5000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "07-report.png") });

    // 8. Scroll through report
    console.log("Scrolling through report...");
    await page.evaluate(async () => {
      for (let i = 0; i < 8; i++) {
        window.scrollBy(0, 800);
        await new Promise(r => setTimeout(r, 600));
      }
    });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "08-report-scrolled.png"), fullPage: true });

    report.status = "passed";
    console.log("Full flow test passed!");

  } catch (error) {
    console.error("Test failed:", error);
    report.status = "failed";
    report.errors.push({ source: "runner", text: error.message });
    if (page) {
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, "error.png"), fullPage: true });
    }
  } finally {
    if (context) await context.close();
    if (browser) await browser.close();
    report.finishedAt = new Date().toISOString();
    writeReport(report);
    console.log(`Artifacts saved in ${ARTIFACT_DIR}`);
  }
}

main();
