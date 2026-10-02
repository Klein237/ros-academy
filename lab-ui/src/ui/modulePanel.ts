import type { ContentsClient } from "../api/contents";
import type { ModuleClient } from "../api/module";
import {
  academyDir,
  cleanOutput,
  exerciseDir,
  findExitCode,
  installExerciseFiles,
  labDir,
  resetLab,
  scriptCommand,
} from "../module";
import { button, h, toast } from "./dom";
import type { TerminalPanel } from "./terminals";

export interface ModulePanelOptions {
  moduleId: string;
  client: ModuleClient;
  contents: ContentsClient;
  terminals: TerminalPanel;
  /** Déplier ce dossier dans l'arborescence (et la rafraîchir). */
  reveal(path: string): Promise<void>;
  openExercise: boolean;
}

const nonce = () => Math.random().toString(36).slice(2, 10);

/** Le module du parcours : retour au cours, workspace du lab guidé, exercice avec bug. */
export class ModulePanel {
  readonly el = h("section", { class: "panel module-panel", attrs: { "aria-label": "Module" } });
  private readonly status = h("div", { class: "exercise-status", attrs: { role: "status", "aria-live": "polite" } });
  private readonly hints = h("div", { class: "hints" });
  private readonly startButton: HTMLButtonElement;
  private readonly checkButton: HTMLButtonElement;
  private readonly hintButton: HTMLButtonElement;
  private hintsShown = 0;
  private hintCount = 3;
  private busy = false;

  constructor(private readonly opts: ModulePanelOptions) {
    this.startButton = button("Commencer l'exercice", () => void this.startExercise(), { class: "primary" });
    this.checkButton = button("Vérifier", () => void this.check());
    this.hintButton = button("Indice 1", () => void this.nextHint());
  }

  async start(): Promise<void> {
    const id = this.opts.moduleId;
    const [info, exercise] = await Promise.all([this.opts.client.info(), this.opts.client.exercise()]);
    this.hintCount = exercise.indices;
    const enonce = h("div", { class: "enonce" });
    enonce.innerHTML = exercise.enonce_html; // HTML produit par le service Contenus (Markdown sans HTML brut)
    const details = h("details", { class: "exercise-details" }, h("summary", { text: "Énoncé de l'exercice" }), enonce);
    details.open = this.opts.openExercise;
    this.el.append(
      h("div", { class: "panel-header" },
        h("h2", { text: "Module" }),
        h("a", { class: "small", text: "Retour au cours", attrs: { href: `/modules/${encodeURIComponent(id)}/`, target: "_blank", rel: "noopener" } })),
      h("div", { class: "module-body" },
        h("p", { class: "module-title", text: info.titre }),
        h("p", { class: "muted small" }, "Lab guidé : ", h("code", { text: `~/${labDir(id)}` }), " ",
          button("Réinitialiser", () => void this.reset(), { class: "link", title: "Repartir du workspace de départ" })),
        h("h3", { text: "Exercice" }),
        details,
        h("div", { class: "exercise-actions" }, this.startButton, this.checkButton),
        this.status,
        h("div", { class: "hint-row" }, this.hintButton,
          h("span", { class: "muted small", text: "chaque indice retire 15 % de la note de l'exercice" })),
        this.hints,
      ),
    );
    this.hintButton.disabled = this.hintCount === 0;
  }

  private setBusy(busy: boolean): void {
    this.busy = busy;
    this.startButton.disabled = this.checkButton.disabled = busy;
  }

  private show(kind: "info" | "ok" | "ko", title: string, detail = ""): void {
    this.status.className = `exercise-status ${kind}`;
    this.status.replaceChildren(h("strong", { text: title }), detail ? h("pre", { text: detail }) : "");
  }

