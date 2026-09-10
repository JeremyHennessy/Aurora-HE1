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
  page.on('requestfailed', (request) => requestFailures.push(`${label}: ${request.method()} ${request.url()} :: ${request.failure()?.errorText || 'unknown failure'}`));
}

async function assertViewerLoaded(page, label) {
  const response = await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (!response || !response.ok()) throw new Error(`${label}: viewer navigation failed with HTTP ${response?.status() ?? 'no response'}`);
  await page.waitForFunction(() => document.querySelector('#status')?.textContent?.includes('Phase 3 geometry loaded'), null, { timeout: 30_000 });
  await page.waitForSelector('#scene canvas', { state: 'visible', timeout: 30_000 });
  await page.waitForFunction(() => document.querySelectorAll('#tailSelect option').length === 5, null, { timeout: 30_000 });
  await page.waitForTimeout(1200);

  const state = await page.evaluate(() => {
    const canvas = document.querySelector('#scene canvas');
    return {
      title: document.title,
      status: document.querySelector('#status')?.textContent || '',
      activeTab: document.querySelector('.tab.active')?.dataset?.tab || '',
      canvasWidth: canvas?.width || 0,
      canvasHeight: canvas?.height || 0,
      tabs: [...document.querySelectorAll('.tab')].map((el) => el.dataset.tab),
      tailOptions: [...document.querySelectorAll('#tailSelect option')].map((el) => el.value),
      modelMetrics: document.querySelector('#modelMetrics')?.innerText || '',
      warning: document.body.innerText.includes('not for construction or flight clearance'),
    };
  });

  if (state.title !== 'Aurora HE-1 Engineering Viewer') throw new Error(`${label}: unexpected title ${state.title}`);
  if (!state.status.includes('Snapshot 8de7fbe') || !state.status.includes('Phase 3 geometry loaded')) throw new Error(`${label}: unexpected viewer status ${state.status}`);
  if (state.activeTab !== 'model') throw new Error(`${label}: model tab is not initial active tab`);
  if (state.canvasWidth < 300 || state.canvasHeight < 200) throw new Error(`${label}: Three.js canvas did not size correctly (${state.canvasWidth}x${state.canvasHeight})`);
  for (const tab of ['model', 'stability', 'prop', 'aero', 'cg', 'sources']) {
    if (!state.tabs.includes(tab)) throw new Error(`${label}: missing ${tab} tab`);
  }
  for (const tail of ['HT35T70', 'HT45T65', 'HT55T65', 'HT65T55', 'HT55T100']) {
    if (!state.tailOptions.includes(tail)) throw new Error(`${label}: missing Phase 3B tail ${tail}`);
  }
  if (!state.modelMetrics.includes('23.0 m') || !state.modelMetrics.includes('4 source profiles')) throw new Error(`${label}: Phase 3 model metrics are incomplete: ${state.modelMetrics}`);
  if (!state.warning) throw new Error(`${label}: construction/flight-clearance warning missing`);
}

async function assertSandboxLoaded(page, label) {
  const response = await page.goto(sandboxUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (!response || !response.ok()) throw new Error(`${label}: sandbox navigation failed with HTTP ${response?.status() ?? 'no response'}`);
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
  if (!state.metrics.includes('110.0 kg')) throw new Error(`${label}: sandbox default gross mass mismatch: ${state.metrics}`);
  if (!state.metrics.includes('333 W')) throw new Error(`${label}: sandbox default shaft requirement mismatch: ${state.metrics}`);
  if (!state.speed.includes('9.5 m/s')) throw new Error(`${label}: sandbox default speed mismatch: ${state.speed}`);
  if (state.prop !== 'phase2_reference') throw new Error(`${label}: sandbox default prop reference mismatch: ${state.prop}`);
}

async function captureTab(page, prefix, tab) {
  await page.locator(`.tab[data-tab="${tab}"]`).click();
  await page.waitForSelector(`#${tab}.section.active`, { state: 'visible' });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outputDir, `${prefix}-${tab}.png`), fullPage: true });
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await desktop.newPage();
  attachDiagnostics(page, 'desktop');
  await assertViewerLoaded(page, 'desktop');
  await page.screenshot({ path: path.join(outputDir, 'desktop-model-ht35.png'), fullPage: true });

  await page.selectOption('#tailSelect', 'HT65T55');
  await page.waitForTimeout(350);
  const tailState = await page.evaluate(() => ({ selected: document.querySelector('#tailSelect')?.value, details: document.querySelector('#tailDetails')?.innerText || '', metrics: document.querySelector('#modelMetrics')?.innerText || '' }));
  if (tailState.selected !== 'HT65T55' || !tailState.details.includes('47.59%') || !tailState.metrics.includes('HT65T55')) {
    throw new Error(`desktop: tail switch did not propagate through model/details: ${JSON.stringify(tailState)}`);
  }
  await page.screenshot({ path: path.join(outputDir, 'desktop-model-ht65.png'), fullPage: true });

  await page.locator('#layerMass').check();
  await page.locator('#layerPilot').check();
  await page.locator('#layerClearance').check();
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(outputDir, 'desktop-model-diagnostics.png'), fullPage: true });

  await captureTab(page, 'desktop', 'stability');
  const stability = await page.locator('#stabilityMetrics').innerText();
  const rows = await page.locator('#tailTable tbody tr').count();
  if (!stability.includes('38.2%') || !stability.includes('47.6%') || !stability.includes('0') || rows !== 5) {
    throw new Error(`desktop: Phase 3B stability evidence incomplete: ${stability}; rows=${rows}`);
  }
  await captureTab(page, 'desktop', 'prop');
  if (await page.locator('#propTable tbody tr').count() !== 7) throw new Error('desktop: Phase 2B operating envelope no longer has seven rows');
  await captureTab(page, 'desktop', 'aero');
  await captureTab(page, 'desktop', 'cg');
  await captureTab(page, 'desktop', 'sources');

  await assertSandboxLoaded(page, 'desktop-sandbox');
  await page.screenshot({ path: path.join(outputDir, 'desktop-sandbox-reference.png'), fullPage: true });
  await page.locator('#lightPilot').click();
  await page.waitForTimeout(250);
  const lightMetrics = await page.locator('#metrics').innerText();
  if (!lightMetrics.includes('97.5 kg')) throw new Error(`desktop-sandbox: light-pilot scenario did not recompute gross mass: ${lightMetrics}`);
  await page.locator('#reset').click();
  await page.waitForTimeout(150);
  const resetMetrics = await page.locator('#metrics').innerText();
  if (!resetMetrics.includes('110.0 kg')) throw new Error(`desktop-sandbox: reset did not restore reference: ${resetMetrics}`);
  await desktop.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const mobilePage = await mobile.newPage();
  attachDiagnostics(mobilePage, 'mobile');
  await assertViewerLoaded(mobilePage, 'mobile');
  await mobilePage.screenshot({ path: path.join(outputDir, 'mobile-model.png'), fullPage: true });
  await captureTab(mobilePage, 'mobile', 'stability');
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
