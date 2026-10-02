import { execFileSync } from "node:child_process";
import { expect, test, type APIRequestContext } from "@playwright/test";
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
  await run(page, "source ~/ws/install/setup.bash && ros2 topic echo --once /bavardage", "data: Bonjour ROS", 60_000);
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
