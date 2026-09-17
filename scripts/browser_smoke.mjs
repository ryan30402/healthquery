import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseURL = process.env.HEALTHQUERY_BASE_URL || "http://127.0.0.1:8000";
const output = path.resolve(process.env.HEALTHQUERY_BROWSER_OUTPUT || "artifacts/browser");
const report = { base_url: baseURL, checks: [], screenshots: [], passed: false };
const launch = { headless: true };
if (process.env.HEALTHQUERY_CHROMIUM_PATH) launch.executablePath = process.env.HEALTHQUERY_CHROMIUM_PATH;
if (process.env.HEALTHQUERY_CHROMIUM_ARGS) launch.args = JSON.parse(process.env.HEALTHQUERY_CHROMIUM_ARGS);
await mkdir(output, { recursive: true });
let browser;
let page;

async function waitForReady(context) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const timeout = Math.max(1, Math.min(1000, deadline - Date.now()));
      const response = await context.request.get(new URL("/ready", baseURL).href, { timeout });
      if (response.ok() && (await response.json()).status === "ready") return;
    } catch {
      // A container may still be starting or loading its models.
    }
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, Math.min(250, deadline - Date.now()))));
  }
  throw new Error("HealthQuery did not become ready within 30 seconds. Check the server logs.");
}

async function statusMatches(pattern) {
  await page.waitForFunction((source) => new RegExp(source).test(document.querySelector("#status").textContent), pattern.source);
}

async function screenshot(name) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  await page.screenshot({ path: path.join(output, name), fullPage: !["desktop-welcome.png", "desktop-archive.png"].includes(name) });
  report.screenshots.push(name);
}

async function check(name, operation) {
  await operation();
  report.checks.push(name);
  console.log(`PASS ${name}`);
}

