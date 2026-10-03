// Abonnement pro de bout en bout contre le faux Stripe (deploy/docker-compose.stripe-simule.yml).
import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { admin, cleanup, containerLimits, loginStudent, newEmail, openLabViaAccount, stopServer } from "./helpers";

const STRIPE = process.env.FAKE_STRIPE_URL ?? "http://localhost:12111";
let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

async function minutesLeft(page: Page): Promise<number | null> {
  return (await (await page.request.get("/api/comptes/moi")).json()).minutes_restantes;
}

/** Depuis la page Abonnement : ouvre le portail, clique une action, revient sur ROS Academy. */
async function portal(page: Page, action: string): Promise<void> {
  await page.getByRole("button", { name: "Gérer mon abonnement" }).click();
  await expect(page).toHaveURL(new RegExp(`^${STRIPE}/portal/`));
  await page.getByRole("button", { name: action }).click();
  await page.getByRole("link", { name: "Retour à ROS Academy" }).click();
  await expect(page).toHaveURL(/\/compte\/abonnement$/);
}

test("abonnement pro : paiement, lab sans quota et conteneur pro, échec de paiement, résiliation @stripe", async ({
  page,
}) => {
  test.setTimeout(480_000);
  const name = await loginStudent(page, newEmail(), "/compte/");
  students.push(name);
  expect(await minutesLeft(page)).toBe(600);

  await page.getByRole("link", { name: "Passer en pro" }).click();
  await expect(page.locator(".price")).toHaveText("9,00 € / mois");

  // paiement abandonné : retour sans changement
  await page.getByRole("button", { name: "S'abonner" }).click();
  await expect(page).toHaveURL(new RegExp(`^${STRIPE}/checkout/`)); // la CSP laisse le formulaire aller chez Stripe
  await page.getByRole("link", { name: "Annuler et revenir" }).click();
  await expect(page.getByRole("button", { name: "S'abonner" })).toBeVisible();

  // paiement : formule pro dès le retour
  await page.getByRole("button", { name: "S'abonner" }).click();
  await page.getByRole("button", { name: "Payer" }).click();
  await expect(page).toHaveURL(/\/compte\/abonnement\?retour=paye$/);
  await expect(page.getByText("Vous êtes abonné à la formule pro")).toBeVisible();
  await expect(page.getByText(/Prochain renouvellement le \d{2}\/\d{2}\/\d{4}/)).toBeVisible();
  expect(await minutesLeft(page)).toBeNull();

  await openLabViaAccount(page);
  expect(containerLimits(name)).toEqual({ cpus: 2, memory: 4 * 1024 ** 3, pids: 512 });
  await stopServer(api, name);

  // échec de paiement : Stripe relance, l'étudiant reste pro mais est prévenu
  await page.goto("/compte/abonnement");
  await portal(page, "Simuler un échec de paiement");
  await expect(page.getByText("le dernier paiement a échoué")).toBeVisible();
  expect(await minutesLeft(page)).toBeNull();

  // résiliation à la fin de la période : encore pro jusque-là
  await portal(page, "Reprendre l'abonnement");
  await portal(page, "Résilier à la fin de la période");
  await expect(page.getByText(/la formule pro reste active jusqu'au/)).toBeVisible();
  expect(await minutesLeft(page)).toBeNull();

  // fin de l'abonnement : retour en formule gratuite, et conteneur gratuit au lab suivant
  await portal(page, "Résilier maintenant");
  await expect(page.getByRole("button", { name: "S'abonner" })).toBeVisible();
  expect(await minutesLeft(page)).toBeLessThanOrEqual(600);
  await openLabViaAccount(page);
  expect(containerLimits(name)).toEqual({ cpus: 1, memory: 2 * 1024 ** 3, pids: 256 });
});

test("webhooks du faux Stripe tous acceptés par Comptes (signature vérifiée) @stripe", async ({ request }) => {
  const etat = await (await request.get(`${STRIPE}/__etat`)).json();
  expect(etat.deliveries.length).toBeGreaterThan(0);
  expect(etat.deliveries.filter((d: { status: number }) => d.status !== 200)).toEqual([]);
});
