import { expect, test, type APIRequestContext } from "./fixtures";
import {
  activeTerminal,
  admin,
  cleanup,
  loginStudent,
  mint,
  mintAdmin,
  newEmail,
  openLabViaAccount,
  run,
  waitReady,
  watchErrors,
} from "./helpers";

let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
});

test("sans connexion : catalogue, Découvrir ROS 2 et titres des modules, mais pas le cours", async ({ page }) => {
  await page.goto("/parcours/ros2-fondamentaux/");
  await expect(page.locator(".programme")).toContainText("Écrire un nœud");
  await page.locator(".programme").getByRole("link", { name: "Découvrir ROS 2" }).click();
  await expect(page.locator("h1")).toContainText("ROS");
  await page.goBack();
  await page.locator(".programme").getByRole("link", { name: "Écrire un nœud" }).click();
  await expect(page.getByRole("heading", { name: "Cours réservé aux inscrits" })).toBeVisible();
  await expect(page.locator(".module-reserve")).toContainText("Au programme");
  await expect(page.locator(".cours, .code-tabs, #qcm")).toHaveCount(0);
  // l'en-tête d'identité posé par Caddy ne se forge pas depuis le navigateur
  for (const path of ["/modules/05-noeud/", "/api/contenus/modules/05-noeud/exercice", "/api/contenus/modules/05-noeud/lab"]) {
    const r = await page.request.get(path, { headers: { "X-Academy-Etudiant": "1" } });
    expect(await r.text(), path).not.toContain("class DiffDriveNode");
    if (path.startsWith("/api/")) expect(r.status(), path).toBe(401);
  }
  // « Se connecter » ramène au module
  await page.getByRole("link", { name: "Créer un compte" }).click();
  await expect(page).toHaveURL(/\/connexion\/inscription\?suite=\/modules\/05-noeud\/$/);
});

test("le site présente le parcours et corrige le QCM sans exposer les réponses", async ({ page }) => {
  await loginStudent(page, newEmail());
  await page.goto("/");
  await page.getByRole("link", { name: "ROS 2 Fondamentaux" }).click();
  await expect(page.locator("h1")).toHaveText("ROS 2 Fondamentaux");
  await page.getByRole("link", { name: "Écrire un nœud" }).click();
  await expect(page.locator(".code-tabs .tab-bar button")).toHaveText(["Python", "C++"]);
  const html = await page.content();
  expect(html).not.toMatch(/correct["':=]/); // ni attribut ni donnée « correct » dans la page
  // les choix sont affichés dans un ordre mélangé ; la valeur reste le rang dans qcm.yaml (0 : la bonne réponse)
  await page.locator('input[name="spin"][value="0"]').check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.locator(".qcm-result")).toContainText("/ 20");
  await expect(page.locator('fieldset[data-question="spin"] .feedback')).toContainText("Juste");
});

test("module de cours : schémas, pas d'exercice, le QCM fait la note", async ({ page }) => {
  students.push(await loginStudent(page, newEmail(), "/modules/01-robot-mobile/"));
  await page.goto("/modules/01-robot-mobile/");
  await expect(page.locator("h1")).toHaveText("Le robot mobile");
  await expect(page.locator(".etapes-module [data-etape]")).toHaveText(["Cours", "QCM"]);
  await expect(page.locator("#exercice")).toHaveCount(0);
  await expect(page.locator("#qcm")).toContainText("ce module de cours n'a pas d'exercice");
  // les schémas passent par Caddy, réservés comme le cours, et s'affichent vraiment
  const schemas = page.locator(".cours img.schema");
  await expect(schemas).toHaveCount(5);
  for (const img of await schemas.all()) {
    await img.scrollIntoViewIfNeeded();
    await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true);
  }
  const src = await schemas.first().getAttribute("src");
  const anonyme = await page.context().browser()!.newContext({ ignoreHTTPSErrors: true });
  expect((await anonyme.request.get(new URL(src!, page.url()).href)).status()).toBe(404);
  await anonyme.close();
  // parcours : la partie « Les bases » et le module de cours signalé
  await page.goto("/parcours/ros2-fondamentaux/");
  await expect(page.locator(".programme li.partie").first()).toHaveText("Les bases");
  await expect(page.locator('.programme li[data-module="01-robot-mobile"]')).toContainText("cours et QCM");
});

