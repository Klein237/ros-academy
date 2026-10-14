// Achat d'un parcours de bout en bout contre le faux Stripe (deploy/docker-compose.stripe-simule.yml,
// qui active aussi l'accès payant : ACCES_PAYANT=1).
import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { admin, cleanup, containerLimits, loginStudent, newEmail, openLabViaAccount, stopServer } from "./helpers";

const STRIPE = process.env.FAKE_STRIPE_URL ?? "http://localhost:12111";
const PARCOURS = "ros2-fondamentaux";
const MODULE = "05-noeud"; // un module du parcours acheté
const AUTRE = "31-bras-urdf"; // un module d'un autre parcours, non acheté
let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

async function me(page: Page): Promise<{ formule: string; minutes_restantes: number | null }> {
  return (await page.request.get("/api/comptes/moi")).json();
}

test("achat d'un parcours : cours, QCM et lab ouverts pour ce parcours seulement @stripe", async ({ page }) => {
  test.setTimeout(480_000);
  const name = await loginStudent(page, newEmail(), "/compte/");
  students.push(name);

  // sans parcours : ni cours, ni QCM, ni lab
  expect(await me(page)).toMatchObject({ formule: "aucune", minutes_restantes: 0 });
  await page.goto(`/modules/${MODULE}/`);
  await expect(page.getByRole("heading", { name: "Ce module fait partie d'un parcours" })).toBeVisible();
  expect((await page.request.get(`/api/contenus/modules/${MODULE}/qcm`)).status()).toBe(403);
  expect((await page.request.get(`/api/comptes/qcm/${MODULE}`)).status()).toBe(403);
  await page.goto("/compte/lab");
  await expect(page.getByRole("heading", { name: "Le lab est inclus avec un parcours" })).toBeVisible();

  // la page Tarifs mène à la page d'achat
  await page.goto("/tarifs/");
  await page.locator(`a[href="/compte/acheter/${PARCOURS}"]`).click();
  await expect(page.locator(".price")).toContainText("30 €");

  // paiement abandonné : retour sans accès
  await page.getByLabel(/Je demande l'accès immédiat/).check();
  await page.getByRole("button", { name: "Payer 30 €" }).click();
  await expect(page).toHaveURL(new RegExp(`^${STRIPE}/checkout/`)); // la CSP laisse le formulaire aller chez Stripe
  await expect(page.getByText("30,00 €")).toBeVisible();
  await page.getByRole("link", { name: "Annuler et revenir" }).click();
  await expect(page.getByRole("button", { name: "Payer 30 €" })).toBeVisible();
  expect((await me(page)).formule).toBe("aucune");

  // paiement : accès de 12 mois dès le retour
  await page.getByLabel(/Je demande l'accès immédiat/).check();
  await page.getByRole("button", { name: "Payer 30 €" }).click();
  await page.getByRole("button", { name: "Payer" }).click();
  await expect(page).toHaveURL(new RegExp(`/compte/acheter/${PARCOURS}\\?retour=paye$`));
  await expect(page.getByText(/Vous avez accès à ce parcours jusqu'au \d{2}\/\d{2}\/\d{4}/)).toBeVisible();
  expect(await me(page)).toMatchObject({ formule: "pro", minutes_restantes: null });

  // le cours et le QCM du parcours s'ouvrent, pas ceux d'un autre parcours
  await page.goto(`/modules/${MODULE}/`);
  await expect(page.getByRole("heading", { name: "Ce module fait partie d'un parcours" })).toHaveCount(0);
  expect((await page.request.get(`/api/contenus/modules/${MODULE}/qcm`)).status()).toBe(200);
  expect((await page.request.get(`/api/comptes/qcm/${MODULE}`)).status()).toBe(200);
  await page.goto(`/modules/${AUTRE}/`);
  await expect(page.getByRole("heading", { name: "Ce module fait partie d'un parcours" })).toBeVisible();

  // le lab, dans un conteneur pro
  await openLabViaAccount(page);
  expect(containerLimits(name)).toEqual({ cpus: 2, memory: 4 * 1024 ** 3, pids: 512 });
  await stopServer(api, name);
});

test("webhooks du faux Stripe tous acceptés par Comptes (signature vérifiée) @stripe", async ({ request }) => {
  const etat = await (await request.get(`${STRIPE}/__etat`)).json();
  expect(etat.deliveries.length).toBeGreaterThan(0);
  expect(etat.deliveries.filter((d: { status: number }) => d.status !== 200)).toEqual([]);
});
