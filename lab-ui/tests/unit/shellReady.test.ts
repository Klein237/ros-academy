import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ShellReady } from "../../src/shellReady";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function watch(s: ShellReady) {
  const state = { ready: false };
  void s.ready.then(() => (state.ready = true));
  return state;
}

it("attend l'invite puis le silence du shell", async () => {
  const s = new ShellReady();
  const state = watch(s);
  await vi.advanceTimersByTimeAsync(2000); // bash charge ROS : rien d'écrit
  expect(state.ready).toBe(false);
  s.data();
  await vi.advanceTimersByTimeAsync(200);
  s.data(); // la suite de l'invite
  await vi.advanceTimersByTimeAsync(200);
  expect(state.ready).toBe(false);
  await vi.advanceTimersByTimeAsync(100);
  expect(state.ready).toBe(true);
});

it("n'attend pas indéfiniment un shell muet", async () => {
  const state = watch(new ShellReady());
  await vi.advanceTimersByTimeAsync(10_000);
  expect(state.ready).toBe(true);
});

it("finish rend prêt tout de suite", async () => {
  const s = new ShellReady();
  const state = watch(s);
  s.finish();
  s.data();
  await vi.advanceTimersByTimeAsync(0);
  expect(state.ready).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});
