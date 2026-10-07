/** Le lab complet : arborescence, éditeur, terminaux, bureau graphique, vue 2D, module du parcours. */
import { ComptesClient, NoAccount } from "./api/comptes";
import { ContentsClient } from "./api/contents";
import { HubClient } from "./api/hub";
import { ModuleClient } from "./api/module";
import { TerminalsClient } from "./api/terminals";
import { readConfig } from "./config";
import { ACTIVITY_EVENTS, IdleWatcher } from "./idle";
import { ensureCourseFile, exerciseDir, installLabWithRetry, labDir } from "./module";
import { normalizePath, parentOf } from "./paths";
import { RosbridgeClient } from "./ros/rosbridge";
import { Session } from "./session";
import { IdleBanner, QuotaBanner } from "./ui/banner";
import { DesktopPanel } from "./ui/desktop";
import { button, h, toast } from "./ui/dom";
import { EditorPanel } from "./ui/editor";
import { FileTree } from "./ui/files";
import { ModulePanel } from "./ui/modulePanel";
import { TerminalPanel } from "./ui/terminals";
import { View2D } from "./ui/view2d";
import { WaitingScreen } from "./ui/waiting";

const config = readConfig(location.search);
const hub = new HubClient();
const comptes = new ComptesClient();
const session = new Session(hub, { account: comptes });
const contents = new ContentsClient(hub);
const terminalsClient = new TerminalsClient(hub);
const moduleClient = config.moduleId ? new ModuleClient(config.moduleId) : null;

const app = document.getElementById("app")!;
const waiting = new WaitingScreen(() => void session.launch());
const banner = new IdleBanner(() => idle.activity());
const quota = new QuotaBanner();
const user = h("span", { class: "muted small" });
const stopButton = button("Arrêter le lab", () => {
  if (confirm("Arrêter le lab ? Vos fichiers sont conservés.")) void session.stop("user");
});
const show2d = button("Vue 2D", () => toggle2d(), { attrs: { "aria-pressed": "true" } });
const showDesktop = button("Bureau (RViz, Gazebo)", () => toggleDesktop(), { attrs: { "aria-pressed": "false" } });
// Lab à côté du cours (?integre=1) : place comptée, fichiers et panneau du module repliés au départ
if (config.embedded) document.body.classList.add("integre");
const showFiles = button("Fichiers", () => toggleFiles(), { attrs: { "aria-pressed": "true" } });
showFiles.hidden = !config.embedded;
if (config.embedded) show2d.textContent = config.moduleId ? "Module et vue 2D" : "Vue 2D";
const workspace = h("main", { class: "workspace" });
// Lab seul, ouvert depuis un module : chemin de retour visible vers le cours (même onglet)
const backToCourse = config.moduleId && !config.embedded
  ? h("a", { class: "back-course", text: "← Retour au cours", attrs: { href: `/modules/${encodeURIComponent(config.moduleId)}/` } })
  : null;
