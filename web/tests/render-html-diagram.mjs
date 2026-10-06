// Export a diagram-design HTML file (docs/diagrams/<name>.html) to <name>.svg and <name>.png (2.4x), headless:
//   cd web && node tests/render-html-diagram.mjs architecture
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
const name = process.argv[2] ?? "architecture";
const dir = new URL("../../docs/diagrams/", import.meta.url).pathname;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2.4 });
await page.goto(`file://${dir}${name}.html`);
await page.waitForTimeout(1500); // web fonts
const svg = page.locator("svg").first();
await svg.screenshot({ path: `${dir}${name}.png` });
await writeFile(`${dir}${name}.svg`, await svg.evaluate((el) => {
  const clone = el.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  return clone.outerHTML;
}));
await browser.close();
