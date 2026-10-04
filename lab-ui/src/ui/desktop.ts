/**
 * Bureau graphique du lab (RViz, Gazebo) : l'écran X virtuel du conteneur (Xvnc), affiché
 * par noVNC. Le flux VNC passe par jupyter-server-proxy (/user/<nom>/bureau/), authentifié
 * par le jeton du Lab UI ; le bureau démarre au premier accès.
 */
import { Backoff, realTimers, type Timers } from "../backoff";
import { button, h } from "./dom";

export type DesktopStatus = "arrete" | "connexion" | "connecte" | "reconnexion" | "separe";

const STATUS_TEXT: Record<DesktopStatus, string> = {
  arrete: "arrêté",
  connexion: "démarrage…",
  connecte: "connecté",
  reconnexion: "reconnexion…",
  separe: "dans une fenêtre séparée",
};

/** Ce que le panneau utilise du client RFB de noVNC (remplaçable dans les tests). */
export interface RfbLike {
  scaleViewport: boolean;
  resizeSession: boolean;
  addEventListener(type: "connect" | "disconnect", listener: (ev: Event) => void): void;
  disconnect(): void;
  focus(): void;
}

export type RfbFactory = (target: HTMLElement, url: string) => RfbLike;

export interface DesktopOptions {
  url: () => Promise<string>;
  rfb?: RfbFactory;
  timers?: Timers;
  /** Bouton « Agrandir » : le bureau prend tout l'espace de travail (absent si non fourni). */
  onMaximize?: () => void;
  /** Bouton « Fenêtre séparée » (absent si non fourni). */
  onDetach?: () => void;
  /** « Ramener ici » quand le bureau est dans une fenêtre séparée. */
  onReattach?: () => void;
}

async function noVncFactory(): Promise<RfbFactory> {
  // chargé à la première ouverture du bureau seulement
  const { default: RFB } = await import("@novnc/novnc");
  return (target, url) => new RFB(target, url, { shared: true }) as unknown as RfbLike;
}

export class DesktopPanel {
  readonly el = h("section", { class: "panel desktop", attrs: { "aria-label": "Bureau graphique", hidden: "" } });
  private readonly screen = h("div", { class: "desktop-screen", attrs: { "aria-label": "Écran du lab" } });
  private readonly statusPill = h("span", { class: "pill", text: STATUS_TEXT.arrete });
  private readonly hint = h("p", {
    class: "desktop-hint muted small",
    text: "Lancez rviz2 ou gazebo dans un terminal : leurs fenêtres s'affichent ici.",
  });
  private readonly maximizeButton: HTMLButtonElement | null;
  private readonly detachedNote: HTMLElement;
  private rfb: RfbLike | null = null;
  private wanted = false;
  private detached = false;
  private retryTimer: unknown = null;
  private readonly backoff = new Backoff(1000, 15_000);
  private readonly timers: Timers;
  private resizeTimers: unknown[] = [];
  status: DesktopStatus = "arrete";

  constructor(private readonly options: DesktopOptions) {
    this.timers = options.timers ?? realTimers;
    this.maximizeButton = options.onMaximize
      ? button("Agrandir", () => options.onMaximize?.(), { class: "small", attrs: { "aria-pressed": "false" } })
      : null;
    this.detachedNote = h(
      "div",
      { class: "desktop-detached", attrs: { hidden: "" } },
      h("p", { text: "Le bureau est ouvert dans une fenêtre séparée." }),
      button("Ramener ici", () => options.onReattach?.(), { class: "small" }),
    );
    this.screen.append(this.detachedNote);
    // Taille de l'écran changée (panneau agrandi, fenêtre séparée redimensionnée…) : on redemande la
    // taille du bureau une fois l'écran stabilisé (voir resyncSize).
    if (typeof ResizeObserver === "function") new ResizeObserver(() => this.resyncSize()).observe(this.screen);
    const fullscreen =
      typeof this.el.requestFullscreen === "function"
        ? button("Plein écran", () => void this.el.requestFullscreen().catch(() => undefined), { class: "small" })
        : null;
    this.el.append(
      h(
        "div",
        { class: "panel-header" },
        h("h2", { text: "Bureau" }),
        this.statusPill,
        h("span", { class: "spacer" }),
        this.maximizeButton,
        fullscreen,
        options.onDetach ? button("Fenêtre séparée", () => options.onDetach?.(), { class: "small" }) : null,
        button("Reconnecter", () => this.reconnect(), { class: "small" }),
      ),
      this.hint,
      this.screen,
    );
  }

