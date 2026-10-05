import { realTimers, type Timers } from "./backoff";

/**
 * Un terminal tout juste créé n'a pas encore affiché son invite (bash charge ROS) : une commande
 * envoyée trop tôt s'affiche avant l'invite. Le shell est prêt quand il a écrit quelque chose
 * (l'invite) puis s'est tu `quietMs` ; au plus tard après `maxMs`.
 */
export class ShellReady {
  readonly ready: Promise<void>;
  private resolve!: () => void;
  private done = false;
  private quiet: unknown = null;
  private readonly max: unknown;

  constructor(
    private readonly timers: Timers = realTimers,
    private readonly quietMs = 300,
    maxMs = 10_000,
  ) {
    this.ready = new Promise((resolve) => (this.resolve = resolve));
    this.max = timers.setTimeout(() => this.finish(), maxMs);
  }

  /** Le shell a écrit : on attend qu'il se taise. */
  data(): void {
    if (this.done) return;
    if (this.quiet !== null) this.timers.clearTimeout(this.quiet);
    this.quiet = this.timers.setTimeout(() => this.finish(), this.quietMs);
  }

  /** Prêt sans attendre (terminal déjà ouvert avant le rechargement de la page). */
  finish(): void {
    if (this.done) return;
    this.done = true;
    if (this.quiet !== null) this.timers.clearTimeout(this.quiet);
    this.timers.clearTimeout(this.max);
    this.resolve();
  }
}
