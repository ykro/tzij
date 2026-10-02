// Render an SVG diagram to PNG at 2.4x (run from web/, which has Playwright):
//   cd web && node tests/render-diagram.mjs bitacora
import { chromium } from "playwright";
const name = process.argv[2] ?? "bitacora";
const dir = new URL("../../docs/diagrams/", import.meta.url).pathname;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 520 }, deviceScaleFactor: 2.4 });
await page.goto(`file://${dir}${name}.svg`);
await page.waitForTimeout(1200);
await page.locator("svg").first().screenshot({ path: `${dir}${name}.png` });
await browser.close();
