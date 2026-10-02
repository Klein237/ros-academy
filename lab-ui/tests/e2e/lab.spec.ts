import { execFileSync } from "node:child_process";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  activeTerminal,
  admin,
  cleanup,
  mint,
  newStudent,
  openLab,
  pasteInEditor,
  run,
  waitReady,
  watchErrors,
} from "./helpers";

let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

// En cas d'échec, la sortie du test montre ce que le navigateur a vu (jetons masqués).
const masked = (text: string) => text.replace(/token=[^&\s']+/g, "token=…");
test.beforeEach(async ({ page }) => {
  page.on("console", (m) => console.log(masked(`[navigateur ${m.type()}] ${m.text()}`)));
  page.on("pageerror", (e) => console.log(masked(`[navigateur pageerror] ${e.message}`)));
  page.on("requestfailed", (r) =>
    console.log(masked(`[navigateur requête échouée] ${r.method()} ${r.url()} ${r.failure()?.errorText}`)),
  );
  page.on("response", (r) => {
    if (r.status() >= 400) console.log(masked(`[navigateur HTTP ${r.status()}] ${r.request().method()} ${r.url()}`));
  });
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

function student(): string {
  const name = newStudent();
  students.push(name);
  return name;
}

test("écran d'attente puis terminal ROS fonctionnel", async ({ page }) => {
  const name = student();
  await page.goto(`/hub/jwt_login?token=${mint(name)}`);
  await expect(page).toHaveURL(/\/lab\/$/);
  await expect(page.locator(".overlay")).toBeVisible();
  await waitReady(page);
  await expect(page.locator(".topbar")).toContainText(name);
  await run(page, "echo resultat-$((6*7))", "resultat-42");
  // le JWT n'apparaît jamais dans l'URL ni dans l'historique de la page
  expect(page.url()).not.toContain("token=");
});

test("lien invalide ou session absente → retour au cours", async ({ page }) => {
  await page.goto("/lab/");
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "noauth");
  await expect(page.getByRole("link", { name: "Se reconnecter" })).toHaveAttribute("href", "/compte/lab?suite=%2Flab%2F");
});

test("créer un fichier dans l'éditeur, l'enregistrer, le lire dans le terminal", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const errors = watchErrors(page);
  const name = student();
  await openLab(page, name);
  await page.getByRole("button", { name: "+ Fichier" }).click();
  await page.getByLabel("Nom du nouveau fichier").fill("note.txt");
  await page.keyboard.press("Enter");
  await expect(page.locator(".editor .tab.active")).toContainText("note.txt");
  await pasteInEditor(page, "bonjour depuis l'éditeur\n");
  await expect(page.locator(".editor .tab.active")).toHaveClass(/dirty/);
  await page.keyboard.press("ControlOrMeta+S");
  await expect(page.locator(".editor .tab.active")).not.toHaveClass(/dirty/);
  await run(page, "cat ~/note.txt", "bonjour depuis l'éditeur");
  expect(errors).toEqual([]); // Monaco, xterm et les workers respectent la CSP
});

test("?open= ouvre un fichier existant (« Ouvrir dans le lab »)", async ({ page, context }) => {
  const name = student();
  // le serveur est démarré et le fichier créé avant l'ouverture du lab
  const login = await context.request.get(`/hub/jwt_login?token=${mint(name)}`, { maxRedirects: 0 });
  expect(login.status()).toBe(302);
  await api.post(`/hub/api/users/${name}/server`);
  await expect
    .poll(async () => (await (await api.get(`/hub/api/users/${name}`)).json()).servers?.[""]?.ready, { timeout: 180_000 })
    .toBe(true);
  for (const dir of ["ws", "ws/module-02"]) {
    await api.put(`/user/${name}/api/contents/${dir}`, { data: { type: "directory" } });
  }
  await api.put(`/user/${name}/api/contents/ws/module-02/talker.py`, {
    data: { type: "file", format: "text", content: "print('fichier du cours')\n" },
  });
  await page.goto("/lab/?open=ws/module-02/talker.py&dossier=ws/module-02");
  await waitReady(page);
  await expect(page.locator(".editor .tab.active")).toContainText("talker.py");
  await expect(page.locator(".monaco-editor")).toContainText("fichier du cours");
  await expect(page.locator('.tree-row[data-path="ws/module-02/talker.py"]')).toBeVisible();
  await run(page, "pwd", "/home/etudiant/ws/module-02");
});

test("coupure réseau → le terminal se reconnecte au même shell", async ({ page }) => {
  const name = student();
  await openLab(page, name);
  await run(page, "export MARQUE=avant-coupure");
  // redémarrer Caddy coupe toutes les connexions du navigateur
  execFileSync("docker", ["restart", process.env.CADDY_CONTAINER ?? "deploy-caddy-1"]);
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "reconnecting", { timeout: 30_000 });
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open", { timeout: 60_000 });
  await run(page, 'echo "marque=$MARQUE"', "marque=avant-coupure");
});

test("conteneur arrêté pendant la session → Relancer, fichiers conservés", async ({ page }) => {
  const name = student();
  await openLab(page, name);
  await run(page, "echo conserve > ~/persistant.txt && echo ok-ecrit", "ok-ecrit");
  await api.delete(`/hub/api/users/${name}/server`);
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "stopped", { timeout: 90_000 });
  await expect(page.getByText("Vos fichiers sont conservés.")).toBeVisible();
  await page.getByRole("button", { name: "Relancer le lab" }).click();
  await waitReady(page);
  await run(page, "cat ~/persistant.txt", "conserve");
});

