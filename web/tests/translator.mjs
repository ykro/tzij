// Screenshots of the translator page (/traductor/) for docs/DEMO.md, and a check that it works:
// click an example, wait for David, type a phrase, translate. Needs `make up` with the stage David.
//   cd web && node tests/translator.mjs
// Output: docs/demo/traductor-*.png. Exit code 1 if the page doesn't translate.
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8787";
const OUT = new URL("../../docs/demo/", import.meta.url).pathname;

async function translated(page) {
  await page.locator(".tr__result").waitFor({ timeout: 60_000 });
  return page.locator(".tr__result").innerText();
}

await mkdir(OUT, { recursive: true });
const examples = await (await fetch(BASE + "/api/examples")).json();
if (!examples.length) throw new Error("no examples: make examples");
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
await page.goto(BASE + "/traductor/");
await page.locator(".tr__chip").first().waitFor();
await page.screenshot({ path: OUT + "traductor-1-lista.png" });
console.log("  traductor-1-lista");

await page.getByRole("button", { name: examples[0].text, exact: true }).click();
console.log(`  «${examples[0].text}» → «${await translated(page)}»`);
await page.screenshot({ path: OUT + "traductor-2-ejemplo.png" });
console.log("  traductor-2-ejemplo");

const typed = examples[examples.length - 1].text;
await page.locator("textarea").fill(typed);
await page.getByRole("button", { name: "Traducir" }).click();
await page.locator(".tr__wait").waitFor({ state: "detached", timeout: 60_000 });
console.log(`  «${typed}» → «${await translated(page)}»`);
await page.screenshot({ path: OUT + "traductor-3-escrita.png" });
console.log("  traductor-3-escrita");
await browser.close();
