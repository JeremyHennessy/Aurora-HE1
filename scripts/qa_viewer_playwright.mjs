#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const pageUrl = process.env.PAGE_URL || 'https://jeremyhennessy.github.io/Aurora-HE1/';
const sandboxUrl = `${pageUrl.replace(/\/$/, '')}/sandbox.html`;
const outputDir = process.env.QA_OUTPUT_DIR || 'qa-artifacts/viewer';
fs.mkdirSync(outputDir, { recursive: true });

const consoleErrors = [];
const pageErrors = [];
const requestFailures = [];

function attachDiagnostics(page, label) {
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (text.includes('favicon.ico')) return;
    consoleErrors.push(`${label}: ${text}`);
  });
  page.on('pageerror', (error) => pageErrors.push(`${label}: ${error.message}`));
  page.on('requestfailed', (request) => {
    requestFailures.push(`${label}: ${request.method()} ${request.url()} :: ${request.failure()?.errorText || 'unknown failure'}`);
  });
}

async function assertViewerLoaded(page, label) {
  const response = await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (!response || !response.ok()) {
    throw new Error(`${label}: viewer navigation failed with HTTP ${response?.status() ?? 'no response'}`);
  }
  await page.waitForFunction(() => document.querySelector('#status')?.textContent?.includes('verified'), null, { timeout: 30_000 });
  await page.waitForSelector('#scene canvas', { state: 'visible', timeout: 30_000 });
  await page.waitForTimeout(1500);

  const state = await page.evaluate(() => {
    const canvas = document.querySelector('#scene canvas');
    const activeTab = document.querySelector('.tab.active')?.dataset?.tab;
    return {
      title: document.title,
      status: document.querySelector('#status')?.textContent || '',
      activeTab,
      canvasWidth: canvas?.width || 0,
      canvasHeight: canvas?.height || 0,
      tabs: [...document.querySelectorAll('.tab')].map((el) => el.dataset.tab),
    };
  });

  if (state.title !== 'Aurora HE-1 Engineering Viewer') throw new Error(`${label}: unexpected title ${state.title}`);
  if (!state.status.includes('Snapshot 8de7fbe') || !state.status.includes('verified')) throw new Error(`${label}: unexpected snapshot status ${state.status}`);
  if (state.canvasWidth < 300 || state.canvasHeight < 200) throw new Error(`${label}: Three.js canvas did not size correctly (${state.canvasWidth}x${state.canvasHeight})`);
  for (const tab of ['overview', 'prop', 'aero', 'cg', 'sources']) {
    if (!state.tabs.includes(tab)) throw new Error(`${label}: missing ${tab} tab`);
  }
}

