import type * as Monaco from "monaco-editor/editor/editor.api.js";
import { BinaryFile, FileTooLarge, NotFound, type ContentsClient } from "../api/contents";
import { OpenDocuments } from "../docs";
import { languageFor } from "../lang";
import { baseName } from "../paths";
import { button, h, toast } from "./dom";

type MonacoNS = typeof Monaco;

interface EditorTab {
  path: string;
  model: Monaco.editor.ITextModel;
  tab: HTMLElement;
  view: Monaco.editor.ICodeEditorViewState | null;
}

/** Onglets de fichiers ouverts dans Monaco, enregistrés par l'API fichiers. */
export class EditorPanel {
  readonly el = h("section", { class: "panel editor", attrs: { "aria-label": "Éditeur" } });
  readonly docs = new OpenDocuments();
  private readonly tabs = h("div", { class: "tabs", attrs: { role: "tablist" } });
  private readonly host = h("div", { class: "editor-host" });
  private readonly empty = h(
    "div",
    { class: "editor-empty" },
    h("p", { text: "Ouvrez un fichier dans l'arborescence, ou créez-en un avec « + Fichier »." }),
    h("p", { class: "muted small", text: "Ctrl+S pour enregistrer." }),
  );
  private monaco: MonacoNS | null = null;
  private editor: Monaco.editor.IStandaloneCodeEditor | null = null;
  private loading: Promise<MonacoNS> | null = null;
  private readonly open = new Map<string, EditorTab>();
  private readonly opening = new Set<string>();
  private active: EditorTab | null = null;

  constructor(private readonly client: ContentsClient) {
    this.el.append(h("div", { class: "panel-header" }, this.tabs), this.host, this.empty);
    this.host.hidden = true;
  }

  private async load(): Promise<MonacoNS> {
    this.loading ??= import("./monaco").then(({ monaco }) => {
      this.monaco = monaco;
      monaco.editor.defineTheme("lab", {
        base: "vs-dark",
        inherit: true,
        rules: [],
        colors: { "editor.background": "#0f141a" },
      });
      this.editor = monaco.editor.create(this.host, {
        theme: "lab",
        automaticLayout: true,
        fontSize: 14,
        minimap: { enabled: false },
        tabSize: 4,
        insertSpaces: true,
        renderWhitespace: "boundary",
        scrollBeyondLastLine: false,
      });
      this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => void this.save());
      return monaco;
    });
    return this.loading;
  }

  async openFile(path: string): Promise<void> {
    const already = this.open.get(path);
    if (already) return this.show(already);
    if (this.opening.has(path)) return; // double clic : un seul onglet
    this.opening.add(path);
    if (!this.monaco) this.empty.replaceChildren(h("p", { class: "muted", text: "Chargement de l'éditeur…" }));
    let text: string;
    try {
      [text] = await Promise.all([this.client.read(path), this.load()]);
    } catch (e) {
      this.opening.delete(path);
      this.resetEmpty();
      if (e instanceof FileTooLarge) return toast(`${baseName(path)} fait plus de 1 Mo : ouvrez-le dans le terminal.`, "error");
      if (e instanceof BinaryFile) return toast(`${baseName(path)} n'est pas un fichier texte.`, "error");
      if (e instanceof NotFound) return toast(`${path} n'existe pas.`, "error");
      return toast(`Impossible d'ouvrir ${baseName(path)}`, "error");
    }
    this.opening.delete(path);
    const monaco = this.monaco!;
    const uri = monaco.Uri.file(`/home/etudiant/${path}`);
    const model = monaco.editor.getModel(uri) ?? monaco.editor.createModel(text, languageFor(path), uri);
    model.setValue(text);
    model.updateOptions({ tabSize: languageFor(path) === "python" ? 4 : 2 });
    this.docs.open(path, text);
    const tab = h(
      "div",
      {
        class: "tab",
        title: path,
        dataset: { path },
        attrs: { role: "tab" },
        on: { click: () => this.show(entry) },
      },
      h("span", { class: "tab-name", text: baseName(path) }),
      h("span", { class: "dirty-dot", title: "Non enregistré", attrs: { "aria-label": "non enregistré" } }),
      button("×", () => this.close(entry), { class: "tab-close", title: "Fermer" }),
    );
    const entry: EditorTab = { path, model, tab, view: null };
    model.onDidChangeContent(() => {
      this.docs.update(path, model.getValue());
      this.markDirty(entry);
    });
    this.tabs.append(tab);
    this.open.set(path, entry);
    this.show(entry);
  }

  private resetEmpty(): void {
    this.empty.replaceChildren(
      h("p", { text: "Ouvrez un fichier dans l'arborescence, ou créez-en un avec « + Fichier »." }),
      h("p", { class: "muted small", text: "Ctrl+S pour enregistrer." }),
    );
  }

  private markDirty(entry: EditorTab): void {
    entry.tab.classList.toggle("dirty", this.docs.isDirty(entry.path));
  }

  private show(entry: EditorTab): void {
    if (!this.editor) return;
    if (this.active) this.active.view = this.editor.saveViewState();
    this.active = entry;
    this.editor.setModel(entry.model);
    if (entry.view) this.editor.restoreViewState(entry.view);
    for (const t of this.open.values()) {
      t.tab.classList.toggle("active", t === entry);
      t.tab.setAttribute("aria-selected", String(t === entry));
    }
    this.host.hidden = false;
    this.empty.hidden = true;
    this.editor.focus();
  }

  async save(entry: EditorTab | null = this.active): Promise<void> {
    if (!entry) return;
    const text = entry.model.getValue();
    try {
      await this.client.save(entry.path, text);
    } catch {
      return toast(`Échec de l'enregistrement de ${baseName(entry.path)}`, "error");
    }
    this.docs.markSaved(entry.path, text);
    this.docs.update(entry.path, entry.model.getValue());
    this.markDirty(entry);
    toast(`${baseName(entry.path)} enregistré`);
  }

  /** Enregistre tous les fichiers modifiés ; faux si l'un d'eux n'a pas pu l'être. */
  async saveAll(): Promise<boolean> {
    for (const entry of [...this.open.values()]) {
      if (this.docs.isDirty(entry.path)) await this.save(entry);
    }
    return this.docs.dirtyPaths().length === 0;
  }

  private close(entry: EditorTab): void {
    if (this.docs.isDirty(entry.path) && !confirm(`${baseName(entry.path)} n'est pas enregistré. Fermer quand même ?`)) {
      return;
    }
    this.forget(entry);
  }

  private forget(entry: EditorTab): void {
    entry.tab.remove();
    entry.model.dispose();
    this.docs.close(entry.path);
    this.open.delete(entry.path);
    if (this.active === entry) {
      this.active = null;
      const next = [...this.open.values()].pop();
      if (next) this.show(next);
      else {
        this.editor?.setModel(null);
        this.host.hidden = true;
        this.empty.hidden = false;
        this.resetEmpty();
      }
    }
  }

  /** Fichier ou dossier supprimé depuis l'arborescence. */
  closeDeleted(path: string): void {
    for (const entry of [...this.open.values()]) {
      if (entry.path === path || entry.path.startsWith(`${path}/`)) this.forget(entry);
    }
  }
}
