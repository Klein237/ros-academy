import { expect, test, type APIRequestContext } from "@playwright/test";
import { admin, cleanup, containerLimits, loginStudent, mint, newEmail, openLabViaAccount, sql, waitReady } from "./helpers";

let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

const QCM = "/modules/02-noeud/";

test("le QCM du site demande une connexion, puis compte 2 tentatives au plus", async ({ page }) => {
  await page.goto(QCM);
  const status = page.locator(".qcm-status");
  await expect(status).toContainText("Connectez-vous pour que votre note soit enregistrée");
  await expect(page.getByRole("button", { name: "Valider mes réponses" })).toBeDisabled();

  await status.getByRole("link", { name: "se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion\?suite=/);
  await loginStudent(page, newEmail(), `${QCM}#qcm`);
  await expect(page).toHaveURL(new RegExp(`${QCM}#qcm$`));
  await expect(status).toContainText("Tentatives restantes : 2 sur 2.");

  await page.locator('input[name="spin"]').first().check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.locator(".qcm-result")).toContainText("/ 20");
  await expect(status).toContainText("Tentative restante : 1 sur 2.");
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(status).toContainText("Vous avez utilisé vos 2 tentatives");
  await expect(page.getByRole("button", { name: "Valider mes réponses" })).toBeDisabled();

  // une 3e tentative est refusée par le serveur, pas seulement par la page
  const third = await page.request.post("/api/comptes/qcm/02-noeud", {
    data: { reponses: {} },
    headers: { Origin: new URL(page.url()).origin },
  });
  expect(third.status()).toBe(409);

  await page.goto("/compte/resultats");
  const row = page.getByRole("row", { name: /Écrire un nœud/ });
  await expect(row).toContainText("(2/2)");
  await expect(row).toContainText("à faire"); // exercice pas encore réussi
  await expect(page.getByText("Note finale : disponible quand")).toBeVisible();
});

test("parcours terminé : la note finale pondérée s'affiche sur la page Résultats", async ({ page }) => {
  await loginStudent(page, newEmail(), "/modules/01-initiation/");
  const origin = { Origin: new URL(page.url()).origin };
  const parcours = (await (await page.request.get("/api/contenus/parcours")).json()).parcours[0];
  const modules: { id: string; coef: number }[] = parcours.modules;
  expect(modules.map((m) => m.id)).toEqual(["01-initiation", "02-noeud", "03-service", "04-action", "05-urdf"]);

  // module 01 : QCM sur le site, un indice, exercice réussi
  await page.locator("fieldset[data-question] input").first().check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.locator(".qcm-result")).toContainText("/ 20");
  const result = await page.locator(".qcm-result").textContent();
  const qcm01 = Number(/Note : ([\d,]+) \/ 20/.exec(result ?? "")![1].replace(",", "."));
  const hint = await page.request.post("/api/comptes/exercices/01-initiation/indices/1", { headers: origin });
  expect(hint.ok()).toBe(true);
  // la réussite est déclarée comme le fait le Lab UI après check.sh (exercice complet dans le lab : test @ros)
  const done = (id: string) => page.request.post(`/api/comptes/exercices/${id}/reussite`, { headers: origin });
  expect((await done("01-initiation")).ok()).toBe(true);

  const notes: Record<string, number> = { "01-initiation": 0.5 * qcm01 + 0.5 * 20 * 0.85 };
  for (const m of modules.slice(1)) {
    const r = await page.request.post(`/api/comptes/qcm/${m.id}`, { data: { reponses: {} }, headers: origin });
    const qcm = (await r.json()).note as number;
    expect((await done(m.id)).ok()).toBe(true);
    notes[m.id] = 0.5 * qcm + 0.5 * 20;
  }

  await page.goto("/compte/resultats");
  const total = modules.reduce((acc, m) => acc + m.coef, 0);
  const finale = modules.reduce((acc, m) => acc + m.coef * Math.round(notes[m.id] * 100) / 100, 0) / total;
  await expect(page.locator(".final-grade")).toHaveText(`Note finale : ${finale.toFixed(2).replace(".", ",")} / 20`);
  await expect(page.getByRole("row", { name: /Initiation/ })).toContainText("réussi (1 indice) · 17,0");
});

test("routes internes injoignables depuis l'extérieur", async ({ request }) => {
  for (const [method, path] of [
    ["POST", "/api/contenus/modules/02-noeud/qcm"],
    ["GET", "/api/contenus/modules/02-noeud/indices/1"],
    ["GET", "/api/contenus/modules/02-noeud/explication"],
    ["GET", "/api/contenus/modules/02-noeud/indices%2F1"],
    ["GET", "/api/comptes/interne/lab/u1"],
  ] as const) {
    const r = await request.fetch(path, { method, data: method === "POST" ? { reponses: {} } : undefined });
    expect(r.status(), `${method} ${path}`).toBe(404);
  }
  // sans connexion, Comptes ne sert ni indice ni explication
  expect((await request.post("/api/comptes/exercices/02-noeud/indices/1")).status()).toBe(401);
  expect((await request.get("/api/comptes/exercices/02-noeud/explication")).status()).toBe(401);
});

