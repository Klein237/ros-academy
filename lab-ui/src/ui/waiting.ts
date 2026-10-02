import type { SessionState } from "../session";
import { button, h } from "./dom";

const STOPPED_TEXT = {
  idle: "Le lab s'est arrêté après 20 minutes d'inactivité.",
  external: "Le lab s'est arrêté.",
  user: "Vous avez arrêté le lab.",
} as const;

/** Écran plein qui couvre l'espace de travail tant que le conteneur n'est pas prêt. */
export class WaitingScreen {
  readonly el = h("div", { class: "overlay", attrs: { role: "dialog", "aria-live": "polite" } });
  private countdown: number | null = null;

  constructor(private readonly onRetry: () => void) {}

  render(state: SessionState): void {
    if (this.countdown !== null) clearInterval(this.countdown);
    this.countdown = null;
    this.el.hidden = state.kind === "ready";
    this.el.dataset.state = state.kind;
    const card = h("div", { class: "overlay-card" });
    switch (state.kind) {
      case "auth":
        card.append(h("h1", { text: "Connexion au lab…" }), spinner());
        break;
      case "starting":
        card.append(
          h("h1", { text: "Préparation de votre environnement ROS 2" }),
          progressBar(state.progress),
          h("p", { class: "muted", text: state.message }),
          h("p", { class: "muted small", text: "Cela prend en général 10 à 30 secondes." }),
        );
        break;
      case "full": {
        const left = h("span", { text: String(Math.round(state.retryInMs / 1000)) });
        let seconds = Math.round(state.retryInMs / 1000);
        this.countdown = window.setInterval(() => {
          seconds = Math.max(0, seconds - 1);
          left.textContent = String(seconds);
        }, 1000);
        card.append(
          h("h1", { text: "Le serveur est plein pour le moment" }),
          h("p", { text: "Trop d'étudiants travaillent en même temps. Votre place se libère dès qu'un lab s'arrête." }),
          h("p", { class: "muted" }, "Nouvel essai automatique dans ", left, " s."),
          button("Réessayer maintenant", this.onRetry, { class: "primary" }),
        );
        break;
      }
      case "failed":
        card.append(
          h("h1", { text: "Le lab n'a pas pu démarrer" }),
          h("p", { text: state.message }),
          h("p", { class: "muted", text: "Vos fichiers sont conservés." }),
          button("Relancer", this.onRetry, { class: "primary" }),
        );
        break;
      case "stopped":
        card.append(
          h("h1", { text: STOPPED_TEXT[state.reason] }),
          h("p", { class: "muted", text: "Vos fichiers sont conservés." }),
          button("Relancer le lab", this.onRetry, { class: "primary" }),
        );
        break;
      case "noauth":
        card.append(
          h("h1", { text: "Session expirée" }),
          h("p", { text: "Le lien n'est plus valide. Rouvrez le lab depuis la page du cours." }),
          h("a", { class: "button primary", text: "Retour au cours", attrs: { href: "/" } }),
        );
        break;
      case "ready":
        break;
    }
    this.el.replaceChildren(card);
  }
}

function spinner(): HTMLElement {
  return h("div", { class: "spinner", attrs: { "aria-hidden": "true" } });
}

function progressBar(value: number): HTMLElement {
  const bar = h("div", { class: "progress", attrs: { role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100" } });
  const pct = Math.max(5, Math.min(100, value));
  bar.setAttribute("aria-valuenow", String(Math.round(pct)));
  const fill = h("div", { class: "progress-fill" });
  fill.style.width = `${pct}%`;
  bar.append(fill);
  return bar;
}