test("module Linux : l'exercice se corrige dans le terminal et le serveur le vérifie @ros", async ({ page }) => {
  students.push(await loginStudent(page, newEmail()));
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.goto("/modules/02-linux/");
  await page.getByRole("link", { name: "Ouvrir l'exercice dans le lab" }).click();
  await waitReady(page);
  const panel = page.locator(".module-panel");
  await expect(panel.locator(".exercise-status")).toContainText("Exercice prêt", { timeout: 180_000 });
  // le lab guidé du module (fichiers d'entraînement) est installé
  await expect(page.locator('.tree-row[data-path="ws/02-linux"]')).toBeVisible();
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 180_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Permission denied");
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, "cd ~/ws/02-linux-exercice && chmod +x demarrer_robot.sh && ./demarrer_robot.sh", "robot.env introuvable");
  await run(page, `cp config/robot.env.exemple config/robot.env && sed -i 's/a-changer/livreur-01/' config/robot.env && ./demarrer_robot.sh`,
    "Robot livreur-01 prêt");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice réussi", { timeout: 180_000 });
  await expect(panel.locator(".explication")).toContainText("droit d'exécution");
});

test("module Nœud : « Ouvrir dans le lab » crée le fichier du cours sans jamais l'écraser", async ({ page }) => {
  // le cours est réservé aux étudiants connectés : le lab passe par la session de Comptes
  students.push(await loginStudent(page, newEmail()));
  const file = "ws/05-noeud/src/my_pkg/my_pkg/diff_drive_node.py";
  await openLabViaAccount(page, `?module=05-noeud&open=${encodeURIComponent(file)}`);
  await expect(page.locator(".editor .tab.active")).toContainText("diff_drive_node.py");
  await expect(page.locator(".monaco-editor")).toContainText("class DiffDriveNode");
  // lab seul ouvert depuis un module : retour au cours visible, dans le même onglet
  await expect(page.getByRole("link", { name: "← Retour au cours" })).toHaveAttribute("href", "/modules/05-noeud/");
  await expect(page.locator('.tree-row[data-path="ws/05-noeud/src"]')).toBeVisible(); // lab/ installé et déplié
  // en tête de fichier : Monaco n'affiche que les lignes visibles
  await run(page, `sed -i '1i # ma modification' ~/${file} && echo ok-""modifie`, "ok-modifie");
  await page.reload();
  await waitReady(page);
  await expect(page.locator(".monaco-editor")).toContainText("# ma modification");
});

test("module Nœud : l'exercice se fait entièrement dans le lab @ros", async ({ page }) => {
  students.push(await loginStudent(page, newEmail()));
  // comme le bouton « Ouvrir l'exercice dans le lab » du site, sur un écran étroit : le lab seul
  // (sur écran large, il s'ouvre à côté du cours : voir le test « Cours + lab »)
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.goto("/modules/05-noeud/");
  await page.getByRole("link", { name: "Ouvrir l'exercice dans le lab" }).click();
  await expect(page).toHaveURL(/\/lab\/\?module=05-noeud&exercice=1$/);
  await waitReady(page);
  const panel = page.locator(".module-panel");
  await expect(panel).toContainText("Écrire un nœud");
  await expect(panel.locator(".enonce")).toContainText("Le robot reste immobile");
  // ouvert par « Ouvrir l'exercice dans le lab » : l'exercice s'installe tout seul (~/ws/05-noeud-exercice)
  await expect(panel.locator(".exercise-status")).toContainText("Exercice prêt", { timeout: 180_000 });
  await expect(page.locator('.tree-row[data-path="ws/05-noeud-exercice"]')).toBeVisible();

  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 180_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Le robot n'avance pas");

  await panel.getByRole("button", { name: "Indice 1" }).click();
  await expect(panel.locator(".hint")).toContainText("ros2 node info");

  // tricher sur check.sh ne sert à rien : le serveur lance le check.sh publié, hors du conteneur
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, `printf '#!/bin/bash\\nexit 0\\n' > ~/.academy/05-noeud/check.sh && echo triche-""ok`, "triche-ok");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 180_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Le robot n'avance pas");

  // la correction, comme un étudiant la ferait dans un terminal
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, `sed -i 's/cmd_vell/cmd_vel/' ~/ws/05-noeud-exercice/src/my_pkg/my_pkg/diff_drive_node.py && echo corrige-""ok`, "corrige-ok");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice réussi", { timeout: 180_000 });
  await expect(panel.locator(".explication")).toContainText("cmd_vell");

  // réussite et indice enregistrés : retrouvés en rouvrant le lab, comptés dans les résultats
  await openLabViaAccount(page, "?module=05-noeud");
  await expect(panel.locator(".hint")).toHaveCount(1);
  await expect(panel.locator(".exercise-status")).toContainText("Exercice déjà réussi");
  await expect(panel.locator(".explication")).toContainText("cmd_vell");
  await page.goto("/compte/resultats");
  await expect(page.getByRole("row", { name: /Écrire un nœud/ })).toContainText("réussi (1 indice) · 17,0");
});

