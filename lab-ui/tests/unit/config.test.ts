import { expect, it } from "vitest";
import { IDLE_STOP_MS, readConfig } from "../../src/config";

it("valeurs par défaut : arrêt à 20 min, avertissement 5 min avant", () => {
  const c = readConfig("");
  expect(c.idleStopMs).toBe(IDLE_STOP_MS);
  expect(c.idleStopMs - c.idleWarnMs).toBe(5 * 60_000);
  expect(c.openPath).toBeNull();
  expect(c.folder).toBe("");
});

it("lit open et dossier, et refuse les chemins qui sortent du dossier personnel", () => {
  const c = readConfig("?open=~/ws/module-02/talker.py&dossier=ws/module-02");
  expect(c.openPath).toBe("ws/module-02/talker.py");
  expect(c.folder).toBe("ws/module-02");
  expect(readConfig("?open=../../etc/passwd").openPath).toBeNull();
});

it("?inactivite ne peut que raccourcir le délai", () => {
  expect(readConfig("?inactivite=40").idleStopMs).toBe(40_000);
  expect(readConfig("?inactivite=40").idleWarnMs).toBe(30_000);
  expect(readConfig("?inactivite=999999").idleStopMs).toBe(IDLE_STOP_MS);
  expect(readConfig("?inactivite=1").idleStopMs).toBe(IDLE_STOP_MS);
  expect(readConfig("?inactivite=abc").idleStopMs).toBe(IDLE_STOP_MS);
});

it("?vue=bureau : la fenêtre séparée du bureau", () => {
  expect(readConfig("").desktopOnly).toBe(false);
  expect(readConfig("?vue=bureau").desktopOnly).toBe(true);
  expect(readConfig("?vue=autre").desktopOnly).toBe(false);
});