test("inactivité : avertissement puis arrêt du lab", async ({ page }) => {
  const name = student();
  await openLab(page, name, "?inactivite=20");
  await expect(page.locator(".idle-banner")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".idle-banner")).toContainText("le lab s'arrêtera");
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "stopped", { timeout: 30_000 });
  await expect(page.getByText("inactivité")).toBeVisible();
  await expect
    .poll(async () => Object.keys((await (await api.get(`/hub/api/users/${name}`)).json()).servers ?? {}).length, {
      timeout: 60_000,
    })
    .toBe(0);
});

test("module Nœud : paquet, nœud écrit dans l'éditeur, build, run et echo @ros", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const name = student();
  await openLab(page, name);
  await run(
    page,
    `mkdir -p ~/ws/src && cd ~/ws/src && ros2 pkg create --build-type ament_python noeud_demo --node-name bavard >/dev/null && echo cree-""ok`,
    "cree-ok",
  );
  await page.getByRole("button", { name: "Rafraîchir" }).click();
  for (const path of ["ws", "ws/src", "ws/src/noeud_demo", "ws/src/noeud_demo/noeud_demo"]) {
    await page.locator(`.tree-row[data-path="${path}"]`).click();
  }
  await page.locator('.tree-row[data-path="ws/src/noeud_demo/noeud_demo/bavard.py"]').click();
  await expect(page.locator(".editor .tab.active")).toContainText("bavard.py");
  await pasteInEditor(
    page,
    [
      "import rclpy",
      "from rclpy.node import Node",
      "from std_msgs.msg import String",
      "",
      "",
      "class Bavard(Node):",
      "    def __init__(self):",
      "        super().__init__('bavard')",
      "        self.pub = self.create_publisher(String, 'bavardage', 10)",
      "        self.create_timer(0.5, self.parler)",
      "",
      "    def parler(self):",
      "        self.pub.publish(String(data='Bonjour ROS'))",
      "",
      "",
      "def main():",
      "    rclpy.init()",
      "    rclpy.spin(Bavard())",
      "",
      "",
      "if __name__ == '__main__':",
      "    main()",
      "",
    ].join("\n"),
  );
  await page.keyboard.press("ControlOrMeta+S");
  await expect(page.locator(".editor .tab.active")).not.toHaveClass(/dirty/);
  await run(
    page,
    "cd ~/ws && colcon build --packages-select noeud_demo 2>&1 | tail -1 && source install/setup.bash && ros2 run noeud_demo bavard &",
    /Summary: 1 package finished/,
    180_000,
  );
  await page.getByRole("button", { name: "Nouveau terminal" }).click();
  await expect(page.locator(".terminals .tab")).toHaveCount(2);
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  // avec le type, echo attend que le nœud lancé dans l'autre terminal soit découvert
  await run(page, "source ~/ws/install/setup.bash && ros2 topic echo --once /bavardage std_msgs/msg/String", "data: Bonjour ROS", 60_000);
});

test("vue 2D : le robot simulé avance avec la téléopération @ros", async ({ page }) => {
  const name = student();
  await openLab(page, name);
  await run(page, "academy-diffbot");
  const canvas = page.locator(".view-canvas");
  await expect(canvas).toHaveAttribute("data-x", /.+/, { timeout: 60_000 });
  const forward = page.getByRole("button", { name: "Avancer" });
  await forward.hover();
  await page.mouse.down();
  await page.waitForTimeout(2000);
  await page.mouse.up();
  await expect.poll(async () => Number(await canvas.getAttribute("data-x"))).toBeGreaterThan(0.2);
  await page.getByRole("button", { name: "Topics actifs" }).click();
  await expect(page.locator(".topic-list")).toContainText("/odom");
});

/** Couleurs de l'écran du bureau (canvas de noVNC), échantillonnées sur une grille. */
async function desktopColors(page: Page): Promise<string[]> {
  return page.locator(".desktop-screen canvas").evaluate((el) => {
    const canvas = el as HTMLCanvasElement;
    const ctx = canvas.getContext("2d");
    if (!ctx || canvas.width === 0) return [];
    const colors = new Set<string>();
    for (let gx = 1; gx < 20; gx++) {
      for (let gy = 1; gy < 20; gy++) {
        const [r, g, b] = ctx.getImageData(Math.floor((canvas.width * gx) / 20), Math.floor((canvas.height * gy) / 20), 1, 1).data;
        colors.add(`${r},${g},${b}`);
      }
    }
    return [...colors];
  });
}

