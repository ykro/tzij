// Validator on the Android emulator (Chrome), presenter on desktop Chromium.
// The emulator reaches the laptop at 10.0.2.2. Measures tap -> presenter latency.
//   BASE_URL=http://127.0.0.1:8788 ANDROID_SERIAL=emulator-5556 node tests/emulator.mjs
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8787";
const SERIAL = process.env.ANDROID_SERIAL ?? "emulator-5556";
const PHONE_BASE = BASE.replace("127.0.0.1", "10.0.2.2").replace("localhost", "10.0.2.2");
const OUT = new URL("../test-results/screens/", import.meta.url).pathname;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const adb = (...args) => execFileSync("adb", ["-s", SERIAL, ...args]);
const api = (path, body) =>
  fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
async function untilDone() {
  for (let i = 0; i < 600; i++) {
    const s = await (await fetch(BASE + "/api/state")).json();
    if (s.round?.status === "done") return s;
    await sleep(100);
  }
  throw new Error("round did not finish");
}
async function screencap(name, page) {
  // The emulator is shared: bring Chrome and our tab to the front right before capturing.
  adb("shell", "am", "start", "-n", "com.android.chrome/com.google.android.apps.chrome.Main");
  if (page) await page.bringToFront();
  await sleep(1500);
  await writeFile(OUT + name + ".png", adb("exec-out", "screencap", "-p"));
  console.log("  " + name);
}

await mkdir(OUT, { recursive: true });
await api("/api/reset");
await api("/api/connectivity", { force_offline: false });

const desktop = await chromium.launch();
const presenter = await (await desktop.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
await presenter.goto(BASE + "/presentador/");

// Real Chrome on the emulator, driven over its DevTools socket (adb forward).
adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", PHONE_BASE + "/validar/", "com.android.chrome");
await sleep(2500);
adb("forward", "tcp:9333", "localabstract:chrome_devtools_remote");
const mobile = await chromium.connectOverCDP("http://127.0.0.1:9333");
const tabs = mobile.contexts().flatMap((c) => c.pages()).filter((p) => p.url().includes("/validar"));
const phone = tabs.pop();
if (!phone) throw new Error("validator tab not found in emulator Chrome");
// Earlier runs leave tabs with open event streams; Chrome allows 6 connections per host.
for (const old of tabs) await old.close();
console.log(`emulator ${SERIAL}: ${await phone.evaluate(() => navigator.userAgent)}`);
await phone.reload({ waitUntil: "domcontentloaded" });
await phone.waitForSelector(".phone__state");
await screencap("emulator-01-waiting", phone);

await api("/api/rounds", { kind: "en_vivo", direction: "es-quc", text: process.env.LIVE_PHRASE ?? "Buenos días, ¿cómo estás?" });
await untilDone();
await phone.waitForSelector(".verdict");
await phone.bringToFront();
await screencap("emulator-02-live", phone);

const before = await presenter.locator(".badge").count();
const button = await phone.locator(".verdict").nth(0).elementHandle();
await button.evaluate((el) => el.scrollIntoView({ block: "center" }));
// Timer starts when the tap is delivered in the emulator's Chrome (DOM click, no Playwright
// actionability polling over adb), and stops when the presenter shows the verdict.
const tapped = Date.now();
await button.evaluate((el) => el.click());
await presenter.waitForFunction((n) => document.querySelectorAll(".badge").length > n, before, { timeout: 5000 });
const ms = Date.now() - tapped;
console.log(`  verdict from the emulator reached the presenter in ${ms} ms`);
await screencap("emulator-03-voted", phone);
await presenter.screenshot({ path: OUT + "emulator-presenter-after-vote.png" });
await mobile.close();
adb("forward", "--remove", "tcp:9333");
await desktop.close();
if (ms > 1000) throw new Error(`verdict took ${ms} ms (> 1 s)`);
