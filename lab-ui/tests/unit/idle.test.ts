import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { IdleWatcher } from "../../src/idle";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function make() {
  const events: string[] = [];
  const w = new IdleWatcher({
    warnAfterMs: 15 * 60_000,
    stopAfterMs: 20 * 60_000,
    onWarn: () => events.push("warn"),
    onActive: () => events.push("active"),
    onStop: () => events.push("stop"),
  });
  w.start();
  return { w, events };
}

it("avertit à 15 min puis arrête à 20 min", () => {
  const { events } = make();
  vi.advanceTimersByTime(15 * 60_000 - 2000);
  expect(events).toEqual([]);
  vi.advanceTimersByTime(3000);
  expect(events[0]).toBe("warn");
  vi.advanceTimersByTime(5 * 60_000);
  expect(events.at(-1)).toBe("stop");
  expect(events.filter((e) => e === "stop")).toHaveLength(1);
});

it("une activité retire l'avertissement et repousse l'arrêt", () => {
  const { w, events } = make();
  vi.advanceTimersByTime(16 * 60_000);
  w.activity();
  expect(events.at(-1)).toBe("active");
  vi.advanceTimersByTime(14 * 60_000);
  expect(events).not.toContain("stop");
  vi.advanceTimersByTime(6 * 60_000 + 1000);
  expect(events.at(-1)).toBe("stop");
});

it("une activité régulière n'avertit jamais", () => {
  const { w, events } = make();
  for (let i = 0; i < 10; i++) {
    vi.advanceTimersByTime(10 * 60_000);
    w.activity();
  }
  expect(events).toEqual([]);
});
