// Screenshots of every designed state, at 1920×1080 (presenter) and 390×844 (validator).
// Needs a running duel service: BASE_URL (default http://127.0.0.1:8787). Drives it via its API.
// Output: web/test-results/screens/*.png
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8787";
const OUT = new URL("../test-results/screens/", import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (path, body) =>
  fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
const state = async () => (await fetch(BASE + "/api/state")).json();
async function untilDone() {
  for (let i = 0; i < 600; i++) {
    const s = await state();
    if (s.round?.status === "done") return s;
    await sleep(100);
  }
  throw new Error("round did not finish");
}

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const presenter = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
const phone = await (await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })).newPage();
const shot = async (page, name) => {
  await sleep(450);
  await page.screenshot({ path: OUT + name + ".png" });
  console.log("  " + name);
};

await api("/api/reset");
await api("/api/connectivity", { force_offline: false });
await presenter.goto(BASE + "/presentador/");
await phone.goto(BASE + "/validar/");
await presenter.waitForSelector(".stage__bar");
await shot(presenter, "presenter-01-empty");
await shot(phone, "phone-01-waiting");

// Evaluation round: capture while translating, then done.
await api("/api/rounds", { kind: "evaluacion", direction: "es-quc" });
await sleep(150);
await shot(presenter, "presenter-02-translating");
await untilDone();
await shot(presenter, "presenter-03-evaluation");
await shot(phone, "phone-02-evaluation");

// Live round: phone votes, presenter shows the verdicts.
await api("/api/rounds", { kind: "en_vivo", direction: "es-quc", text: process.env.LIVE_PHRASE ?? "Buenos días, ¿cómo estás?" });
await untilDone();
await shot(phone, "phone-03-live");
const buttons = phone.locator(".verdict");
// End-to-end latency: tap on the phone -> verdict badge on the presenter screen.
const before = await presenter.locator(".badge").count();
const tapped = Date.now();
await buttons.nth(0).click();
await presenter.waitForFunction((n) => document.querySelectorAll(".badge").length > n, before, { timeout: 5000 });
const verdictMs = Date.now() - tapped;
console.log(`  verdict reached the presenter in ${verdictMs} ms`);
if (verdictMs > 1000) throw new Error(`verdict took ${verdictMs} ms (> 1 s)`);
await buttons.nth(4).click();
await shot(phone, "phone-04-voted");
await shot(presenter, "presenter-04-live-verdicts");

// K'iche' -> Spanish evaluation round.
await api("/api/rounds", { kind: "evaluacion", direction: "quc-es" });
await untilDone();
await shot(presenter, "presenter-05-quc-es");

// Wi-Fi off: Goliath offline, David still translates.
await api("/api/connectivity", { force_offline: true });
await api("/api/rounds", { kind: "evaluacion", direction: "es-quc" });
await untilDone();
await shot(presenter, "presenter-06-offline");
await shot(phone, "phone-05-offline");
await api("/api/connectivity", { force_offline: false });

// Presenter tools.
await presenter.keyboard.press("m");
await shot(presenter, "presenter-07-model-card");
await presenter.keyboard.press("Escape");
await presenter.keyboard.press("/");
await presenter.fill("#phrase", "¿Dónde está el mercado?");
await shot(presenter, "presenter-08-command-bar");
await presenter.keyboard.press("Escape");

await browser.close();
console.log("screenshots in " + OUT);
