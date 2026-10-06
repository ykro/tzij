// Screenshots of the translator page (/traductor/) for docs/DEMO.md, and a check that it works:
// the empty page, an example (both columns, the correct translation and how close each one got),
// a typed sentence, and the same example with "Wi-Fi off" simulated. Needs `make up` with the stage
// models. 1920x1080 (projector) and 1280x800 (laptop).
//   cd web && node tests/translator.mjs
// Output: docs/demo/traductor-*.png. Exits with an error if a column doesn't fill.
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8787";
const OUT = new URL("../../docs/demo/", import.meta.url).pathname;
const TYPED = process.env.TYPED ?? "Agregar otro motor de búsqueda";
const api = (path, body) =>
  fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function bothDone(page) {
  await page.waitForFunction(() => document.querySelectorAll('.tx__col[aria-busy="true"]').length === 0
    && document.querySelectorAll(".tx__out, .tx__fail").length === 2, null, { timeout: 90_000 });
  await page.waitForTimeout(900); // the closeness bars finish growing
  return page.$$eval(".tx__col", (cols) => cols.map((c) => `${c.querySelector(".tx__name").textContent}: «${(c.querySelector(".tx__out, .tx__fail") ?? {}).textContent}» ${c.querySelector(".tx__meter-row b")?.textContent ?? ""}`));
}

await mkdir(OUT, { recursive: true });
await api("/api/connectivity", { force_offline: false });
const examples = await (await fetch(BASE + "/api/examples")).json();
if (!examples.length) throw new Error("no examples: make examples");
const browser = await chromium.launch();
for (const [w, h, suffix] of [[1920, 1080, ""], [1280, 800, "-laptop"]]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
  await page.goto(BASE + "/traductor/");
  await page.locator(".tx__chip").first().waitFor();
  await page.screenshot({ path: OUT + `traductor-1-lista${suffix}.png` });

  await page.getByRole("button", { name: examples[0].text, exact: true }).click();
  await page.locator('.tx__col[aria-busy="true"]').first().waitFor();
  if (!suffix) await page.screenshot({ path: OUT + "traductor-2-traduciendo.png" });
  console.log("  " + (await bothDone(page)).join(" · "));
  await page.screenshot({ path: OUT + `traductor-3-ejemplo${suffix}.png` });
  if (suffix) { await page.close(); continue; }

  await page.locator("textarea").fill(TYPED);
  await page.getByRole("button", { name: "Traducir" }).click();
  console.log("  " + (await bothDone(page)).join(" · "));
  await page.screenshot({ path: OUT + "traductor-4-escrita.png" });

  await api("/api/connectivity", { force_offline: true });
  await page.getByRole("button", { name: examples[1].text, exact: true }).click();
  console.log("  " + (await bothDone(page)).join(" · "));
  await page.waitForSelector(".tx__net--off");
  await page.screenshot({ path: OUT + "traductor-5-sin-internet.png" });
  await api("/api/connectivity", { force_offline: false });
  await page.close();
}
await browser.close();
