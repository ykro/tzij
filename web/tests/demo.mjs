// Screenshots for docs/DEMO.md: the demo, step by step, driven with the same keys the presenter
// uses on stage. Needs `make up` running with the stage variant (real models, not MOCK_AI).
//   cd web && node tests/demo.mjs            (EMULATOR=0 skips the Android validator step)
// Output: docs/demo/NN-*.png
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8787";
// ANDROID_SERIAL, or the first running emulator in `adb devices` (its port changes between boots).
const emulatorSerial = () =>
  process.env.ANDROID_SERIAL ??
  execFileSync("adb", ["devices"]).toString().split("\n").map((l) => l.split("\t")[0]).find((s) => s.startsWith("emulator-"));
const OUT = new URL("../../docs/demo/", import.meta.url).pathname;
// Phrases from licensed data (Bloom Library, MINEDUC, CC BY 4.0); the first two are short phrases.
const SHORT_ES = process.env.SHORT_ES ?? "Ocho mazorcas.";
const SHORT_QUC = process.env.SHORT_QUC ?? "Jalajoj taq uwach rikil";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (path, body) =>
  fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
const state = async () => (await fetch(BASE + "/api/state")).json();
async function untilDone() {
  await sleep(300);
  for (let i = 0; i < 900; i++) {
    const s = await state();
    if (s.round?.status === "done") return s;
    await sleep(100);
  }
  throw new Error("round did not finish");
}
const times = [];
async function shot(page, name) {
  await sleep(500);
  await page.screenshot({ path: OUT + name + ".png" });
  const s = await state();
  const r = s.round?.results ?? {};
  const fmt = (x) => (x?.latency_ms != null ? `${(x.latency_ms / 1000).toFixed(1)} s` : "—");
  times.push(`${name}: David ${fmt(r.david)} (${r.david?.status ?? "-"}), Goliath ${fmt(r.goliath)} (${r.goliath?.status ?? "-"})`);
  console.log("  " + name);
}

await mkdir(OUT, { recursive: true });
await api("/api/reset");
await api("/api/connectivity", { force_offline: false });
const browser = await chromium.launch();
const p = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
await p.goto(BASE + "/presentador/");
await p.waitForSelector(".stage__bar");
await shot(p, "01-listo");

// 2. Evaluation round, Spanish -> K'iche' (key E).
await p.keyboard.press("e");
await untilDone();
await shot(p, "02-evaluacion-es-quc");

// 3. Change direction (D), evaluation round K'iche' -> Spanish (E).
await p.keyboard.press("d");
await p.keyboard.press("e");
await untilDone();
await shot(p, "03-evaluacion-quc-es");

// 4. Specialty round from the niche: Firefox Focus, translation memory (D back to es->quc, then S).
await p.keyboard.press("d");
await p.keyboard.press("s");
await untilDone();
await shot(p, "04-especialidad");

// 5. Live round with a short phrase typed in the command bar (/ , type, Enter).
await p.keyboard.press("/");
await p.fill("#phrase", SHORT_ES);
await shot(p, "05a-escribir-frase");
await p.keyboard.press("Enter");
await untilDone();
await shot(p, "05b-en-vivo-frase-corta");

// 6. Optional: the validator on the Android emulator votes; the verdict shows on the projector.
if (process.env.EMULATOR !== "0") {
  const serial = emulatorSerial();
  if (!serial) throw new Error("No emulator in `adb devices` (EMULATOR=0 skips this step)");
  const adb = (...args) => execFileSync("adb", ["-s", serial, ...args]);
  const phoneBase = BASE.replace("127.0.0.1", "10.0.2.2");
  adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", phoneBase + "/validar/", "com.android.chrome");
  await sleep(2500);
  adb("forward", "tcp:9333", "localabstract:chrome_devtools_remote");
  const mobile = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const tabs = mobile.contexts().flatMap((c) => c.pages()).filter((x) => x.url().includes("/validar"));
  const phone = tabs.pop();
  for (const old of tabs) await old.close();
  await phone.reload({ waitUntil: "domcontentloaded" });
  await p.keyboard.press("/");
  await p.fill("#phrase", "Distintas clases de comida");
  await p.keyboard.press("Enter");
  await untilDone();
  await phone.waitForSelector(".verdict");
  await phone.bringToFront();
  await sleep(1500);
  await writeFile(OUT + "06a-validador-emulador.png", adb("exec-out", "screencap", "-p"));
  console.log("  06a-validador-emulador");
  const button = await phone.locator(".verdict").nth(0).elementHandle();
  await button.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await button.evaluate((el) => el.click());
  await p.waitForFunction(() => document.querySelectorAll(".badge").length > 0, null, { timeout: 5000 });
  await shot(p, "06b-veredicto-en-pantalla");
  await mobile.close();
  adb("forward", "--remove", "tcp:9333");
}

// 7. Wi-Fi off (rehearsal switch in the command bar), then an evaluation round (E).
await p.keyboard.press("/");
// Controlled checkbox: the server confirms the switch over SSE, so click and wait for the state.
await p.getByLabel("Simular sin Wi-Fi (ensayo)").click();
for (let i = 0; i < 50 && !(await state()).force_offline; i++) await sleep(100);
await sleep(300);
await p.keyboard.press("Escape");
await p.keyboard.press("e");
await untilDone();
await shot(p, "07-sin-conexion");
await api("/api/connectivity", { force_offline: false });

// 8. K'iche' -> Spanish live round with a short phrase, back online.
await p.keyboard.press("d");
await p.keyboard.press("/");
await p.fill("#phrase", SHORT_QUC);
await p.keyboard.press("Enter");
await untilDone();
await shot(p, "08-en-vivo-quc-es");

// 9. Model card panel (M).
await p.keyboard.press("m");
await shot(p, "09-ficha-del-modelo");
await p.keyboard.press("Escape");

await browser.close();
await writeFile(OUT + "timings.txt", times.join("\n") + "\n");
console.log(times.join("\n"));
