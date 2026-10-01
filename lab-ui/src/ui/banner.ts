import { button, h } from "./dom";

/** Bandeau d'avertissement avant l'arrêt pour inactivité. */
export class IdleBanner {
  readonly el = h("div", { class: "banner", attrs: { role: "alert" } });
  private readonly text = h("span");

  constructor(onStay: () => void) {
    this.el.hidden = true;
    this.el.append(this.text, button("Je suis là", onStay, { class: "primary" }));
  }

  show(remainingMs: number): void {
    const minutes = Math.max(1, Math.ceil(remainingMs / 60_000));
    this.text.textContent =
      remainingMs >= 60_000
        ? `Pas d'activité depuis un moment : le lab s'arrêtera dans ${minutes} min. Vos fichiers seront conservés.`
        : `Pas d'activité depuis un moment : le lab s'arrêtera dans ${Math.ceil(remainingMs / 1000)} s. Vos fichiers seront conservés.`;
    this.el.hidden = false;
  }

  hide(): void {
    this.el.hidden = true;
  }
}
