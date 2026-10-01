import "./style.css";
import { ContentsClient } from "./api/contents";
import { HubClient } from "./api/hub";
import { TerminalsClient } from "./api/terminals";
import { readConfig } from "./config";
import { ACTIVITY_EVENTS, IdleWatcher } from "./idle";
import { normalizePath, parentOf } from "./paths";
import { RosbridgeClient } from "./ros/rosbridge";
import { Session } from "./session";
import { IdleBanner } from "./ui/banner";
import { button, h } from "./ui/dom";
import { EditorPanel } from "./ui/editor";
import { FileTree } from "./ui/files";
import { TerminalPanel } from "./ui/terminals";
import { View2D } from "./ui/view2d";
import { WaitingScreen } from "./ui/waiting";

const config = readConfig(location.search);
const hub = new HubClient();
const session = new Session(hub);
const contents = new ContentsClient(hub);
const terminalsClient = new TerminalsClient(hub);

const app = document.getElementById("app")!;
const waiting = new WaitingScreen(() => void session.launch());
const banner = new IdleBanner(() => idle.activity());
const user = h("span", { class: "muted small" });
const stopButton = button("Arrêter le lab", () => {
  if (confirm("Arrêter le lab ? Vos fichiers sont conservés.")) void session.stop("user");
});
const show2d = button("Vue 2D", () => toggle2d(), { attrs: { "aria-pressed": "true" } });
const workspace = h("main", { class: "workspace" });
app.append(
  h(
    "header",
    { class: "topbar" },
    h("strong", { text: "Lab ROS 2" }),
    user,
    h("span", { class: "spacer" }),
    show2d,
    stopButton,
  ),
  banner.el,
  workspace,
  waiting.el,
);

const idle = new IdleWatcher({
  warnAfterMs: config.idleWarnMs,
  stopAfterMs: config.idleStopMs,
  onWarn: (remaining) => banner.show(remaining),
  onActive: () => banner.hide(),
  onStop: () => void session.stop("idle"),
});
for (const event of ACTIVITY_EVENTS) {
  window.addEventListener(event, () => idle.activity(), { capture: true, passive: true });
}

/** État de l'espace de travail, recréé à chaque démarrage du conteneur. */
let current: { terminals: TerminalPanel; ros: RosbridgeClient; view: View2D; editor: EditorPanel } | null = null;
let openedFromUrl = false;

function toggle2d(): void {
  const view = workspace.querySelector<HTMLElement>(".view2d");
  if (!view) return;
  view.hidden = !view.hidden;
  show2d.setAttribute("aria-pressed", String(!view.hidden));
}

async function startWorkspace(): Promise<void> {
  teardown();
  user.textContent = hub.user;
  const cwd = config.folder && (await contents.exists(config.folder).catch(() => false)) ? config.folder : "";
  const editor = new EditorPanel(contents);
  let refreshTimer: number | null = null;
  const files = new FileTree({
    client: contents,
    root: cwd || (config.openPath ? parentOf(config.openPath) : ""),
    onOpen: (path) => void editor.openFile(path),
    onDeleted: (path) => editor.closeDeleted(path),
  });
  const terminals = new TerminalPanel({
    client: terminalsClient,
    cwd,
    isServerAlive: () => session.checkAlive(),
    onCommand: () => {
      // les fichiers créés dans le terminal apparaissent peu après la commande
      if (refreshTimer !== null) clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => void files.refresh(), 1500);
    },
  });
  const ros = new RosbridgeClient({
    url: () => hub.wsUrl("rosbridge/"),
    onStatus: (status) => view.setStatus(status),
  });
  const view = new View2D(ros);
  workspace.replaceChildren(
    files.el,
    h("div", { class: "center" }, editor.el, h("div", { class: "splitter", attrs: { "aria-hidden": "true" } }), terminals.el),
    view.el,
  );
  setupSplitter(workspace.querySelector(".center")!);
  current = { terminals, ros, view, editor };
  idle.start();
  await Promise.all([files.load(), terminals.restore().catch(() => undefined)]);
  void ros.connect();
  view.start();
  if (config.openPath && !openedFromUrl) {
    openedFromUrl = true;
    await editor.openFile(config.openPath);
  } else {
    terminals.focus();
  }
}

function teardown(): void {
  idle.dispose();
  banner.hide();
  if (!current) return;
  current.terminals.disposeAll();
  current.view.stop();
  current.ros.close();
  current = null;
}

/** Glisser la barre entre éditeur et terminaux. */
function setupSplitter(center: HTMLElement): void {
  const splitter = center.querySelector<HTMLElement>(".splitter")!;
  splitter.addEventListener("pointerdown", (ev) => {
    splitter.setPointerCapture(ev.pointerId);
    const move = (e: PointerEvent) => {
      const rect = center.getBoundingClientRect();
      const ratio = Math.min(0.85, Math.max(0.15, (e.clientY - rect.top) / rect.height));
      center.style.gridTemplateRows = `${ratio}fr 6px ${1 - ratio}fr`;
    };
    const up = () => {
      splitter.removeEventListener("pointermove", move);
      splitter.removeEventListener("pointerup", up);
    };
    splitter.addEventListener("pointermove", move);
    splitter.addEventListener("pointerup", up);
  });
}

session.onChange((state) => {
  waiting.render(state);
  stopButton.disabled = state.kind !== "ready";
  if (state.kind === "ready") void startWorkspace();
  else if (state.kind === "stopped" || state.kind === "failed" || state.kind === "noauth") teardown();
});

// Une page parente de même origine (le site du cours) peut signaler une activité
// ou demander l'ouverture d'un fichier (« Ouvrir dans le lab »).
window.addEventListener("message", (ev) => {
  if (ev.origin !== location.origin || typeof ev.data !== "object" || ev.data === null) return;
  const data = ev.data as { type?: string; path?: string };
  if (data.type === "rosacademy:activity") idle.activity();
  if (data.type === "rosacademy:open" && typeof data.path === "string" && current) {
    try {
      void current.editor.openFile(normalizePath(data.path));
    } catch {
      // chemin refusé (..)
    }
  }
});

window.addEventListener("beforeunload", (ev) => {
  if (current?.editor.docs.dirtyPaths().length) ev.preventDefault();
});

waiting.render(session.state);
void session.open();
