import { FULL_RETRY_MS, START_TIMEOUT_MS } from "./config";
import { NotLoggedIn, type HubClient } from "./api/hub";
import { realTimers, sleep, type Timers } from "./backoff";

export type SessionState =
  | { kind: "auth" }
  | { kind: "noauth" }
  | { kind: "starting"; progress: number; message: string }
  | { kind: "full"; retryInMs: number }
  | { kind: "ready" }
  | { kind: "failed"; message: string }
  | { kind: "stopped"; reason: "idle" | "external" | "user" };

type HubLike = Pick<HubClient, "refreshToken" | "start" | "progress" | "server" | "stop">;

export interface SessionOptions {
  fullRetryMs?: number;
  startTimeoutMs?: number;
  pollMs?: number;
  timers?: Timers;
}

/** Démarrage du conteneur de l'étudiant, vu comme une suite d'états affichables. */
export class Session {
  state: SessionState = { kind: "auth" };
  private listeners: ((s: SessionState) => void)[] = [];
  private retryTimer: unknown = null;
  private readonly fullRetryMs: number;
  private readonly startTimeoutMs: number;
  private readonly pollMs: number;
  private readonly timers: Timers;

  constructor(
    private readonly hub: HubLike,
    opts: SessionOptions = {},
  ) {
    this.fullRetryMs = opts.fullRetryMs ?? FULL_RETRY_MS;
    this.startTimeoutMs = opts.startTimeoutMs ?? START_TIMEOUT_MS;
    this.pollMs = opts.pollMs ?? 1000;
    this.timers = opts.timers ?? realTimers;
  }

  onChange(cb: (s: SessionState) => void): void {
    this.listeners.push(cb);
  }

  private set(state: SessionState): void {
    this.state = state;
    for (const cb of this.listeners) cb(state);
  }

  async open(): Promise<void> {
    this.set({ kind: "auth" });
    try {
      await this.hub.refreshToken();
    } catch (e) {
      if (e instanceof NotLoggedIn) return this.set({ kind: "noauth" });
      return this.set({ kind: "failed", message: "Le serveur du lab est injoignable." });
    }
    await this.launch();
  }

  /** Démarre (ou retrouve) le conteneur ; appelé aussi par le bouton Relancer. */
  async launch(): Promise<void> {
    this.timers.clearTimeout(this.retryTimer);
    this.set({ kind: "starting", progress: 0, message: "Demande d'un environnement ROS…" });
    try {
      const result = await this.hub.start();
      if (result === "full") return this.waitForRoom();
      if (result !== "running") {
        const last = await this.hub.progress((e) =>
          this.set({
            kind: "starting",
            progress: e.progress ?? 0,
            message: e.message ? frenchProgress(e.message) : "Démarrage du conteneur…",
          }),
        );
        if (last?.failed) {
          return this.set({ kind: "failed", message: "Le conteneur n'a pas pu démarrer." });
        }
      }
      await this.waitReady();
    } catch (e) {
      if (e instanceof NotLoggedIn) return this.set({ kind: "noauth" });
      this.set({ kind: "failed", message: "Le conteneur n'a pas pu démarrer." });
    }
  }

  /** Serveur plein : nouvel essai automatique. */
  private waitForRoom(): void {
    this.set({ kind: "full", retryInMs: this.fullRetryMs });
    this.retryTimer = this.timers.setTimeout(() => void this.launch(), this.fullRetryMs);
  }

  private async waitReady(): Promise<void> {
    const deadline = this.timers.now() + this.startTimeoutMs;
    while (this.timers.now() < deadline) {
      const server = await this.hub.server();
      if (server?.ready) return this.set({ kind: "ready" });
      if (!server) {
        // un ancien conteneur finissait de s'arrêter : on redemande le démarrage
        if ((await this.hub.start()) === "full") return this.waitForRoom();
      }
      await sleep(this.pollMs, this.timers);
    }
    this.set({ kind: "failed", message: "Le conteneur met trop de temps à démarrer." });
  }

  /** Vrai si le conteneur tourne encore ; sinon passe à l'état `stopped`. */
  async checkAlive(): Promise<boolean> {
    if (this.state.kind !== "ready") return false;
    let server: Awaited<ReturnType<HubLike["server"]>>;
    try {
      server = await this.hub.server();
    } catch {
      return true; // réseau coupé : on ne conclut rien
    }
    if (server?.ready) return true;
    this.set({ kind: "stopped", reason: "external" });
    return false;
  }

  async stop(reason: "idle" | "user"): Promise<void> {
    this.set({ kind: "stopped", reason });
    try {
      await this.hub.stop();
    } catch {
      // le culler du Hub arrêtera le conteneur de toute façon
    }
  }
}

/** Messages de progression de JupyterHub/DockerSpawner, traduits pour l'étudiant. */
export function frenchProgress(message: string): string {
  if (/pulling/i.test(message)) return "Téléchargement de l'image ROS…";
  if (/requested/i.test(message)) return "Environnement demandé…";
  if (/started|ready/i.test(message)) return "Conteneur démarré, connexion…";
  if (/spawn/i.test(message)) return "Démarrage du conteneur…";
  return "Démarrage du conteneur…";
}
