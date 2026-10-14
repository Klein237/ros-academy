import { NoAccount, type ComptesClient, type QueueTicket } from "./api/comptes";
import { FULL_RETRY_MS, START_TIMEOUT_MS } from "./config";
import { HttpError, NotLoggedIn, type HubClient, type ServerStatus } from "./api/hub";
import { realTimers, sleep, type Timers } from "./backoff";

export type SessionState =
  | { kind: "auth" }
  | { kind: "noauth" }
  | { kind: "starting"; progress: number; message: string }
  | { kind: "full"; retryInMs: number; position?: number }
  /** Lab refusé : minutes du mois épuisées, ou (sansParcours) aucun parcours acheté ni offert. */
  | { kind: "quota"; sansParcours?: boolean }
  | { kind: "ready" }
  | { kind: "failed"; message: string }
  | { kind: "stopped"; reason: "idle" | "external" | "user" };

type HubLike = Pick<HubClient, "refreshToken" | "start" | "progress" | "server" | "stop">;
/** Service Comptes : quota de minutes et file d'attente (facultatif : lab ouvert sans compte). */
type AccountLike = Pick<ComptesClient, "me" | "joinQueue" | "beat" | "leaveQueue">;

export interface SessionOptions {
  fullRetryMs?: number;
  startTimeoutMs?: number;
  pollMs?: number;
  timers?: Timers;
  account?: AccountLike;
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
  private readonly account: AccountLike | null;
  private ticket: QueueTicket | null = null;

  constructor(
    private readonly hub: HubLike,
    opts: SessionOptions = {},
  ) {
    this.fullRetryMs = opts.fullRetryMs ?? FULL_RETRY_MS;
    this.startTimeoutMs = opts.startTimeoutMs ?? START_TIMEOUT_MS;
    this.pollMs = opts.pollMs ?? 1000;
    this.timers = opts.timers ?? realTimers;
    this.account = opts.account ?? null;
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
    // une coupure réseau passagère (Wi-Fi, changement de réseau) ne fait pas échouer l'ouverture :
    // jusqu'à trois nouveaux essais, 1 s, 2 s puis 3 s plus tard
    for (let essai = 1; ; essai++) {
      try {
        await this.hub.refreshToken();
        break;
      } catch (e) {
        if (e instanceof NotLoggedIn) return this.set({ kind: "noauth" });
        if (essai <= 3 && isTransient(e)) {
          console.warn("Jeton du lab : coupure passagère, nouvel essai", e);
          await sleep(1000 * essai, this.timers);
          continue;
        }
        return this.set({ kind: "failed", message: "Le serveur du lab est injoignable." });
      }
    }
    await this.launch();
  }

  /** Démarre (ou retrouve) le conteneur ; appelé aussi par le bouton Relancer. */
  async launch(): Promise<void> {
    this.timers.clearTimeout(this.retryTimer);
    this.set({ kind: "starting", progress: 0, message: "Demande d'un environnement ROS…" });
    const refus = await this.labRefused();
    if (refus) return this.set(refus);
    try {
      // une coupure pendant la demande ne dit rien du démarrage, qui continue côté Hub :
      // l'état réel est lu ensuite par waitReady (qui redemande le démarrage si besoin)
      const result = await transientAs(this.hub.start(), "pending" as const);
      if (result === "full") return this.waitForRoom();
      if (result !== "running") {
        const last = await transientAs(
          this.hub.progress((e) =>
            this.set({
              kind: "starting",
              progress: e.progress ?? 0,
              message: e.message ? frenchProgress(e.message) : "Démarrage du conteneur…",
            }),
          ),
          null,
        );
        if (last?.failed) {
          console.warn("Démarrage du lab refusé par le Hub", last);
          return this.set({ kind: "failed", message: "Le conteneur n'a pas pu démarrer." });
        }
      }
      await this.waitReady();
    } catch (e) {
      if (e instanceof NotLoggedIn) return this.set({ kind: "noauth" });
      // le Hub refuse le démarrage d'un étudiant dont le quota est épuisé
      const refus = await this.labRefused();
      if (refus) return this.set(refus);
      console.warn("Démarrage du lab en échec", e);
      this.set({ kind: "failed", message: "Le conteneur n'a pas pu démarrer." });
    }
  }

