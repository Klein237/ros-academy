import { HttpError } from "../api/hub";
import type { ContentsClient, Entry } from "../api/contents";
import { isValidName, joinPath, parentOf } from "../paths";
import { button, h, toast } from "./dom";

interface DirNode {
  path: string;
  expanded: boolean;
  children: HTMLElement;
  row: HTMLElement | null;
}

export interface FileTreeOptions {
  client: ContentsClient;
  root: string;
  onOpen(path: string): void;
  onDeleted?(path: string): void;
}

/** Arborescence de /home/etudiant, chargée dossier par dossier. */
export class FileTree {
  readonly el = h("aside", { class: "panel files", attrs: { "aria-label": "Fichiers" } });
  private readonly list = h("div", { class: "tree", attrs: { role: "tree" } });
  private readonly dirs = new Map<string, DirNode>();
  private selectedDir = "";
  private selectedRow: HTMLElement | null = null;

  constructor(private readonly opts: FileTreeOptions) {
    const actions = h(
      "div",
      { class: "panel-actions" },
      button("+ Fichier", () => this.prompt("file"), { title: "Nouveau fichier" }),
      button("+ Dossier", () => this.prompt("directory"), { title: "Nouveau dossier" }),
      button("⟳", () => void this.refresh(), { title: "Rafraîchir", attrs: { "aria-label": "Rafraîchir" } }),
    );
    this.el.append(h("div", { class: "panel-header" }, h("h2", { text: "Fichiers" })), actions, this.list);
    const root: DirNode = { path: "", expanded: true, children: this.list, row: null };
    this.dirs.set("", root);
  }

  /** Charge la racine et déplie le dossier de départ. */
  async load(): Promise<void> {
    await this.reveal(this.opts.root);
  }

  /** Recharge l'arborescence et déplie un dossier (création d'un exercice, réinitialisation…). */
  async reveal(path: string): Promise<void> {
    await this.loadDir(this.dirs.get("")!);
    let current = "";
    for (const part of path.split("/").filter(Boolean)) {
      current = joinPath(current, part);
      const node = this.dirs.get(current);
      if (!node) break;
      await this.expand(node);
    }
    if (this.dirs.has(path)) this.selectedDir = path;
  }

  private async loadDir(node: DirNode): Promise<void> {
    let entries: Entry[];
    try {
      entries = await this.opts.client.list(node.path);
    } catch {
      node.children.replaceChildren(h("div", { class: "tree-empty", text: "Dossier illisible" }));
      return;
    }
    const depth = node.path ? node.path.split("/").length : 0;
    const rows = entries
      .filter((e) => !e.name.startsWith("."))
      .map((e) => (e.type === "directory" ? this.dirRow(e, depth) : this.fileRow(e, depth)));
    node.children.replaceChildren(...(rows.length ? rows : [h("div", { class: "tree-empty", text: "Vide" })]));
  }

  private indent(depth: number): HTMLElement {
    const pad = h("span", { class: "indent" });
    pad.style.width = `${depth * 14}px`;
    return pad;
  }

  private dirRow(entry: Entry, depth: number): HTMLElement {
    const known = this.dirs.get(entry.path);
    const children = h("div", { class: "tree-children", attrs: { role: "group" } });
    const node: DirNode = { path: entry.path, expanded: false, children, row: null };
    const row = h(
      "div",
      {
        class: "tree-row dir",
        dataset: { path: entry.path },
        attrs: { role: "treeitem", "aria-expanded": "false", tabindex: "0" },
        on: {
          click: () => {
            this.select(row, entry.path);
            void (node.expanded ? this.collapse(node) : this.expand(node));
          },
          keydown: (ev) => {
            if (ev.key === "Enter") row.click();
          },
        },
      },
      this.indent(depth),
      h("span", { class: "twisty", text: "▸" }),
      h("span", { class: "name", text: entry.name }),
      this.deleteButton(entry),
    );
    node.row = row;
    this.dirs.set(entry.path, node);
    const wrap = h("div", {}, row, children);
    children.hidden = true;
    if (known?.expanded) void this.expand(node);
    return wrap;
  }