app.append(
  h(
    "header",
    { class: "topbar" },
    ...(backToCourse ? [backToCourse] : []),
    h("strong", { text: "Lab ROS 2" }),
    user,
    h("span", { class: "spacer" }),
    showFiles,
    showDesktop,
    show2d,
    stopButton,
  ),
  h("div", { class: "banners" }, banner.el, quota.el),
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
let current: {
  terminals: TerminalPanel;
  ros: RosbridgeClient;
  view: View2D;
  editor: EditorPanel;
  desktop: DesktopPanel;
} | null = null;
let openedFromUrl = false;

/** Demande du cours affiché à côté (voir handleCourseMessage), gardée tant que le lab démarre. */
interface CourseMessage {
  type?: string;
  path?: string;
  command?: string;
}
const pendingMessages: CourseMessage[] = [];


/** Le bureau graphique prend la place de l'éditeur (les terminaux restent dessous). */
function toggleDesktop(): void {
  if (!current) return;
  const show = !current.desktop.visible;
  if (show) current.desktop.show();
  else {
    current.desktop.hide();
    setDesktopMaximized(false);
  }
  current.editor.el.hidden = show;
  showDesktop.setAttribute("aria-pressed", String(show));
}

/** « Agrandir » : le bureau occupe tout l'espace de travail (sans fichiers, terminaux ni vue 2D). */
function setDesktopMaximized(on: boolean): void {
  workspace.classList.toggle("bureau-agrandi", on);
  current?.desktop.setMaximized(on);
}

/** « Fenêtre séparée » : le bureau dans sa propre fenêtre, déplaçable et redimensionnable. */
let desktopWindow: Window | null = null;
let desktopWindowTimer: number | null = null;

function detachDesktop(): void {
  if (!current) return;
  if (desktopWindow && !desktopWindow.closed) {
    desktopWindow.focus();
    return;
  }
  const opened = window.open(`${location.pathname}?vue=bureau`, "ros-academy-bureau", "popup,width=1280,height=820");
  if (!opened) {
    toast("La fenêtre a été bloquée : autorisez les fenêtres surgissantes pour ce site.", "error");
    return;
  }
  desktopWindow = opened;
  setDesktopMaximized(false);
  current.desktop.setDetached(true);
  // fenêtre fermée par l'étudiant : le bureau revient dans le lab
  desktopWindowTimer = window.setInterval(() => {
    if (desktopWindow?.closed) reattachDesktop();
  }, 1000);
}

function closeDesktopWindow(): void {
  if (desktopWindowTimer !== null) clearInterval(desktopWindowTimer);
  desktopWindowTimer = null;
  if (desktopWindow && !desktopWindow.closed) desktopWindow.close();
  desktopWindow = null;
}

function reattachDesktop(): void {
  closeDesktopWindow();
  current?.desktop.setDetached(false);
}

function toggleFiles(): void {
  const files = workspace.querySelector<HTMLElement>(".panel.files");
  if (!files) return;
  files.hidden = !files.hidden;
  showFiles.setAttribute("aria-pressed", String(!files.hidden));
}

function toggle2d(): void {
  const view = workspace.querySelector<HTMLElement>(".view2d");
  const side = workspace.querySelector<HTMLElement>(".side");
  if (!view || !side) return;
  if (config.embedded) {
    // intégré : le bouton replie tout le panneau (module et vue 2D) pour laisser la place à l'éditeur
    side.hidden = !side.hidden;
    show2d.setAttribute("aria-pressed", String(!side.hidden));
    return;
  }
  view.hidden = !view.hidden;
  side.hidden = view.hidden && !side.querySelector(".module-panel");
  show2d.setAttribute("aria-pressed", String(!view.hidden));
}

/** Module du parcours : copie lab/ si besoin ; renvoie le dossier de départ. */
async function prepareModule(): Promise<string> {
  if (!moduleClient || !config.moduleId) return "";
  const id = config.moduleId;
  try {
    const client = moduleClient;
    await installLabWithRetry(contents, id, () => client.labFiles());
  } catch (e) {
    console.warn(`Module ${id} non installé :`, e);
    // sans session de Comptes, le panneau du module invite à se reconnecter
    if (!(e instanceof NoAccount)) toast(`Le module ${id} n'a pas pu être chargé.`, "error");
    return "";
  }
  if (config.exercice && (await contents.exists(exerciseDir(id)).catch(() => false))) return exerciseDir(id);
  return labDir(id);
}

/** « Ouvrir dans le lab » : crée le fichier depuis le cours s'il n'existe pas encore. */
async function openFromCourse(editor: EditorPanel, path: string): Promise<void> {
  if (moduleClient && config.moduleId) {
    try {
      await ensureCourseFile(contents, config.moduleId, path, await moduleClient.courseFiles());
    } catch {
      // le fichier sera signalé absent par l'éditeur
    }
  }
  await editor.openFile(path);
}

async function startWorkspace(): Promise<void> {
  teardown();
  user.textContent = hub.user;
  const moduleFolder = await prepareModule();
  const cwd = config.folder && (await contents.exists(config.folder).catch(() => false)) ? config.folder : moduleFolder;
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
  const desktop = new DesktopPanel({
    url: () => hub.wsUrl("bureau/"),
    onMaximize: () => setDesktopMaximized(!workspace.classList.contains("bureau-agrandi")),
    onDetach: () => detachDesktop(),
    onReattach: () => reattachDesktop(),
  });
  const side = h("div", { class: "side" });
  if (moduleClient && config.moduleId) {
    const panel = new ModulePanel({
      moduleId: config.moduleId,
      client: moduleClient,
      comptes,
      saveAll: () => editor.saveAll(),
      contents,
      terminals,
      reveal: (path) => files.reveal(path),
      openExercise: config.exercice,
    });
    side.append(panel.el);
    panel.start().catch(() => toast("Le module n'a pas pu être chargé.", "error"));
  }
  side.append(view.el);
  workspace.replaceChildren(
    files.el,
    h(
      "div",
      { class: "center" },
      editor.el,
      desktop.el,
      h("div", { class: "splitter", attrs: { "aria-hidden": "true" } }),
      terminals.el,
    ),
    side,
  );
  setupSplitter(workspace.querySelector(".center")!);
  current = { terminals, ros, view, editor, desktop };
  showDesktop.setAttribute("aria-pressed", "false");
  setDesktopMaximized(false);
  if (config.embedded) {
    files.el.hidden = true;
    showFiles.setAttribute("aria-pressed", "false");
    side.hidden = !config.exercice; // l'exercice garde son panneau (Commencer, Vérifier, indices)
    show2d.setAttribute("aria-pressed", String(!side.hidden));
  }
  idle.start();
  watchQuota();
  await Promise.all([files.load(), terminals.restore().catch(() => undefined)]);
  void ros.connect();
  view.start();
  if (config.openPath && !openedFromUrl) {
    openedFromUrl = true;
    await openFromCourse(editor, config.openPath);
  } else {
    terminals.focus();
  }
  for (const message of pendingMessages.splice(0)) handleCourseMessage(message);
}

/** Minutes restantes, relues chaque minute : bandeau dans les 5 dernières. */
let quotaTimer: number | null = null;
function watchQuota(): void {
  const refresh = () =>
    comptes
      .me()
      .then((me) => quota.update(me.minutes_restantes))
      .catch(() => quota.update(null)); // lab ouvert sans compte : pas de quota affiché
  void refresh();
  quotaTimer = window.setInterval(refresh, 60_000);
}

function teardown(): void {
  idle.dispose();
  banner.hide();
  if (quotaTimer !== null) clearInterval(quotaTimer);
  quotaTimer = null;
  quota.update(null);
  if (!current) return;
  current.terminals.disposeAll();
  current.view.stop();
  current.ros.close();
  closeDesktopWindow();
  current.desktop.dispose();
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
  else if (state.kind === "stopped" || state.kind === "failed" || state.kind === "noauth" || state.kind === "quota") teardown();
});

