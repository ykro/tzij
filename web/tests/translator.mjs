// Screenshots of the live demo page (Cloud Run) for docs/DEMO.md, and a check that it works end to
// end: David waking up, the page ready, an example (both columns, the correct translation and how
// close each one got) and a typed sentence. 1920x1080 (projector) and 1280x800 (laptop).
//   make screens            (or: cd web && BASE_URL=https://... node tests/translator.mjs)
// Output: docs/demo/pagina-*.png (the 1280x800 pass only checks the layout). Exits with an error if a column doesn't fill.
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = (process.env.BASE_URL ?? "").replace(/\/$/, "");
if (!BASE) throw new Error("BASE_URL is not set: make screens");
const OUT = new URL("../../docs/demo/", import.meta.url).pathname;
const TYPED = process.env.TYPED ?? "Bloquear rastreadores";

async function bothDone(page) {
  await page.waitForFunction(() => document.querySelectorAll('.tx__col[aria-busy="true"]').length === 0
    && document.querySelectorAll(".tx__out, .tx__fail").length === 2, null, { timeout: 120_000 });
  await page.waitForTimeout(900); // the closeness bars finish growing
  const failed = await page.$$eval(".tx__fail", (els) => els.map((e) => e.textContent));
  if (failed.length) throw new Error(`a column failed: ${failed.join(" | ")}`);
  return page.$$eval(".tx__col", (cols) => cols.map((c) => `${c.querySelector(".tx__name").textContent}: «${c.querySelector(".tx__out").textContent}» ${c.querySelector(".tx__meter-row b")?.textContent ?? ""} ${c.querySelector(".tx__facts dd")?.textContent ?? ""}`));
}

await mkdir(OUT, { recursive: true });
const examples = await (await fetch(BASE + "/api/examples")).json();
if (!examples.length) throw new Error("no examples: make examples");
const browser = await chromium.launch();
for (const [w, h, suffix] of [[1920, 1080, ""], [1280, 800, "-laptop"]]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
  const t0 = Date.now();
  await page.goto(BASE + "/");
  await page.locator(".tx__chip").first().waitFor();
  if (!suffix && (await page.locator(".tx__net--waking").count())) {
    await page.screenshot({ path: OUT + "pagina-0-preparando.png" });
  }
  await page.locator(".tx__net--on").waitFor({ timeout: 10 * 60_000 });
  console.log(`  David listo en ${Math.round((Date.now() - t0) / 1000)} s`);
  if (!suffix) await page.screenshot({ path: OUT + "pagina-1-lista.png" });

  await page.getByRole("button", { name: examples[0].text, exact: true }).click();
  await page.locator('.tx__col[aria-busy="true"]').first().waitFor();
  if (!suffix) await page.screenshot({ path: OUT + "pagina-2-traduciendo.png" });
  console.log("  " + (await bothDone(page)).join(" · "));
  if (!suffix) await page.screenshot({ path: OUT + "pagina-3-ejemplo.png" });
  if (suffix) { await page.close(); continue; }

  await page.locator("textarea").fill(TYPED);
  await page.getByRole("button", { name: "Traducir" }).click();
  console.log("  " + (await bothDone(page)).join(" · "));
  await page.screenshot({ path: OUT + "pagina-4-escrita.png" });
  await page.close();
}
await browser.close();