  private async startExercise(): Promise<void> {
    if (this.busy) return;
    const id = this.opts.moduleId;
    if ((await this.opts.contents.exists(exerciseDir(id))) &&
      !confirm(`Recommencer l'exercice ? Le dossier ~/${exerciseDir(id)} sera remplacé par la version de départ.`)) {
      return;
    }
    this.setBusy(true);
    this.show("info", "Installation de l'exercice…", "Le workspace est copié puis compilé : comptez jusqu'à une minute.");
    try {
      const exercise = await this.opts.client.exercise();
      await installExerciseFiles(this.opts.contents, id, exercise.files);
      const n = nonce();
      const { code, output } = await this.opts.terminals.run("Exercice", scriptCommand(id, "setup.sh", n),
        (out) => findExitCode(out, n));
      if (code === 0) {
        this.show("info", `Exercice prêt dans ~/${exerciseDir(id)}`,
          "Diagnostiquez la panne dans un terminal, corrigez-la, puis cliquez sur Vérifier.");
        await this.opts.reveal(exerciseDir(id));
      } else {
        this.show("ko", "L'installation de l'exercice a échoué", tail(cleanOutput(output, n)));
      }
    } catch {
      this.show("ko", "Impossible d'installer l'exercice", "Réessayez dans un instant.");
    } finally {
      this.setBusy(false);
    }
  }

  private async check(): Promise<void> {
    if (this.busy) return;
    const id = this.opts.moduleId;
    if (!(await this.opts.contents.exists(exerciseDir(id))) || !(await this.opts.contents.exists(`${academyDir(id)}/check.sh`))) {
      this.show("info", "Commencez d'abord l'exercice", "« Commencer l'exercice » installe le workspace avec la panne.");
      return;
    }
    this.setBusy(true);
    this.show("info", "Vérification en cours…");
    try {
      const n = nonce();
      const { code, output } = await this.opts.terminals.run("Vérification", scriptCommand(id, "check.sh", n),
        (out) => findExitCode(out, n));
      const text = tail(cleanOutput(output, n));
      if (code === 0) {
        this.show("ok", "Exercice réussi !", text);
        const explication = h("div", { class: "explication" });
        explication.innerHTML = await this.opts.client.explanation();
        this.status.append(h("h4", { text: "Explication" }), explication);
      } else {
        this.show("ko", code === null ? "La vérification n'a pas abouti" : "Pas encore : le problème est toujours là", text);
      }
    } catch {
      this.show("ko", "La vérification n'a pas pu être lancée", "Réessayez dans un instant.");
    } finally {
      this.setBusy(false);
    }
  }

  private async nextHint(): Promise<void> {
    const n = this.hintsShown + 1;
    if (n > this.hintCount) return;
    if (!confirm(`Afficher l'indice ${n} sur ${this.hintCount} ? Chaque indice utilisé retire 15 % de la note de l'exercice.`)) return;
    try {
      const block = h("div", { class: "hint" }, h("h4", { text: `Indice ${n}` }));
      const body = h("div");
      body.innerHTML = await this.opts.client.hint(n);
      block.append(body);
      this.hints.append(block);
      this.hintsShown = n;
      this.hintButton.textContent = n < this.hintCount ? `Indice ${n + 1}` : "Plus d'indice";
      this.hintButton.disabled = n >= this.hintCount;
    } catch {
      toast("Indice indisponible", "error");
    }
  }

  private async reset(): Promise<void> {
    const id = this.opts.moduleId;
    if (!confirm(`Réinitialiser le lab guidé ? Votre dossier ~/${labDir(id)} sera renommé (rien n'est supprimé), puis le workspace de départ sera réinstallé.`)) {
      return;
    }
    try {
      const backup = await resetLab(this.opts.contents, id, await this.opts.client.labFiles());
      toast(`Ancien dossier conservé : ~/${backup}`);
      await this.opts.reveal(labDir(id));
    } catch {
      toast("Réinitialisation impossible", "error");
    }
  }
}

/** Les dernières lignes d'une sortie, pour l'affichage. */
function tail(text: string, lines = 15): string {
  return text.split("\n").slice(-lines).join("\n");
}
