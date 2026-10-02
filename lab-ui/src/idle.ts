import { realTimers, type Timers } from "./backoff";

export interface IdleOptions {
  warnAfterMs: number;
  stopAfterMs: number;
  onWarn(remainingMs: number): void;
  onActive(): void;
  onStop(): void;
  timers?: Timers;
  tickMs?: number;
}

/** Inactivité de l'étudiant dans la page : avertissement, puis arrêt du lab. */
export class IdleWatcher {
  private last: number;
  private warned = false;
  private stopped = false;
  private interval: unknown = null;
  private readonly timers: Timers;

  constructor(private readonly opts: IdleOptions) {
    this.timers = opts.timers ?? realTimers;
    this.last = this.timers.now();
  }

  start(): void {
    this.last = this.timers.now();
    this.warned = this.stopped = false;
    this.timers.clearInterval(this.interval);
    this.interval = this.timers.setInterval(() => this.tick(), this.opts.tickMs ?? 1000);
  }

  activity(): void {
    if (this.stopped) return;
    this.last = this.timers.now();
    if (this.warned) {
      this.warned = false;
      this.opts.onActive();
    }
  }

  private tick(): void {
    const idle = this.timers.now() - this.last;
    if (idle >= this.opts.stopAfterMs) {
      this.stopped = true;
      this.dispose();
      this.opts.onStop();
    } else if (idle >= this.opts.warnAfterMs) {
      this.warned = true;
      this.opts.onWarn(this.opts.stopAfterMs - idle);
    }
  }

  dispose(): void {
    this.timers.clearInterval(this.interval);
    this.interval = null;
  }
}

/** Événements qui comptent comme une présence de l'étudiant. */
export const ACTIVITY_EVENTS = ["keydown", "pointerdown", "pointermove", "wheel", "touchstart"] as const;
