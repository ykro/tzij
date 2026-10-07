// Screenshots of the live demo page (Cloud Run) for docs/DEMO.md, and a check that it works end to
// end: David waking up, the page ready, an example (both columns, the correct translation, how close
// each one got, time and cost) and a typed phrase (the closest human translations in the memory).
// Projector 1920x1080, laptop 1280x800, tablet 768x1024 and phones 414x896 and 375x812.
//   make screens            (or: cd web && BASE_URL=https://... node tests/translator.mjs)
// Output: docs/demo/pagina-*.png. Exits with an error if a column doesn't fill or the page is wider
// than the screen (sideways scrolling).
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = (process.env.BASE_URL ?? "").replace(/\/$/, "");
if (!BASE) throw new Error("BASE_URL is not set: make screens");
const OUT = new URL("../../docs/demo/", import.meta.url).pathname;
const TYPED = process.env.TYPED ?? "Bloquear rastreadores de anuncios";

async function bothDone(page) {
  await page.waitForFunction(() => document.querySelectorAll('.tx__col[aria-busy="true"]').length === 0
    && document.querySelectorAll(".tx__out, .tx__fail").length === 2, null, { timeout: 180_000 });
  await page.waitForTimeout(900); // the closeness bars finish growing
  const failed = await page.$$eval(".tx__fail", (els) => els.map((e) => e.textContent));
  if (failed.length) throw new Error(`a column failed: ${failed.join(" | ")}`);
  return page.$$eval(".tx__col", (cols) => cols.map((c) => `${c.querySelector(".tx__name").textContent}: «${c.querySelector(".tx__out").textContent}» ${c.querySelector(".tx__meter-row b")?.textContent ?? ""} ${[...c.querySelectorAll(".tx__facts dd")].map((d) => d.textContent).join(" | ")}`));
}

async function noSideways(page, label) {
  const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (wide > 1) throw new Error(`${label}: the page is ${wide}px wider than the screen`);
}

await mkdir(OUT, { recursive: true });
const examples = await (await fetch(BASE + "/api/examples")).json();
if (!examples.length) throw new Error("no examples: make examples");
const browser = await chromium.launch();
const sizes = [[1920, 1080, ""], [1280, 800, "-laptop"], [768, 1024, "-tablet"], [414, 896, "-telefono"], [375, 812, "-telefono-chico"]];
for (const [w, h, suffix] of sizes) {
  const mobile = w < 900;
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: mobile ? 2 : 1, isMobile: w < 600, hasTouch: mobile })).newPage();
  const t0 = Date.now();
  await page.goto(BASE + "/");
  await page.locator(".tx__chip").first().waitFor();
  if (!suffix && (await page.locator(".tx__net--waking").count())) {
    await page.screenshot({ path: OUT + "pagina-0-preparando.png" });
  }
  await page.locator(".tx__net--on").waitFor({ timeout: 10 * 60_000 });
  console.log(`${w}x${h}: David listo en ${Math.round((Date.now() - t0) / 1000)} s`);
  await noSideways(page, `${w}x${h} ready`);
  if (!suffix) await page.screenshot({ path: OUT + "pagina-1-lista.png" });
  if (suffix === "-telefono") await page.screenshot({ path: OUT + `pagina-1-lista${suffix}.png`, fullPage: true });

  await page.getByRole("button", { name: examples[0].text, exact: true }).click();
  await page.locator('.tx__col[aria-busy="true"]').first().waitFor();
  if (!suffix) await page.screenshot({ path: OUT + "pagina-2-traduciendo.png" });
  console.log("  " + (await bothDone(page)).join(" · "));
  await noSideways(page, `${w}x${h} example`);
  if (!suffix) await page.screenshot({ path: OUT + "pagina-3-ejemplo.png" });
  else await page.screenshot({ path: OUT + `pagina-3-ejemplo${suffix}.png`, fullPage: mobile });

  if (suffix && suffix !== "-telefono") { await page.close(); continue; }
  await page.locator("textarea").fill(TYPED);
  await page.getByRole("button", { name: "Traducir" }).click();
  console.log("  " + (await bothDone(page)).join(" · "));
  await page.locator(".tx__memory, .tx__ref-label").first().waitFor({ timeout: 30_000 }).catch(() => undefined);
  await page.waitForTimeout(400);
  await noSideways(page, `${w}x${h} typed`);
  await page.screenshot({ path: OUT + `pagina-4-escrita${suffix}.png`, fullPage: mobile });
  await page.close();
}
await browser.close();
