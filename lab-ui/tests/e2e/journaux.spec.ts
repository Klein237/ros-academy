// Journaux centralisés (Grafana + Loki) et alertes de la veille.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { admin, cleanup, loginStudent, mintAdmin, newEmail, openLabViaAccount, run, stopServer } from "./helpers";

let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

/** Requête LogQL par Grafana (source Loki), avec la session d'administrateur de la page. */
async function loki(page: Page, query: string): Promise<string[]> {
  const now = Date.now() * 1e6;
  const r = await page.request.get("/admin/journaux/api/datasources/proxy/uid/loki/loki/api/v1/query_range", {
    params: { query, start: String(now - 3600e9), end: String(now), limit: "1000" },
  });
  expect(r.status(), await r.text()).toBe(200);
  const body = (await r.json()) as { data: { result: { values: [string, string][] }[] } };
  return body.data.result.flatMap((s) => s.values.map(([, line]) => line));
}

test("les journaux sont réservés à l'administrateur, même avec un en-tête forgé", async ({ page, request }) => {
  const r = await request.get("/admin/journaux/api/user", { maxRedirects: 0 });
  expect(r.status()).toBe(302);
  expect(r.headers()["location"]).toBe("/compte/admin");
  const forged = await request.get("/admin/journaux/api/user", {
    headers: { "X-Academy-Admin": "pirate" },
    maxRedirects: 0,
  });
  expect(forged.status()).toBe(302);

  // un étudiant connecté n'y a pas accès non plus
  await loginStudent(page, newEmail());
  await page.goto("/admin/journaux/");
  await expect(page).toHaveURL(/\/connexion|\/compte\/admin/);
  expect(page.url()).not.toContain("/admin/journaux");
});

test("l'administrateur retrouve les journaux des services et d'un lab arrêté", async ({ page }) => {
  test.setTimeout(300_000);
  const name = await loginStudent(page, newEmail());
  students.push(name);
  await openLabViaAccount(page);
  await run(page, "echo lab-ok", "lab-ok");

  await page.context().clearCookies();
  await page.goto(`/admin/login?token=${mintAdmin()}`);
  // Alloy lit le conteneur pendant la séance (il met quelques secondes à le découvrir)…
  const labLines = () => loki(page, `{service="lab", etudiant="${name}"}`).then((l) => l.length);
  await expect.poll(labLines, { timeout: 60_000 }).toBeGreaterThan(0);
  // …et les journaux restent consultables une fois le conteneur supprimé
  await stopServer(api, name);
  expect(await labLines()).toBeGreaterThan(0);

  await page.goto("/admin/");
  await page.getByRole("link", { name: "Journaux" }).click();
  await expect(page).toHaveURL(/\/admin\/journaux\//);
  await expect(page.getByText("Lignes de journal par service")).toBeVisible({ timeout: 60_000 });

  // identité imposée par Caddy : un en-tête forgé par un admin connecté ne change rien
  const me = await page.request.get("/admin/journaux/api/user", { headers: { "X-Academy-Admin": "pirate" } });
  expect((await me.json()).login).toBe("admin-e2e");

  await expect.poll(() => loki(page, '{service="hub"}').then((l) => l.length), { timeout: 60_000 }).toBeGreaterThan(0);
});

test("une alerte de la veille arrive dans les journaux", async ({ page }) => {
  const seuil = Number(process.env.VEILLE_SEUIL_DISQUE ?? 80);
  test.skip(!(seuil < 50), "seuil de disque non abaissé pour le test (VEILLE_SEUIL_DISQUE)");
  await page.goto(`/admin/login?token=${mintAdmin()}`);
  await expect
    .poll(() => loki(page, '{service="veille"} |= "ALERTE disque"').then((l) => l.length), { timeout: 90_000 })
    .toBeGreaterThan(0);
  const lines = await loki(page, '{service="veille"} |= "ALERTE disque"');
  expect(lines[0]).toContain(`(seuil ${seuil} %)`);
});