// Une page de même origine (le site du cours, qui affiche le lab à côté, ou la fenêtre séparée du
// bureau) peut signaler une activité, demander l'ouverture d'un fichier (« Ouvrir dans le lab ») ou
// taper une commande du cours dans le terminal (« Lancer dans le lab »). Les demandes arrivées
// pendant le démarrage du lab sont traitées dès qu'il est prêt.

function handleCourseMessage(data: CourseMessage): void {
  if (!current) {
    const useful = data.type === "rosacademy:open" || data.type === "rosacademy:run";
    if (useful && pendingMessages.length < 10) pendingMessages.push(data);
    return;
  }
  if (data.type === "rosacademy:open" && typeof data.path === "string") {
    try {
      void openFromCourse(current.editor, normalizePath(data.path));
    } catch {
      // chemin refusé (..)
    }
  }
  if (data.type === "rosacademy:run" && typeof data.command === "string" && data.command.length <= 4000) {
    void current.terminals.type(data.command).catch(() => toast("Impossible d'ouvrir un terminal", "error"));
  }
}

window.addEventListener("message", (ev) => {
  if (ev.origin !== location.origin || typeof ev.data !== "object" || ev.data === null) return;
  const data = ev.data as CourseMessage;
  if (data.type === "rosacademy:activity") idle.activity();
  else handleCourseMessage(data);
});

window.addEventListener("beforeunload", (ev) => {
  if (current?.editor.docs.dirtyPaths().length) ev.preventDefault();
});

waiting.render(session.state);
void session.open();