test("quota épuisé : ni jeton de lab, ni démarrage par le Hub", async ({ page }) => {
  const name = await loginStudent(page, newEmail());
  students.push(name);
  useMinutes(name, 600);
  const r = await page.goto("/compte/lab?suite=%2Flab%2F");
  expect(r?.status()).toBe(403);
  await expect(page.locator("h1")).toHaveText("Quota de lab épuisé");
  await expect(page.getByRole("link", { name: "Voir mes résultats" })).toBeVisible();

  // même avec un jeton du Hub (session ouverte avant l'épuisement), le Hub refuse de démarrer
  await page.goto(`/hub/jwt_login?token=${mint(name)}`);
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "quota", { timeout: 60_000 });
  await expect(page.getByText("Quota de lab épuisé")).toBeVisible();
  const start = await api.post(`/hub/api/users/${name}/server`);
  expect(start.status()).toBeGreaterThanOrEqual(400);
  const user = await (await api.get(`/hub/api/users/${name}`)).json();
  expect(user.servers?.[""]?.ready ?? false).toBe(false);
});

function useMinutes(name: string, minutes: number): void {
  sql(`INSERT INTO usage_ticks (user_id, minute)
       SELECT ${Number(name.slice(1))}, date_trunc('month', now() AT TIME ZONE 'utc') + make_interval(mins => g)
       FROM generate_series(0, ${minutes - 1}) AS g;`);
}

test("dernières minutes : bandeau, puis arrêt du lab au passage à zéro", async ({ page }) => {
  test.setTimeout(360_000);
  const name = await loginStudent(page, newEmail());
  students.push(name);
  useMinutes(name, 599); // il reste 1 minute
  await openLabViaAccount(page);
  await expect(page.locator(".quota-banner")).toContainText("Il vous reste 1 min de lab ce mois-ci");
  // le relevé de Comptes (chaque minute) compte la dernière minute et arrête le serveur
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "quota", { timeout: 240_000 });
  await expect(page.locator(".overlay")).toContainText("Quota de lab épuisé");
  await expect(page.locator(".quota-banner")).toBeHidden();
});

test("formule pro : lab sans quota, conteneur 2 vCPU / 4 Go", async ({ page }) => {
  const name = await loginStudent(page, newEmail());
  students.push(name);
  sql(`UPDATE users SET formule = 'pro' WHERE id = ${Number(name.slice(1))};`);
  useMinutes(name, 600); // ne compte pas en pro
  expect((await (await page.request.get("/api/comptes/moi")).json()).minutes_restantes).toBeNull();
  await openLabViaAccount(page);
  expect(containerLimits(name)).toEqual({ cpus: 2, memory: 4 * 1024 ** 3, pids: 512 });
});

test("session du lab expirée → « Se reconnecter » rouvre la même page du lab", async ({ page }) => {
  const name = await loginStudent(page, newEmail());
  students.push(name);
  await page.goto("/lab/?module=02-noeud");
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "noauth");
  await page.getByRole("link", { name: "Se reconnecter" }).click();
  await expect(page).toHaveURL(/\/lab\/\?module=02-noeud$/);
  await waitReady(page);
  await expect(page.locator(".module-panel")).toContainText("Écrire un nœud");
  await expect(page.locator(".account-note")).toBeHidden(); // connecté : progression enregistrée
});

test("une adresse administratrice ouvre l'éditeur depuis son compte", async ({ page }) => {
  const email = process.env.ADMIN_EMAILS?.split(",")[0]?.trim();
  test.skip(!email, "ADMIN_EMAILS non défini");
  await loginStudent(page, email!, "/compte/");
  await page.getByRole("link", { name: "Éditer les formations" }).click();
  await expect(page.locator("h1")).toHaveText("Formations");
});

test("serveur plein → position dans la file, puis démarrage à son tour @limit", async ({ page }) => {
  // ACTIVE_SERVER_LIMIT=2 (Hub et Comptes) : deux étudiants occupent les places
  for (let i = 0; i < 2; i++) {
    const other = `e2e-plein-${i}-${Date.now()}`;
    students.push(other);
    await page.request.get(`/hub/jwt_login?token=${mint(other)}`, { maxRedirects: 0 });
    await api.post(`/hub/api/users/${other}/server`);
  }
  for (const other of [...students]) {
    await expect
      .poll(async () => (await (await api.get(`/hub/api/users/${other}`)).json()).servers?.[""]?.ready, { timeout: 180_000 })
      .toBe(true);
  }
  await page.context().clearCookies();
  const name = await loginStudent(page, newEmail());
  students.push(name);
  await page.goto("/compte/lab?suite=%2Flab%2F");
  await expect(page.locator(".overlay")).toHaveAttribute("data-state", "full", { timeout: 60_000 });
  await expect(page.locator(".queue-position")).toContainText("n° 1");
  await cleanup(api, students.shift()!); // une place se libère
  await waitReady(page);
  await openLabViaAccount(page); // rouvrir son lab démarré ne repasse pas par la file
});
