import { expect, test, type APIRequestContext } from "./fixtures";
import {
  activeTerminal,
  admin,
  cleanup,
  loginStudent,
  mint,
  mintAdmin,
  newEmail,
  newStudent,
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

function student(): string {
  const name = newStudent();
  students.push(name);
  return name;
}

test("le site présente le parcours et corrige le QCM sans exposer les réponses", async ({ page }) => {
  await loginStudent(page, newEmail());
  await page.goto("/");
  await page.getByRole("link", { name: "ROS 2 Fondamentaux" }).click();
  await expect(page.locator("h1")).toHaveText("ROS 2 Fondamentaux");
  await page.getByRole("link", { name: "Écrire un nœud" }).click();
  await expect(page.locator(".code-tabs .tab-bar button")).toHaveText(["Python", "C++"]);
  const html = await page.content();
  expect(html).not.toMatch(/correct["':=]/); // ni attribut ni donnée « correct » dans la page
  await page.locator('input[name="spin"]').first().check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.locator(".qcm-result")).toContainText("/ 20");
  await expect(page.locator('fieldset[data-question="spin"] .feedback')).toContainText("Juste");
});

test("module Nœud : « Ouvrir dans le lab » crée le fichier du cours sans jamais l'écraser", async ({ page }) => {
  const name = student();
  const file = "ws/02-noeud/src/my_pkg/my_pkg/diff_drive_node.py";
  const next = `/lab/?module=02-noeud&open=${encodeURIComponent(file)}`;
  await page.goto(`/hub/jwt_login?token=${mint(name)}&next=${encodeURIComponent(next)}`);
  await waitReady(page);
  await expect(page.locator(".editor .tab.active")).toContainText("diff_drive_node.py");
  await expect(page.locator(".monaco-editor")).toContainText("class DiffDriveNode");
  await expect(page.locator('.tree-row[data-path="ws/02-noeud/src"]')).toBeVisible(); // lab/ installé et déplié
  // en tête de fichier : Monaco n'affiche que les lignes visibles
  await run(page, `sed -i '1i # ma modification' ~/${file} && echo ok-""modifie`, "ok-modifie");
  await page.reload();
  await waitReady(page);
  await expect(page.locator(".monaco-editor")).toContainText("# ma modification");
});

test("module Nœud : l'exercice se fait entièrement dans le lab @ros", async ({ page }) => {
  students.push(await loginStudent(page, newEmail()));
  // comme le bouton « Ouvrir l'exercice dans le lab » du site
  await page.goto("/modules/02-noeud/");
  await page.getByRole("link", { name: "Ouvrir l'exercice dans le lab" }).click();
  await expect(page).toHaveURL(/\/lab\/\?module=02-noeud&exercice=1$/);
  await waitReady(page);
  const panel = page.locator(".module-panel");
  await expect(panel).toContainText("Écrire un nœud");
  await expect(panel.locator(".enonce")).toContainText("Le robot reste immobile");
  await panel.getByRole("button", { name: "Commencer l'exercice" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice prêt", { timeout: 180_000 });
  await expect(page.locator('.tree-row[data-path="ws/02-noeud-exercice"]')).toBeVisible();

  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 180_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Le robot n'avance pas");

  await panel.getByRole("button", { name: "Indice 1" }).click();
  await expect(panel.locator(".hint")).toContainText("ros2 node info");

  // tricher sur check.sh ne sert à rien : le serveur lance le check.sh publié, hors du conteneur
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, `printf '#!/bin/bash\\nexit 0\\n' > ~/.academy/02-noeud/check.sh && echo triche-""ok`, "triche-ok");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 180_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Le robot n'avance pas");

  // la correction, comme un étudiant la ferait dans un terminal
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, `sed -i 's/cmd_vell/cmd_vel/' ~/ws/02-noeud-exercice/src/my_pkg/my_pkg/diff_drive_node.py && echo corrige-""ok`, "corrige-ok");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice réussi", { timeout: 180_000 });
  await expect(panel.locator(".explication")).toContainText("cmd_vell");

  // réussite et indice enregistrés : retrouvés en rouvrant le lab, comptés dans les résultats
  await openLabViaAccount(page, "?module=02-noeud");
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
  await page.goto("/modules/02-noeud/");
  await expect(page.locator(".code-run").first()).toBeHidden(); // sans le lab à côté : pas de bouton
  await page.getByRole("button", { name: "Cours + lab" }).click();
  const lab = page.frameLocator(".lab-dock iframe");
  await expect(lab.locator(".overlay")).toBeHidden({ timeout: 180_000 });
  const term = lab.locator(".terminal-host:not([hidden])");
  await expect(term).toHaveAttribute("data-status", "open", { timeout: 60_000 });
  await expect(lab.locator(".panel.files")).toBeHidden(); // intégré : fichiers repliés au départ
  // « Lancer dans le lab » : le premier bloc de commandes (création des paquets) s'exécute dans le terminal
  await page.locator(".code-run").first().click();
  await expect(term.locator(".xterm-rows")).toContainText("ros2 pkg create my_pkg_cpp", { timeout: 30_000 });
  // exécuté ligne par ligne : le « cd » a changé de dossier (les paquets existent déjà : lab guidé installé)
  await expect(term.locator(".xterm-rows")).toContainText("/ws/02-noeud/src$", { timeout: 60_000 });
  // « Ouvrir dans le lab » : le fichier du cours s'ouvre dans l'éditeur du panneau, la page ne change pas
  await page.locator('a.code-open[data-open$="diff_drive_node.py"]').first().click();
  await expect(page).toHaveURL(/\/modules\/02-noeud\/$/);
  await expect(lab.locator(".editor .tab.active")).toContainText("diff_drive_node.py");
  // le choix est retenu d'une page à l'autre ; « Cours seul » referme le panneau
  await page.reload();
  await expect(page.locator(".lab-dock iframe")).toBeVisible();
  await page.getByRole("button", { name: "Cours seul" }).click();
  await expect(page.locator(".lab-dock")).toHaveCount(0);
  await expect(page.locator(".code-run").first()).toBeHidden();
  expect(errors).toEqual([]);
});

test("l'administrateur modifie un module et le publie après les tests", async ({ page }) => {
  test.setTimeout(600_000);
  const marque = `Initiation à ROS 2 — édition ${Date.now()}`;
  await page.goto(`/admin/login?token=${mintAdmin()}`);
  await expect(page.locator("h1")).toHaveText("Formations");
  await page.locator("#modules").getByRole("row", { name: /01-initiation/ }).getByRole("link", { name: "Éditer" }).click();
  const area = page.locator("#contenu");
  await expect(area).toHaveValue(/titre: Initiation à ROS 2/);
  const text = await area.inputValue();
  await area.fill(text.replace(/^# Initiation à ROS 2.*$/m, `# ${marque}`));
  await page.keyboard.press("ControlOrMeta+S");
  await expect(page.locator("#etat-fichier")).toHaveText("Enregistré");
  await expect(page.locator("#apercu")).toContainText(marque);

  // pas encore visible des étudiants
  const before = await page.request.get("/modules/01-initiation/");
  expect(await before.text()).not.toContain(marque);

  await page.getByRole("link", { name: "Tableau de bord" }).click();
  await expect(page.locator("#modules").getByRole("row", { name: /01-initiation/ })).toContainText("modifié, non publié");
  await page.getByRole("button", { name: "Publier le brouillon" }).click();
  await expect(page.locator("#pub-etat")).toContainText("Dernière publication réussie", { timeout: 540_000 });
  await expect(page.locator("#pub-rapports")).toContainText("tests réussis");
  const after = await page.request.get("/modules/01-initiation/");
  expect(await after.text()).toContain(marque);
});

test("l'éditeur refuse un lien étudiant", async ({ page }) => {
  const r = await page.goto(`/admin/login?token=${mint("pas-admin")}`);
  expect(r?.status()).toBe(403);
  await page.goto("/admin/"); // sans session : connexion par le service Comptes
  await expect(page).toHaveURL(/\/connexion\?suite=%2Fcompte%2Fadmin$/);
});