async function openDesktop(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Bureau (RViz, Gazebo)" }).click();
  await expect(page.locator(".panel.editor")).toBeHidden(); // le bureau prend la place de l'éditeur
  await expect(page.locator(".desktop .pill")).toHaveText("connecté", { timeout: 60_000 });
}

test("bureau graphique : un programme du terminal s'affiche dans le bureau", async ({ page }) => {
  const name = student();
  const errors = watchErrors(page);
  await openLab(page, name);
  await openDesktop(page);
  // le terminal dessine sur l'écran du lab (DISPLAY=:1) : le fond du bureau devient rouge
  await run(page, "xsetroot -solid '#ff0000' && echo FOND-\"\"OK", "FOND-OK");
  await expect.poll(() => desktopColors(page), { timeout: 20_000 }).toEqual(["255,0,0"]);
  // retour à l'éditeur, puis au bureau : la même session est gardée
  await page.getByRole("button", { name: "Bureau (RViz, Gazebo)" }).click();
  await expect(page.locator(".panel.editor")).toBeVisible();
  await page.getByRole("button", { name: "Bureau (RViz, Gazebo)" }).click();
  await expect(page.locator(".desktop .pill")).toHaveText("connecté");
  expect(errors).toEqual([]);
});

test("bureau graphique : agrandi, puis dans une fenêtre séparée qui revient à sa fermeture", async ({ page }) => {
  const name = student();
  const errors = watchErrors(page);
  await openLab(page, name);
  await openDesktop(page);
  const files = page.locator(".panel.files");
  const terminals = page.locator(".panel.terminals");
  await page.getByRole("button", { name: "Agrandir" }).click();
  await expect(files).toBeHidden();
  await expect(terminals).toBeHidden();
  await page.getByRole("button", { name: "Réduire" }).click();
  await expect(files).toBeVisible();
  await expect(terminals).toBeVisible();
  // fenêtre séparée : elle se connecte, le lab lâche sa connexion
  const [popup] = await Promise.all([
    page.waitForEvent("popup"),
    page.getByRole("button", { name: "Fenêtre séparée" }).click(),
  ]);
  await expect(popup.locator(".desktop .pill")).toHaveText("connecté", { timeout: 60_000 });
  await expect(page.locator(".desktop .pill")).toHaveText("dans une fenêtre séparée");
  await expect(page.locator(".desktop-detached")).toBeVisible();
  // la fenêtre séparée suit sa taille : l'écran du lab prend les dimensions de la fenêtre
  await popup.setViewportSize({ width: 900, height: 600 });
  await expect.poll(() => popup.locator(".desktop-screen canvas").evaluate((c) => (c as HTMLCanvasElement).width), {
    timeout: 20_000,
  }).toBeLessThan(1000);
  await popup.close();
  await expect(page.locator(".desktop .pill")).toHaveText("connecté", { timeout: 30_000 });
  await expect(page.locator(".desktop-detached")).toBeHidden();
  expect(errors).toEqual([]);
});

test("bureau graphique : RViz2 s'ouvre avec le rendu logiciel @ros @rviz", async ({ page }) => {
  const name = student();
  await openLab(page, name);
  await openDesktop(page);
  await run(page, "xsetroot -solid '#1b1f24'; rviz2 > /tmp/rviz.log 2>&1 &");
  // une fenêtre RViz dessinée : bien plus de couleurs que le fond uni du bureau
  await expect.poll(async () => (await desktopColors(page)).length, { timeout: 90_000 }).toBeGreaterThan(8);
  await run(page, "pgrep -x rviz2 >/dev/null && echo RVIZ-\"\"VIVANT", "RVIZ-VIVANT");
});

test("serveur plein → écran d'attente avec nouvel essai @limit", async ({ page }) => {
  // ACTIVE_SERVER_LIMIT=2 : deux étudiants occupent les places
  for (let i = 0; i < 2; i++) {
    const other = student();
    await page.request.get(`/hub/jwt_login?token=${mint(other)}`, { maxRedirects: 0 });
    await api.post(`/hub/api/users/${other}/server`);
  }
  for (const other of [...students]) {
    await expect
      .poll(async () => (await (await api.get(`/hub/api/users/${other}`)).json()).servers?.[""]?.ready, { timeout: 180_000 })
      .toBe(true);
  }
  const name = student();
  await page.context().clearCookies();
  await page.goto(`/hub/jwt_login?token=${mint(name)}`);
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "full", { timeout: 60_000 });
  await expect(page.getByText("Le serveur est plein pour le moment")).toBeVisible();
  // une place se libère : le lab démarre sans action de l'étudiant
  await cleanup(api, students.shift()!);
  await waitReady(page);
});