  private fileRow(entry: Entry, depth: number): HTMLElement {
    const row = h(
      "div",
      {
        class: "tree-row file",
        dataset: { path: entry.path },
        attrs: { role: "treeitem", tabindex: "0" },
        on: {
          click: () => {
            this.select(row, parentOf(entry.path));
            this.opts.onOpen(entry.path);
          },
          keydown: (ev) => {
            if (ev.key === "Enter") row.click();
          },
        },
      },
      this.indent(depth),
      h("span", { class: "twisty" }),
      h("span", { class: "name", text: entry.name }),
      this.deleteButton(entry),
    );
    return row;
  }

  private deleteButton(entry: Entry): HTMLElement {
    return button(
      "🗑",
      () => undefined,
      {
        class: "row-action",
        title: `Supprimer ${entry.name}`,
        attrs: { "aria-label": `Supprimer ${entry.name}` },
        on: {
          click: (ev) => {
            ev.stopPropagation();
            void this.remove(entry);
          },
        },
      },
    );
  }

  private select(row: HTMLElement, dir: string): void {
    this.selectedRow?.classList.remove("selected");
    row.classList.add("selected");
    this.selectedRow = row;
    this.selectedDir = dir;
  }

  private async expand(node: DirNode): Promise<void> {
    node.expanded = true;
    node.children.hidden = false;
    node.row?.setAttribute("aria-expanded", "true");
    node.row?.querySelector(".twisty")?.replaceChildren("▾");
    await this.loadDir(node);
  }

  private collapse(node: DirNode): void {
    node.expanded = false;
    node.children.hidden = true;
    node.row?.setAttribute("aria-expanded", "false");
    node.row?.querySelector(".twisty")?.replaceChildren("▸");
  }

  /** Recharge les dossiers dépliés (après une commande, une création…). */
  async refresh(): Promise<void> {
    const root = this.dirs.get("")!;
    await this.loadDir(root);
  }

  private prompt(kind: "file" | "directory"): void {
    const dir = this.selectedDir;
    const node = this.dirs.get(dir) ?? this.dirs.get("")!;
    if (!node.expanded) void this.expand(node);
    const input = h("input", {
      class: "tree-input",
      attrs: {
        "aria-label": kind === "file" ? "Nom du nouveau fichier" : "Nom du nouveau dossier",
        placeholder: kind === "file" ? "nom_du_fichier.py" : "nom_du_dossier",
        spellcheck: "false",
      },
    });
    let done = false;
    const finish = async (create: boolean) => {
      if (done) return;
      done = true;
      const name = input.value.trim();
      input.remove();
      if (!create || !name) return;
      if (!isValidName(name)) return toast("Nom invalide", "error");
      const path = joinPath(dir, name);
      try {
        if (kind === "file") await this.opts.client.createFile(path);
        else await this.opts.client.createDirectory(path);
      } catch (e) {
        return toast(e instanceof HttpError && e.status === 409 ? `${name} existe déjà` : "Création impossible", "error");
      }
      await this.loadDir(node);
      if (kind === "file") this.opts.onOpen(path);
    };
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") void finish(true);
      if (ev.key === "Escape") void finish(false);
    });
    input.addEventListener("blur", () => void finish(true));
    node.children.prepend(input);
    input.focus();
  }

  private async remove(entry: Entry): Promise<void> {
    const what = entry.type === "directory" ? "le dossier" : "le fichier";
    if (!confirm(`Supprimer ${what} ${entry.path} ?`)) return;
    try {
      await this.opts.client.remove(entry.path);
    } catch {
      return toast(
        entry.type === "directory" ? "Suppression impossible (le dossier n'est peut-être pas vide)" : "Suppression impossible",
        "error",
      );
    }
    this.opts.onDeleted?.(entry.path);
    const parent = this.dirs.get(parentOf(entry.path)) ?? this.dirs.get("")!;
    await this.loadDir(parent);
  }
}