test("Cours + lab : le lab à côté du cours lance les commandes et ouvre les fichiers @ros", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  const errors = watchErrors(page);
  students.push(await loginStudent(page, newEmail()));
  await page.goto("/modules/05-noeud/");
  await expect(page.locator(".code-run").first()).toBeHidden(); // sans le lab à côté : pas de bouton
  // écran large : « Ouvrir le lab » ouvre le lab à côté du cours ; le lab seul reste proposé à part
  await expect(page.getByRole("link", { name: "Lab en plein écran" })).toHaveAttribute("target", "_blank");
  await page.getByRole("button", { name: "Ouvrir le lab" }).click();
  const lab = page.frameLocator(".lab-dock iframe");
  await expect(lab.locator(".overlay")).toBeHidden({ timeout: 180_000 });
  const term = lab.locator(".terminal-host:not([hidden])");
  await expect(term).toHaveAttribute("data-status", "open", { timeout: 60_000 });
  await expect(lab.locator(".panel.files")).toBeHidden(); // intégré : fichiers repliés au départ
  // « Lancer dans le lab » : le premier bloc de commandes (création des paquets) s'exécute dans le terminal
  await page.locator(".code-run").first().click();
  await expect(term.locator(".xterm-rows")).toContainText("ros2 pkg create my_pkg_cpp", { timeout: 30_000 });
  // exécuté ligne par ligne : le « cd » a changé de dossier (les paquets existent déjà : lab guidé installé)
  await expect(term.locator(".xterm-rows")).toContainText("/ws/05-noeud/src$", { timeout: 60_000 });
  // envoyée après l'invite : la commande n'est pas affichée une première fois avant elle
  const rows = (await term.locator(".xterm-rows").innerText()).split("\n");
  const cdRows = rows.filter((row) => row.includes("cd ~/ws/05-noeud/src"));
  expect(cdRows).toHaveLength(1);
  expect(cdRows[0]).toMatch(/\$ cd ~\/ws\/05-noeud\/src/);
  // « Ouvrir dans le lab » : le fichier du cours s'ouvre dans l'éditeur du panneau, la page ne change pas
  await page.locator('a.code-open[data-open$="diff_drive_node.py"]').first().click();
  await expect(page).toHaveURL(/\/modules\/05-noeud\/$/);
  await expect(lab.locator(".editor .tab.active")).toContainText("diff_drive_node.py");
  // le choix est retenu d'une page à l'autre ; « Masquer le lab » referme le panneau
  await page.reload();
  await expect(page.locator(".lab-dock iframe")).toBeVisible();
  await page.getByRole("button", { name: "Masquer le lab" }).click();
  await expect(page.locator(".lab-dock")).toHaveCount(0);
  await expect(page.locator(".code-run").first()).toBeHidden();
  expect(errors).toEqual([]);
});

test("l'administrateur modifie un module et le publie après les tests", async ({ page }) => {
  test.setTimeout(600_000);
  const marque = `Introduction — édition ${Date.now()}`;
  await page.goto(`/admin/login?token=${mintAdmin()}`);
  await expect(page.locator("h1")).toHaveText("Formations");
  await page.locator("#modules").getByRole("row", { name: /04-workspace/ }).getByRole("link", { name: "Éditer" }).click();
  const area = page.locator("#contenu");
  await expect(area).toHaveValue(/titre: Organiser son code/);
  const text = await area.inputValue();
  // le titre « # » de tête n'est pas affiché (la page montre celui de l'en-tête) : on modifie une section
  await area.fill(text.replace(/^## 1\. .*$/m, `## 1. ${marque}`));
  await page.keyboard.press("ControlOrMeta+S");
  await expect(page.locator("#etat-fichier")).toHaveText("Enregistré");
  await expect(page.locator("#apercu")).toContainText(marque);

  // pas encore visible des étudiants
  const before = await page.request.get("/modules/04-workspace/");
  expect(await before.text()).not.toContain(marque);

  await page.getByRole("link", { name: "Tableau de bord" }).click();
  await expect(page.locator("#modules").getByRole("row", { name: /04-workspace/ })).toContainText("modifié, non publié");
  await page.getByRole("button", { name: "Publier le brouillon" }).click();
  await expect(page.locator("#pub-etat")).toContainText("Dernière publication réussie", { timeout: 540_000 });
  await expect(page.locator("#pub-rapports")).toContainText("tests réussis");
  const after = await page.request.get("/modules/04-workspace/");
  expect(await after.text()).toContain(marque);
});

test("l'éditeur refuse un lien étudiant", async ({ page }) => {
  const r = await page.goto(`/admin/login?token=${mint("pas-admin")}`);
  expect(r?.status()).toBe(403);
  await page.goto("/admin/"); // sans session : connexion par le service Comptes
  await expect(page).toHaveURL(/\/connexion\?suite=%2Fcompte%2Fadmin$/);
});
