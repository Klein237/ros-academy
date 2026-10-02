/**
 * « Fenêtre séparée » du bureau graphique (?vue=bureau) : seulement l'écran du lab, dans une
 * fenêtre que l'étudiant déplace et redimensionne (le bureau prend sa taille). Le lab qui l'a
 * ouverte garde le contrôle de l'inactivité : cette fenêtre lui signale l'activité.
 */
import { ComptesClient } from "./api/comptes";
import { HubClient } from "./api/hub";
import { ACTIVITY_EVENTS } from "./idle";
import { Session } from "./session";
import { DesktopPanel } from "./ui/desktop";
import { h } from "./ui/dom";
import { WaitingScreen } from "./ui/waiting";

const hub = new HubClient();
const session = new Session(hub, { account: new ComptesClient() });
const app = document.getElementById("app")!;
const waiting = new WaitingScreen(() => void session.launch());
const page = h("main", { class: "bureau-seul" });
app.append(page, waiting.el);
document.title = "Bureau — Lab ROS 2";

let desktop: DesktopPanel | null = null;

function signalActivity(): void {
  try {
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({ type: "rosacademy:activity" }, location.origin);
    }
  } catch {
    // fenêtre du lab fermée ou d'une autre origine
  }
}

let lastSignal = 0;
for (const event of ACTIVITY_EVENTS) {
  window.addEventListener(
    event,
    () => {
      const now = Date.now();
      if (now - lastSignal < 5000) return; // inutile d'en envoyer plus
      lastSignal = now;
      signalActivity();
    },
    { capture: true, passive: true },
  );
}

session.onChange((state) => {
  waiting.render(state);
  if (state.kind === "ready") {
    desktop?.dispose();
    desktop = new DesktopPanel({ url: () => hub.wsUrl("bureau/") });
    page.replaceChildren(desktop.el);
    desktop.show();
  } else if (state.kind === "stopped" || state.kind === "failed" || state.kind === "noauth" || state.kind === "quota") {
    desktop?.dispose();
    desktop = null;
  }
});

waiting.render(session.state);
void session.open();