  /**
   * État « quota » seulement si Comptes répond qu'il ne reste aucune minute de lab : minutes du mois
   * épuisées, ou aucun parcours ouvert au compte (formule « aucune »). Une requête coupée
   * (réseau qui change, Comptes qui redémarre) est refaite deux fois : sans cela, un lab arrêté
   * pour quota s'afficherait « arrêté » sans dire pourquoi.
   */
  private async labRefused(): Promise<SessionState | null> {
    if (!this.account) return null;
    for (let essai = 1; ; essai++) {
      try {
        const me = await this.account.me();
        return me.minutes_restantes === 0 ? { kind: "quota", sansParcours: me.formule === "aucune" } : null;
      } catch (e) {
        // pas de session Comptes (lab ouvert sans compte) ou Comptes injoignable : le Hub tranche
        if (e instanceof NoAccount || essai >= 3) return null;
        await sleep(1000, this.timers);
      }
    }
  }

  /**
   * Serveur plein : l'étudiant prend un ticket dans la file de Comptes et le garde par
   * un battement ; le démarrage n'est retenté que lorsque son tour est arrivé.
   * Sans Comptes, nouvel essai à intervalle fixe.
   */
  private async waitForRoom(): Promise<void> {
    if (this.account) {
      try {
        this.ticket = this.ticket ? await this.beatOrRejoin(this.ticket) : await this.account.joinQueue();
      } catch {
        this.ticket = null;
      }
    }
    this.set({ kind: "full", retryInMs: this.fullRetryMs, ...(this.ticket ? { position: this.ticket.position } : {}) });
    this.retryTimer = this.timers.setTimeout(() => void this.onQueueTick(), this.fullRetryMs);
  }

  private async onQueueTick(): Promise<void> {
    if (this.state.kind !== "full") return;
    if (!this.ticket || !this.account) return this.launch();
    try {
      this.ticket = await this.beatOrRejoin(this.ticket);
    } catch {
      return this.launch(); // Comptes injoignable : on essaie quand même
    }
    if (this.ticket.a_vous) return this.launch();
    this.set({ kind: "full", retryInMs: this.fullRetryMs, position: this.ticket.position });
    this.retryTimer = this.timers.setTimeout(() => void this.onQueueTick(), this.fullRetryMs);
  }

  private async beatOrRejoin(ticket: QueueTicket): Promise<QueueTicket> {
    try {
      return await this.account!.beat(ticket.ticket);
    } catch {
      return this.account!.joinQueue(); // ticket expiré (onglet en veille) : nouvelle place
    }
  }

  /** Démarré : on rend sa place dans la file. */
  private leaveQueue(): void {
    const ticket = this.ticket;
    this.ticket = null;
    if (ticket && this.account) void this.account.leaveQueue(ticket.ticket).catch(() => undefined);
  }

  private async waitReady(): Promise<void> {
    const deadline = this.timers.now() + this.startTimeoutMs;
    while (this.timers.now() < deadline) {
      let server: ServerStatus | null;
      try {
        server = await this.hub.server();
      } catch (e) {
        if (!isTransient(e)) throw e;
        await sleep(this.pollMs, this.timers); // proxy ou réseau momentanément indisponible
        continue;
      }
      if (server?.ready) {
        this.leaveQueue();
        return this.set({ kind: "ready" });
      }
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
    // arrêté par Comptes au passage à zéro du quota, ou par le Hub
    this.set((await this.labRefused()) ?? { kind: "stopped", reason: "external" });
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

/** Erreur passagère : réseau coupé (status 0) ou proxy/Hub momentanément indisponible. */
function isTransient(e: unknown): boolean {
  return e instanceof TypeError || (e instanceof HttpError && (e.status === 0 || e.status >= 500));
}

/** Résultat d'une requête, ou `fallback` si elle échoue pour une raison passagère. */
async function transientAs<T, F>(promise: Promise<T>, fallback: F): Promise<T | F> {
  try {
    return await promise;
  } catch (e) {
    if (!isTransient(e)) throw e;
    console.warn("Requête au Hub interrompue, vérification de l'état du serveur", e);
    return fallback;
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
