import { expect, test, type APIRequestContext } from "@playwright/test";
import { activeTerminal, admin, cleanup, mint, mintAdmin, newStudent, run, waitReady } from "./helpers";

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
  const name = student();
  const next = "/lab/?module=02-noeud&exercice=1";
  await page.goto(`/hub/jwt_login?token=${mint(name)}&next=${encodeURIComponent(next)}`);
  await waitReady(page);
  const panel = page.locator(".module-panel");
  await expect(panel).toContainText("Écrire un nœud");
  await expect(panel.locator(".enonce")).toContainText("Le robot reste immobile");
  await panel.getByRole("button", { name: "Commencer l'exercice" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice prêt", { timeout: 180_000 });
  await expect(page.locator('.tree-row[data-path="ws/02-noeud-exercice"]')).toBeVisible();

  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Pas encore", { timeout: 120_000 });
  await expect(panel.locator(".exercise-status")).toContainText("Le robot n'avance pas");

  await panel.getByRole("button", { name: "Indice 1" }).click();
  await expect(panel.locator(".hint")).toContainText("ros2 node info");

  // la correction, comme un étudiant la ferait dans un terminal
  await page.locator(".terminals .tab").first().click();
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open");
  await run(page, `sed -i 's/cmd_vell/cmd_vel/' ~/ws/02-noeud-exercice/src/my_pkg/my_pkg/diff_drive_node.py && echo corrige-""ok`, "corrige-ok");
  await panel.getByRole("button", { name: "Vérifier" }).click();
  await expect(panel.locator(".exercise-status")).toContainText("Exercice réussi", { timeout: 120_000 });
  await expect(panel.locator(".explication")).toContainText("cmd_vell");
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
  await page.goto("/admin/");
  await expect(page.locator("h1")).toHaveText("Connexion requise");
});