try {
  browser = await chromium.launch(launch);
  report.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "en-US" });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
      writeText: async () => { throw new DOMException("Permission denied", "NotAllowedError"); },
    } });
  });
  page = await context.newPage();
  page.setDefaultTimeout(10000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const readinessStarted = Date.now();
  await waitForReady(context);
  report.readiness_wait_ms = Date.now() - readinessStarted;
  await page.goto(baseURL, { waitUntil: "networkidle" });

  await check("Collection statistics come from the running API", async () => {
    const response = await context.request.get(`${baseURL}/api/info`);
    assert.equal(response.status(), 200);
    const info = await response.json();
    report.dataset_revision = info.dataset_revision;
    report.indexed_records = info.indexed_records;
    for (const [key, selector] of Object.entries({ indexed_records: "#record-count", source_urls: "#source-count", question_types: "#type-count" })) {
      assert.equal(await page.locator(selector).textContent(), info[key].toLocaleString("en-US"));
    }
  });
  await check("English page, input labels, live status, and keyboard skip link", async () => {
    assert.equal(await page.locator("html").getAttribute("lang"), "en");
    assert.equal(await page.locator("h1").count(), 1);
    assert.equal(await page.getByLabel("Your medical information question", { exact: true }).count(), 1);
    assert.equal(await page.getByLabel("Sources", { exact: true }).count(), 1);
    assert.equal(await page.locator("#status").getAttribute("aria-live"), "polite");
    await page.keyboard.press("Tab");
    assert.equal(await page.locator(":focus").textContent(), "Skip to workspace");
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(":focus").getAttribute("id"), "workspace");
  });
  await screenshot("desktop-welcome.png");
  await check("Whitespace-only questions are rejected before search", async () => {
    await page.locator("#question").fill("   ");
    await page.locator("#submit-button").click();
    await statusMatches(/Please enter/);
    assert.equal(await page.locator("#results .source-card").count(), 0);
    assert.equal(await page.locator("#submit-button").isEnabled(), true);
  });

  let payload;
  await check("Real API query renders source cards and working archived text", async () => {
    await page.locator("#question").fill("What causes asthma?");
    const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/query") && response.request().method() === "POST");
    await page.locator("#submit-button").click();
    const response = await responsePromise;
    assert.equal(response.status(), 200);
    payload = await response.json();
    await page.locator(".source-card").first().waitFor();
    assert.ok(payload.results.length > 0 && payload.results.length <= 3);
    assert.equal(await page.locator(".source-card").count(), payload.results.length);
    assert.equal(await page.locator(".source-card h3").first().textContent(), payload.results[0].question);
    const detailPromise = page.waitForResponse((item) => new URL(item.url()).pathname.startsWith("/api/sources/"));
    await page.locator(".archive-button").first().click();
    const detailResponse = await detailPromise;
    assert.equal(detailResponse.status(), 200);
    const detail = await detailResponse.json();
    await page.waitForFunction(() => document.querySelector("#dialog-content").getAttribute("aria-busy") === "false");
    assert.equal(await page.locator("#dialog-content").textContent(), detail.answer);
    assert.equal(await page.locator("#dialog-title").textContent(), detail.question);
    assert.equal(await page.locator("#source-dialog").isVisible(), true);
    await screenshot("desktop-archive.png");
    await page.getByRole("button", { name: "Close archived source" }).click();
    assert.equal(await page.locator("#source-dialog").isVisible(), false);
    assert.equal(await page.locator(".archive-button").first().evaluate((node) => node === document.activeElement), true);
  });
  await screenshot("desktop-results.png");
  await check("Mobile layout has no horizontal overflow and controls remain usable", async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.locator("#question").scrollIntoViewIfNeeded();
    assert.equal(await page.locator("#submit-button").isVisible(), true);
    await screenshot("mobile-results.png");
  });
  await check("Denied clipboard access provides a selectable citation", async () => {
    await page.locator(".copy-button").first().click();
    const feedback = page.locator(".citation-status").first();
    await feedback.waitFor();
    assert.match(await feedback.textContent(), /Select and copy this citation:/);
    assert.ok((await feedback.textContent()).includes(payload.results[0].source_url));
  });
  await check("Recent questions can be reused and cleared", async () => {
    assert.equal(await page.locator("#recent-queries button").count(), 1);
    await page.locator("#question").fill("changed");
    await page.locator("#recent-queries button").first().click();
    assert.equal(await page.locator("#question").inputValue(), "What causes asthma?");
    await page.locator("#clear-history").click();
    assert.equal(await page.locator("#recent-queries button").count(), 0);
  });
  await check("Empty results have an explicit recovery message", async () => {
    await page.route("**/api/query", (route) => route.fulfill({ json: { ...payload, results: [] } }));
    await page.locator("#submit-button").click();
    await page.locator("#empty-results").waitFor();
    assert.equal(await page.locator(".source-card").count(), 0);
    await page.unroute("**/api/query");
  });
  await check("Server text is rendered as text instead of executable markup", async () => {
    const attack = '<img src=x onerror="window.healthqueryInjected=true">';
    await page.route("**/api/query", (route) => route.fulfill({ json: { ...payload, results: [{ ...payload.results[0], question: attack, excerpt: attack }] } }));
    await page.locator("#submit-button").click();
    await page.locator(".source-card").first().waitFor();
    assert.equal(await page.locator(".source-card h3").textContent(), attack);
    assert.equal(await page.locator(".source-card img").count(), 0);
    assert.equal(await page.evaluate(() => window.healthqueryInjected), undefined);
    await page.unroute("**/api/query");
  });
  await check("Rate-limit feedback explains when to retry", async () => {
    await page.route("**/api/query", (route) => route.fulfill({ status: 429, headers: { "Retry-After": "9" }, json: { detail: "Too many requests" } }));
    await page.locator("#submit-button").click();
    await statusMatches(/Wait 9 seconds/);
    assert.equal(await page.locator("#submit-button").isEnabled(), true);
    await page.unroute("**/api/query");
  });
  await check("An in-flight request can be cancelled", async () => {
    await page.route("**/api/query", () => {});
    await page.locator("#submit-button").click();
    await page.locator("#cancel-button").click();
    await statusMatches(/Search cancelled/);
    assert.equal(await page.locator("#submit-button").isEnabled(), true);
    await page.unroute("**/api/query");
  });
  await check("A stalled request times out and restores the form", async () => {
    await page.clock.install();
    await page.route("**/api/query", () => {});
    await page.locator("#submit-button").click();
    await page.clock.fastForward(16000);
    await statusMatches(/longer than 15 seconds/);
    assert.equal(await page.locator("#submit-button").isEnabled(), true);
    await page.unroute("**/api/query");
  });
  assert.deepEqual(pageErrors, []);
  report.passed = true;
} catch (error) {
  report.error = error.message;
  if (page) await screenshot("failure.png").catch(() => {});
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  await writeFile(path.join(output, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
  console.log(`${report.passed ? "Browser smoke checks passed" : "Browser smoke checks failed"}; report: ${path.join(output, "report.json")}`);
  if (report.error) console.error(report.error);
}
