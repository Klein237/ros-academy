import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { TerminalConnection, type ConnectionStatus, type TerminalsClient } from "../api/terminals";
import { button, h, toast } from "./dom";

interface Tab {
  id: number;
  title: string;
  listeners: Set<(data: string) => void>;
  term: Terminal;
  fit: FitAddon;
  conn: TerminalConnection;
  host: HTMLElement;
  tab: HTMLElement;
  label: HTMLElement;
}

export interface TerminalPanelOptions {
  client: TerminalsClient;
  cwd: string;
  isServerAlive(): Promise<boolean>;
  /** Appelé après chaque commande lancée (Entrée) : rafraîchir l'arborescence. */
  onCommand?(): void;
}

/** Onglets de terminaux xterm.js reliés aux terminaux jupyter-server. */
export class TerminalPanel {
  readonly el = h("section", { class: "panel terminals", attrs: { "aria-label": "Terminaux" } });
  private readonly tabs = h("div", { class: "tabs", attrs: { role: "tablist" } });
  private readonly body = h("div", { class: "terminal-body" });
  private readonly open: Tab[] = [];
  private active: Tab | null = null;
  private seq = 0;
  private readonly resizeObserver = new ResizeObserver(() => this.fitActive());

  constructor(private readonly opts: TerminalPanelOptions) {
    const add = button("+", () => void this.add().catch(() => toast("Impossible d'ouvrir un terminal", "error")), {
      class: "tab-add",
      title: "Nouveau terminal",
      attrs: { "aria-label": "Nouveau terminal" },
    });
    this.el.append(h("div", { class: "panel-header" }, this.tabs, add), this.body);
    this.resizeObserver.observe(this.body);
  }

  /** Rattache les terminaux existants (page rechargée) ou en ouvre un. */
  async restore(): Promise<void> {
    const names = await this.opts.client.list().catch(() => [] as string[]);
    if (names.length === 0) {
      await this.add();
      return;
    }
    for (const name of names) this.attach(name);
  }

  async add(): Promise<void> {
    const name = await this.opts.client.create(this.opts.cwd);
    this.attach(name);
  }

  /**
   * Lance une commande dans un nouveau terminal (visible, pour que l'étudiant voie la sortie)
   * et attend le marqueur de fin ; `exitCode` lit le code de sortie dans la sortie.
   */
  async run(
    title: string,
    command: string,
    exitCode: (output: string) => number | null,
    timeoutMs = 15 * 60_000,
  ): Promise<{ code: number | null; output: string }> {
    // Un onglet par usage (« Exercice », « Vérification ») : réutilisé s'il est encore ouvert.
    let tab = this.open.find((t) => t.title === title && t.conn.status !== "closed");
    if (tab) this.show(tab);
    else tab = this.attach(await this.opts.client.create(""), title);
    const entry = tab;
    let output = "";
    return new Promise((resolve) => {
      const done = (code: number | null) => {
        entry.listeners.delete(listen);
        clearTimeout(timer);
        resolve({ code, output });
      };
      const listen = (data: string) => {
        output += data;
        const code = exitCode(output);
        if (code !== null) done(code);
      };
      const timer = setTimeout(() => done(null), timeoutMs);
      entry.listeners.add(listen);
      const send = () => {
        if (entry.conn.status === "open") entry.conn.send(`${command}\r`);
        else setTimeout(send, 200);
      };
      send();
    });
  }

  private attach(name: string, title?: string): Tab {
    const id = ++this.seq;
    const label0 = title ?? `Terminal ${id}`;
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: '"JetBrains Mono", "DejaVu Sans Mono", Menlo, Consolas, monospace',
      fontSize: 14,
      scrollback: 5000,
      theme: { background: "#0f141a", foreground: "#d8dee9", cursor: "#7fd4c1", selectionBackground: "#2f4a5a" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    const host = h("div", { class: "terminal-host", dataset: { terminal: String(id) } });
    this.body.append(host);
    term.open(host);
    const label = h("span", { text: label0 });
    const tab = h(
      "div",
      { class: "tab", attrs: { role: "tab" }, on: { click: () => this.show(entry) } },
      label,
      button("×", () => void this.closeTab(entry), { class: "tab-close", title: "Fermer ce terminal" }),
    );
    this.tabs.append(tab);
    const conn = new TerminalConnection({
      name,
      client: this.opts.client,
      cwd: this.opts.cwd,
      onData: (data) => {
        term.write(data);
        for (const l of entry.listeners) l(data);
      },
      onStatus: (status) => this.status(entry, status),
      onReplaced: () => term.write("\r\n\x1b[33m[ancien terminal fermé, nouveau terminal ouvert]\x1b[0m\r\n"),
      isServerAlive: this.opts.isServerAlive,
    });
    const entry: Tab = { id, title: label0, listeners: new Set(), term, fit, conn, host, tab, label };
    term.onData((data) => {
      conn.send(data);
      if (data.includes("\r")) this.opts.onCommand?.();
    });
    term.onResize(({ rows, cols }) => conn.resize(rows, cols));
    this.open.push(entry);
    this.show(entry);
    void conn.connect();
    return entry;
  }

  private status(tab: Tab, status: ConnectionStatus): void {
    tab.tab.dataset.status = status;
    tab.host.dataset.status = status;
    tab.label.textContent = status === "reconnecting" ? `${tab.title} · reconnexion…` : tab.title;
  }

  private show(tab: Tab): void {
    this.active = tab;
    for (const t of this.open) {
      const on = t === tab;
      t.host.hidden = !on;
      t.tab.classList.toggle("active", on);
      t.tab.setAttribute("aria-selected", String(on));
    }
    this.fitActive();
    tab.term.focus();
  }

  private fitActive(): void {
    if (!this.active || this.active.host.hidden) return;
    try {
      this.active.fit.fit();
      this.active.conn.resize(this.active.term.rows, this.active.term.cols);
    } catch {
      // panneau masqué ou de taille nulle
    }
  }

  private async closeTab(tab: Tab): Promise<void> {
    tab.conn.close();
    await this.opts.client.remove(tab.conn.name).catch(() => undefined);
    this.dispose(tab);
    if (this.active === tab) {
      this.active = null;
      const next = this.open[this.open.length - 1];
      if (next) this.show(next);
    }
  }

  private dispose(tab: Tab): void {
    tab.term.dispose();
    tab.host.remove();
    tab.tab.remove();
    this.open.splice(this.open.indexOf(tab), 1);
  }

  /** Conteneur arrêté : on ferme les connexions sans supprimer les terminaux. */
  disposeAll(): void {
    for (const tab of [...this.open]) {
      tab.conn.close();
      this.dispose(tab);
    }
    this.active = null;
  }

  focus(): void {
    this.active?.term.focus();
  }

  /**
   * Tape une commande dans le terminal actif, comme l'étudiant (« Lancer dans le lab » du cours) :
   * chaque ligne est validée par Entrée. Ouvre un terminal s'il n'y en a aucun.
   */
  async type(command: string): Promise<void> {
    if (!this.active) await this.add();
    const tab = this.active!;
    this.show(tab);
    const text = command.replace(/\r?\n/g, "\r").replace(/\r*$/, "\r");
    const send = (tries: number) => {
      if (tab.conn.status === "open") {
        tab.conn.send(text);
        this.opts.onCommand?.();
      } else if (tries > 0) setTimeout(() => send(tries - 1), 200);
    };
    send(50);
    tab.term.focus();
  }
}
