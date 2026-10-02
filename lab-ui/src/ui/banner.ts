import { button, h } from "./dom";

/** Bandeau d'avertissement avant l'arrêt pour inactivité. */
export class IdleBanner {
  readonly el = h("div", { class: "banner idle-banner", attrs: { role: "alert" } });
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

/** Bandeau des dernières minutes du quota mensuel. */
export class QuotaBanner {
  readonly el = h("div", { class: "banner quota-banner", attrs: { role: "status" } });

  constructor() {
    this.el.hidden = true;
  }

  update(minutesLeft: number | null): void {
    if (minutesLeft === null || minutesLeft > 5) {
      this.el.hidden = true;
      return;
    }
    this.el.replaceChildren(
      h("span", {
        text: `Il vous reste ${minutesLeft} min de lab ce mois-ci. À zéro, le lab s'arrête ; vos fichiers sont conservés.`,
      }),
      h("a", { text: "Mon compte", attrs: { href: "/compte/", target: "_blank", rel: "noopener" } }),
    );
    this.el.hidden = false;
  }
}
