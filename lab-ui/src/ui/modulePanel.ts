import { ComptesError, NoAccount, reloginUrl, type ComptesClient } from "../api/comptes";
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
  /** Indices comptés, réussite enregistrée, explication après réussite. */
  comptes: Pick<ComptesClient, "exercise" | "hint" | "verify" | "explanation">;
  /** Enregistre les fichiers modifiés de l'éditeur (la vérification lit le workspace enregistré). */
  saveAll(): Promise<boolean>;
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
  private readonly account = h("p", { class: "account-note small", attrs: { hidden: "" } });
  private readonly startButton: HTMLButtonElement;
  private readonly checkButton: HTMLButtonElement;
  private readonly hintButton: HTMLButtonElement;
  private hintsShown = 0;
  private noAccount = false;
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
    const state = await this.opts.comptes.exercise(id).catch((e: unknown) => {
      if (e instanceof NoAccount) this.askLogin();
      return null;
    });
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
        this.account,
        this.status,
        h("div", { class: "hint-row" }, this.hintButton,
          h("span", { class: "muted small", text: "chaque indice retire 15 % de la note de l'exercice" })),
        this.hints,
      ),
    );
    this.hintButton.disabled = this.hintCount === 0;
    // Ouvert par « Ouvrir l'exercice dans le lab » : l'énoncé parle de ~/ws/<id>-exercice, il doit exister
    if (!(await this.opts.contents.exists(exerciseDir(id)).catch(() => true))) {
      if (this.opts.openExercise) void this.startExercise();
      else this.show("info", "Exercice pas encore installé", `« Commencer l'exercice » crée ~/${exerciseDir(id)} avec la panne à trouver.`);
    }
    if (!state) return;
    // retour sur le module : indices déjà vus (sans nouvelle pénalité) et réussite
    try {
      for (let n = 1; n <= Math.min(state.indices, this.hintCount); n++) await this.showHint(n);
    } catch {
      toast("Vos indices précédents n'ont pas pu être rechargés", "error");
    }
    if (state.reussi) {
      this.show("ok", "Exercice déjà réussi", "Votre réussite est enregistrée. Vous pouvez le refaire pour vous entraîner.");
      await this.appendExplanation();
    }
  }

  private askLogin(): void {
    this.noAccount = true;
    this.account.replaceChildren(
      "Vous n'êtes pas connecté : vos indices et votre réussite ne seront pas enregistrés. ",
      h("a", { text: "Se connecter", attrs: { href: reloginUrl() } }),
    );
    this.account.hidden = false;
  }

  private async appendExplanation(): Promise<void> {
    try {
      const explication = h("div", { class: "explication" });
      explication.innerHTML = await this.opts.comptes.explanation(this.opts.moduleId); // HTML produit par Contenus
      this.status.append(h("h4", { text: "Explication" }), explication);
    } catch {
      this.status.append(h("p", { class: "muted small", text: "L'explication n'a pas pu être chargée." }));
    }
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

  /**
   * « Vérifier » : le serveur lance le check.sh officiel sur le workspace enregistré, hors de
   * ce conteneur ; seule cette vérification compte pour la note. Sans compte, check.sh tourne
   * dans le terminal, à titre indicatif.
   */
  private async check(): Promise<void> {
    if (this.busy) return;
    const id = this.opts.moduleId;
    if (!(await this.opts.contents.exists(exerciseDir(id)))) {
      this.show("info", "Commencez d'abord l'exercice", "« Commencer l'exercice » installe le workspace avec la panne.");
      return;
    }
    this.setBusy(true);
    try {
      if (!(await this.opts.saveAll())) {
        this.show("ko", "Des fichiers n'ont pas pu être enregistrés", "Enregistrez-les (Ctrl+S) puis vérifiez à nouveau.");
        return;
      }
      if (this.noAccount) return await this.localCheck();
      this.show("info", "Vérification sur le serveur…",
        "Votre workspace enregistré est recompilé et testé à part, dans un environnement neuf : comptez jusqu'à une minute.");
      const r = await this.opts.comptes.verify(id);
      if (r.verification) {
        this.show("ok", "Exercice réussi !", tail(r.journal));
        await this.appendExplanation();
      } else {
        this.show("ko", "Pas encore : le problème est toujours là", tail(r.journal));
      }
    } catch (e) {
      if (e instanceof NoAccount) {
        this.askLogin();
        return await this.localCheck();
      }
      const status = e instanceof ComptesError ? e.status : 0;
      this.show("ko", status === 409 ? "Une vérification est déjà en cours" : status === 429
        ? "Le serveur de vérification est occupé" : "La vérification n'a pas pu être lancée", "Réessayez dans un instant.");
    } finally {
      this.setBusy(false);
    }
  }

  /** Sans compte : check.sh dans le terminal, résultat indicatif et non enregistré. */
  private async localCheck(): Promise<void> {
    const id = this.opts.moduleId;
    if (!(await this.opts.contents.exists(`${academyDir(id)}/check.sh`))) {
      this.show("info", "Commencez d'abord l'exercice", "« Commencer l'exercice » installe le workspace avec la panne.");
      return;
    }
    this.show("info", "Vérification en cours…");
    const n = nonce();
    const { code, output } = await this.opts.terminals.run("Vérification", scriptCommand(id, "check.sh", n),
      (out) => findExitCode(out, n));
    const text = tail(cleanOutput(output, n));
    if (code === 0) {
      this.show("ok", "Réussi ici, mais non enregistré", `${text}\n\nConnectez-vous : seule la vérification du serveur compte pour la note.`);
    } else {
      this.show("ko", code === null ? "La vérification n'a pas abouti" : "Pas encore : le problème est toujours là", text);
    }
  }

  private async nextHint(): Promise<void> {
    const n = this.hintsShown + 1;
    if (n > this.hintCount) return;
    if (!confirm(`Afficher l'indice ${n} sur ${this.hintCount} ? Chaque indice utilisé retire 15 % de la note de l'exercice.`)) return;
    try {
      await this.showHint(n);
    } catch (e) {
      if (e instanceof NoAccount) {
        this.askLogin();
        toast("Connectez-vous pour obtenir un indice", "error");
      } else {
        toast("Indice indisponible", "error");
      }
    }
  }

  private async showHint(n: number): Promise<void> {
    const html = await this.opts.comptes.hint(this.opts.moduleId, n);
    const body = h("div");
    body.innerHTML = html; // HTML produit par Contenus (Markdown sans HTML brut)
    this.hints.append(h("div", { class: "hint" }, h("h4", { text: `Indice ${n}` }), body));
    this.hintsShown = n;
    this.hintButton.textContent = n < this.hintCount ? `Indice ${n + 1}` : "Plus d'indice";
    this.hintButton.disabled = n >= this.hintCount;
  }

  private async reset(): Promise<void> {
    const id = this.opts.moduleId;
    if (!confirm(`Réinitialiser le lab guidé ? Votre dossier ~/${labDir(id)} sera mis de côté dans ~/ws/.anciens (rien n'est supprimé), puis le workspace de départ sera réinstallé.`)) {
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
