// The stage emulator is shared with other demos, and Escudo's `make android-prep` sets a screen PIN
// (a fingerprint needs one). After a boot the screen is locked and Chrome can't start until the first
// unlock, so wake the emulator and enter the PIN before opening the validator.
import { setTimeout as sleep } from "node:timers/promises";

export async function unlockEmulator(adb, pin = process.env.EMULATOR_PIN ?? "1234") {
  const locked = () => adb("shell", "dumpsys", "trust").toString().includes("deviceLocked=1");
  adb("shell", "input", "keyevent", "KEYCODE_WAKEUP");
  if (!locked()) return;
  await sleep(1000); // the screen turns on
  adb("shell", "wm", "dismiss-keyguard");
  await sleep(1000); // the PIN pad slides in; keys typed before it are lost
  adb("shell", "input", "text", pin);
  adb("shell", "input", "keyevent", "KEYCODE_ENTER");
  for (let i = 0; i < 20 && locked(); i++) await sleep(500);
  if (locked()) throw new Error(`The emulator is still locked: set EMULATOR_PIN to its screen PIN (tried ${pin})`);
}