async function assertSandboxLoaded(page, label) {
  const response = await page.goto(sandboxUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (!response || !response.ok()) {
    throw new Error(`${label}: sandbox navigation failed with HTTP ${response?.status() ?? 'no response'}`);
  }
  await page.waitForFunction(() => document.querySelectorAll('#metrics .metric').length === 8, null, { timeout: 30_000 });
  await page.waitForFunction(() => document.querySelectorAll('#propConfig option').length === 3, null, { timeout: 30_000 });
  const state = await page.evaluate(() => ({
    title: document.title,
    warning: document.body.innerText.includes('UNVERIFIED SCENARIO'),
    metrics: document.querySelector('#metrics')?.innerText || '',
    speed: document.querySelector('#speedV')?.textContent || '',
    prop: document.querySelector('#propConfig')?.value || '',
  }));
  if (state.title !== 'Aurora HE-1 Scenario Sandbox') throw new Error(`${label}: unexpected sandbox title ${state.title}`);
  if (!state.warning) throw new Error(`${label}: sandbox lacks UNVERIFIED SCENARIO warning`);
  if (!state.metrics.includes('110.0 kg')) throw new Error(`${label}: sandbox default gross mass does not reproduce 110 kg reference: ${state.metrics}`);
  if (!state.metrics.includes('333 W')) throw new Error(`${label}: sandbox default shaft requirement does not reproduce Phase 2 reference: ${state.metrics}`);
  if (!state.speed.includes('9.5 m/s')) throw new Error(`${label}: sandbox default speed mismatch: ${state.speed}`);
  if (state.prop !== 'phase2_reference') throw new Error(`${label}: sandbox default prop reference mismatch: ${state.prop}`);
}

async function captureTabs(page, prefix, tabs) {
  for (const tab of tabs) {
    await page.locator(`.tab[data-tab="${tab}"]`).click();
    await page.waitForSelector(`#${tab}.section.active`, { state: 'visible' });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(outputDir, `${prefix}-${tab}.png`), fullPage: true });
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const desktopPage = await desktop.newPage();
  attachDiagnostics(desktopPage, 'desktop');
  await assertViewerLoaded(desktopPage, 'desktop');
  await captureTabs(desktopPage, 'desktop', ['overview', 'prop', 'aero', 'cg', 'sources']);

  await desktopPage.locator('.tab[data-tab="prop"]').click();
  await desktopPage.locator('#speed').evaluate((el) => { el.value = '6'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await desktopPage.waitForTimeout(250);
  const highSpeedStats = await desktopPage.locator('#speedStats').innerText();
  if (!highSpeedStats.includes('11.0 m/s') || !highSpeedStats.includes('170')) {
    throw new Error(`desktop: speed slider did not expose verified 11 m/s point: ${highSpeedStats}`);
  }
  await desktopPage.screenshot({ path: path.join(outputDir, 'desktop-prop-11ms.png'), fullPage: true });

  await assertSandboxLoaded(desktopPage, 'desktop-sandbox');
  await desktopPage.screenshot({ path: path.join(outputDir, 'desktop-sandbox-reference.png'), fullPage: true });
  await desktopPage.locator('#lightPilot').click();
  await desktopPage.waitForTimeout(250);
  const lightMetrics = await desktopPage.locator('#metrics').innerText();
  if (!lightMetrics.includes('97.5 kg')) throw new Error(`desktop-sandbox: light-pilot scenario did not recompute gross mass: ${lightMetrics}`);
  await desktopPage.screenshot({ path: path.join(outputDir, 'desktop-sandbox-light-pilot.png'), fullPage: true });
  await desktopPage.locator('#reset').click();
  await desktopPage.waitForTimeout(150);
  const resetMetrics = await desktopPage.locator('#metrics').innerText();
  if (!resetMetrics.includes('110.0 kg')) throw new Error(`desktop-sandbox: reset did not restore Phase 2 reference: ${resetMetrics}`);
  await desktop.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const mobilePage = await mobile.newPage();
  attachDiagnostics(mobilePage, 'mobile');
  await assertViewerLoaded(mobilePage, 'mobile');
  await captureTabs(mobilePage, 'mobile', ['overview', 'prop']);
  await assertSandboxLoaded(mobilePage, 'mobile-sandbox');
  await mobilePage.screenshot({ path: path.join(outputDir, 'mobile-sandbox-reference.png'), fullPage: true });
  await mobile.close();
} finally {
  await browser.close();
}

const diagnostic = {
  pageUrl,
  sandboxUrl,
  consoleErrors,
  pageErrors,
  requestFailures,
  screenshots: fs.readdirSync(outputDir).filter((name) => name.endsWith('.png')).sort(),
};
fs.writeFileSync(path.join(outputDir, 'qa-summary.json'), `${JSON.stringify(diagnostic, null, 2)}\n`);

if (consoleErrors.length || pageErrors.length || requestFailures.length) {
  console.error(JSON.stringify(diagnostic, null, 2));
  process.exit(1);
}

console.log('HOSTED BROWSER QA PASSED');
console.log(`screenshots: ${diagnostic.screenshots.length}`);
console.log(`viewer: ${pageUrl}`);
console.log(`sandbox: ${sandboxUrl}`);
