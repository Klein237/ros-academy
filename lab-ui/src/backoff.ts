/** Délai croissant entre deux tentatives de reconnexion. */
export class Backoff {
  private attempt = 0;

  constructor(
    private readonly minMs = 500,
    private readonly maxMs = 10_000,
    private readonly factor = 2,
  ) {}

  next(): number {
    const delay = Math.min(this.maxMs, this.minMs * this.factor ** this.attempt);
    this.attempt += 1;
    return delay;
  }

  reset(): void {
    this.attempt = 0;
  }
}

export interface Timers {
  setTimeout(fn: () => void, ms: number): unknown;
  clearTimeout(id: unknown): void;
  setInterval(fn: () => void, ms: number): unknown;
  clearInterval(id: unknown): void;
  now(): number;
}

export const realTimers: Timers = {
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (id) => globalThis.clearTimeout(id as number),
  setInterval: (fn, ms) => globalThis.setInterval(fn, ms),
  clearInterval: (id) => globalThis.clearInterval(id as number),
  now: () => Date.now(),
};

export function sleep(ms: number, timers: Timers = realTimers): Promise<void> {
  return new Promise((resolve) => timers.setTimeout(resolve, ms));
}