  /** État du bouton « Agrandir » (l'agrandissement lui-même est fait par la page). */
  setMaximized(on: boolean): void {
    if (!this.maximizeButton) return;
    this.maximizeButton.setAttribute("aria-pressed", String(on));
    this.maximizeButton.textContent = on ? "Réduire" : "Agrandir";
  }

  get isDetached(): boolean {
    return this.detached;
  }

  /**
   * Bureau affiché dans une autre fenêtre : ce panneau lâche sa connexion (une seule fenêtre
   * fixe la taille de l'écran) et la reprend quand on le ramène.
   */
  setDetached(on: boolean): void {
    if (on === this.detached) return;
    this.detached = on;
    this.detachedNote.hidden = !on;
    if (on) {
      if (this.retryTimer !== null) this.timers.clearTimeout(this.retryTimer);
      this.retryTimer = null;
      this.closeRfb();
      this.setStatus("separe");
    } else {
      this.setStatus("arrete");
      if (this.visible) this.reconnect();
    }
  }

  get visible(): boolean {
    return !this.el.hidden;
  }

  /** Affiche le bureau et s'y connecte (le premier accès démarre l'écran virtuel). */
  show(): void {
    this.el.hidden = false;
    if (this.detached) return;
    this.wanted = true;
    if (this.rfb) this.rfb.focus();
    else if (this.retryTimer === null) void this.connect();
  }

  /** Masque le panneau ; la connexion reste ouverte pour retrouver les fenêtres telles quelles. */
  hide(): void {
    this.el.hidden = true;
  }

  reconnect(): void {
    if (this.detached) return;
    if (this.retryTimer !== null) this.timers.clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.closeRfb();
    this.backoff.reset();
    this.wanted = true;
    void this.connect();
  }

  dispose(): void {
    this.wanted = false;
    if (this.retryTimer !== null) this.timers.clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.closeRfb();
    this.setStatus("arrete");
  }

  private closeRfb(): void {
    const rfb = this.rfb;
    this.rfb = null;
    if (rfb) {
      try {
        rfb.disconnect();
      } catch {
        // déjà fermé
      }
    }
  }

  private async connect(): Promise<void> {
    this.retryTimer = null;
    if (this.detached) return;
    this.setStatus(this.status === "arrete" ? "connexion" : "reconnexion");
    let rfb: RfbLike;
    try {
      const factory = this.options.rfb ?? (await noVncFactory());
      const url = await this.options.url();
      if (this.detached || !this.wanted) return; // détaché ou arrêté pendant l'attente du jeton
      rfb = factory(this.screen, url);
    } catch (e) {
      console.warn("Bureau : connexion impossible", e);
      this.scheduleRetry();
      return;
    }
    rfb.scaleViewport = true; // l'écran tient dans le panneau
    rfb.resizeSession = true; // et le bureau prend la taille du panneau
    rfb.addEventListener("connect", () => {
      if (this.rfb !== rfb) return;
      this.backoff.reset();
      this.setStatus("connecte");
      this.resyncSize();
    });
    rfb.addEventListener("disconnect", () => {
      if (this.rfb !== rfb) return;
      this.rfb = null;
      this.scheduleRetry();
    });
    this.rfb = rfb;
  }

  /**
   * noVNC abandonne une demande de taille faite avant que le serveur ait annoncé qu'il sait changer de
   * taille, ou pendant qu'une autre demande attend sa réponse, sans la refaire ensuite : l'écran pouvait
   * rester à son ancienne taille. On la redemande donc un peu après chaque changement (sans effet si la
   * taille est déjà la bonne).
   */
  private resyncSize(): void {
    for (const t of this.resizeTimers) this.timers.clearTimeout(t);
    this.resizeTimers = [600, 2000, 5000].map((ms) =>
      this.timers.setTimeout(() => {
        if (this.rfb) this.rfb.resizeSession = true;
      }, ms),
    );
  }

  private scheduleRetry(): void {
    if (!this.wanted) {
      this.setStatus("arrete");
      return;
    }
    this.setStatus("reconnexion");
    this.retryTimer = this.timers.setTimeout(() => void this.connect(), this.backoff.next());
  }

  private setStatus(status: DesktopStatus): void {
    this.status = status;
    this.statusPill.textContent = STATUS_TEXT[status];
    this.statusPill.dataset.status = status;
  }
}
