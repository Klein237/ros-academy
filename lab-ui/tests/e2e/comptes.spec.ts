import { expect, request, test, type APIRequestContext } from "./fixtures";
import {
  admin,
  cleanup,
  containerLimits,
  homeExists,
  loginStudent,
  mint,
  newEmail,
  openLabViaAccount,
  run,
  sql,
  waitReady,
} from "./helpers";

let api: APIRequestContext;
const students: string[] = [];

test.beforeAll(async () => {
  api = await admin();
});

test.afterEach(async () => {
  while (students.length) await cleanup(api, students.pop()!);
});

const QCM = "/modules/02-noeud/";

test("le module demande une connexion, puis le QCM compte 2 tentatives au plus", async ({ page }) => {
  // sans connexion, le cours et son QCM sont réservés
  await page.goto(QCM);
  await expect(page.locator(".qcm")).toHaveCount(0);
  await page.locator(".module-reserve").getByRole("link", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion\?suite=\/modules\/02-noeud\/$/);
  await loginStudent(page, newEmail(), `${QCM}#qcm`);
  await expect(page).toHaveURL(new RegExp(`${QCM}#qcm$`));
  const status = page.locator(".qcm-status");
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
  const modules: { id: string; coef: number; exercice: boolean; bonus: boolean }[] = parcours.modules;
  expect(modules.map((m) => m.id)).toEqual(["01-robot-mobile", "02-linux", "01-initiation", "02-noeud", "03-service", "04-action",
    "05-urdf", "06-parametres", "07-tf2", "08-gazebo"]);
  expect(modules.filter((m) => !m.exercice).map((m) => m.id)).toEqual(["01-robot-mobile"]); // module de cours : QCM seul

  // module 01 : QCM sur le site, un indice, exercice réussi
  await page.locator("fieldset[data-question] input").first().check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.locator(".qcm-result")).toContainText("/ 20");
  const result = await page.locator(".qcm-result").textContent();
  const qcm01 = Number(/Note : ([\d,]+) \/ 20/.exec(result ?? "")![1].replace(",", "."));
  const hint = await page.request.post("/api/comptes/exercices/01-initiation/indices/1", { headers: origin });
  expect(hint.ok()).toBe(true);
  // le navigateur ne peut pas déclarer une réussite : seule la vérification du serveur l'enregistre
  const declared = await page.request.post("/api/comptes/exercices/01-initiation/reussite", { headers: origin });
  expect([404, 405]).toContain(declared.status());
  // réussites enregistrées directement en base (l'exercice vérifié par le serveur : test @ros du module Nœud)
  const userId = Number(((await (await page.request.get("/api/comptes/moi")).json()).hub as string).slice(1));
  const done = (id: string) =>
    sql(`INSERT INTO exercises (user_id, module, indices, verifications, reussi_le) VALUES (${userId}, '${id}', 0, 1, now())
         ON CONFLICT (user_id, module) DO UPDATE SET reussi_le = now();`);
  done("01-initiation");

  const notes: Record<string, number> = { "01-initiation": 0.5 * qcm01 + 0.5 * 20 * 0.85 };
  for (const m of modules.filter((x) => x.id !== "01-initiation")) {
    const r = await page.request.post(`/api/comptes/qcm/${m.id}`, { data: { reponses: {} }, headers: origin });
    const qcm = (await r.json()).note as number;
    if (m.exercice) done(m.id);
    notes[m.id] = m.exercice ? 0.5 * qcm + 0.5 * 20 : qcm;
  }

  await page.goto("/compte/resultats");
  const comptes = modules.filter((m) => !m.bonus); // les bonus restent hors note finale
  const total = comptes.reduce((acc, m) => acc + m.coef, 0);
  const finale = comptes.reduce((acc, m) => acc + m.coef * Math.round(notes[m.id] * 100) / 100, 0) / total;
  await expect(page.locator(".final-grade")).toHaveText(`Note finale : ${finale.toFixed(2).replace(".", ",")} / 20`);
  await expect(page.getByRole("row", { name: /Initiation/ })).toContainText("réussi (1 indice) · 17,0");
  await expect(page.getByRole("row", { name: /Le robot mobile/ })).toContainText("sans exercice");

  // certificat (si la note atteint le seuil) : nom imprimé, page publique de vérification, PDF
  const seuil = Number(process.env.CERTIFICAT_NOTE_MIN ?? 10);
  if (finale < seuil) {
    await expect(page.getByText(/Le certificat demande une note finale d'au moins/)).toBeVisible();
    return;
  }
  await page.getByLabel("Nom à imprimer sur le certificat").fill("Élodie N'Diaye-Martin");
  await page.getByRole("button", { name: "Obtenir mon certificat" }).click();
  await expect(page).toHaveURL(/\/certificats\/[2-9A-Z]{16}$/);
  await expect(page.locator(".verdict")).toContainText("Certificat authentique");
  await expect(page.locator("h1")).toHaveText("Élodie N'Diaye-Martin");
  await expect(page.getByText(`${finale.toFixed(2).replace(".", ",")} / 20`).first()).toBeVisible();
  const code = page.url().split("/").at(-1)!;
  // vérifiable par n'importe qui, avec le numéro tel qu'il est imprimé (ABCD-EFGH-…)
  const printed = code.match(/.{4}/g)!.join("-");
  const anonymous = await request.newContext({ baseURL: new URL(page.url()).origin, ignoreHTTPSErrors: true });
  const check = await anonymous.get(`/certificats/${printed}`);
  expect(check.ok()).toBe(true);
  expect(await check.text()).toContain("Certificat authentique");
  const pdf = await anonymous.get(`/certificats/${code}.pdf`);
  expect(pdf.headers()["content-type"]).toBe("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await anonymous.dispose();
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

test("le formateur suit un étudiant dans son tableau de bord ; un étudiant n'y a pas accès", async ({ browser }) => {
  const trainerEmail = process.env.ADMIN_EMAILS?.split(",")[0]?.trim();
  test.skip(!trainerEmail, "ADMIN_EMAILS non défini");
  const student = await browser.newPage({ ignoreHTTPSErrors: true });
  const email = newEmail();
  await loginStudent(student, email, "/modules/01-initiation/");
  const origin = { Origin: new URL(student.url()).origin };
  await student.request.post("/api/comptes/qcm/01-initiation", { data: { reponses: {} }, headers: origin });
  await student.request.post("/api/comptes/exercices/01-initiation/indices/1", { headers: origin });
  expect((await student.goto("/compte/formateur"))?.status()).toBe(403);

  const trainer = await browser.newPage({ ignoreHTTPSErrors: true });
  await loginStudent(trainer, trainerEmail!, "/compte/");
  await trainer.getByRole("link", { name: "Tableau de bord formateur" }).click();
  await expect(trainer.locator("h1")).toHaveText("Tableau de bord formateur");
  await trainer.getByLabel("Rechercher un étudiant").fill(email);
  await trainer.getByRole("button", { name: "Rechercher" }).click();
  await trainer.getByRole("link", { name: email }).click();
  const row = trainer.getByRole("row", { name: /Initiation/ });
  await expect(row).toContainText("(1/2)"); // une tentative de QCM
  await expect(row).toContainText("1 / 3"); // un indice
  await expect(row).toContainText("en cours");
  const csv = await trainer.request.get("/compte/formateur/etudiants.csv");
  expect(csv.headers()["content-type"]).toContain("text/csv");
  expect(await csv.text()).toContain(email);
  await student.close();
  await trainer.close();
});

test("une adresse administratrice ouvre l'éditeur depuis son compte", async ({ page }) => {
  const email = process.env.ADMIN_EMAILS?.split(",")[0]?.trim();
  test.skip(!email, "ADMIN_EMAILS non défini");
  await loginStudent(page, email!, "/compte/");
  await page.getByRole("link", { name: "Éditer les formations" }).click();
  await expect(page.locator("h1")).toHaveText("Formations");
});

test("supprimer son compte efface aussi le lab et ses fichiers (RGPD)", async ({ page }) => {
  const email = newEmail();
  const name = await loginStudent(page, email, "/compte/");
  await openLabViaAccount(page);
  await run(page, "echo personnel > ~/a-effacer.txt && echo FICHIER-\"\"ECRIT", "FICHIER-ECRIT");
  expect(homeExists(name)).toBe(true);
  // l'export contient le compte
  const exported = await page.request.get("/compte/donnees");
  expect((await exported.json()).compte.email).toBe(email);
  await page.goto("/compte/");
  await page.getByRole("link", { name: "Supprimer mon compte" }).click();
  await expect(page.getByLabel("Recopiez votre adresse e-mail pour confirmer")).toBeVisible();
  await expect(page.getByRole("button", { name: "Supprimer définitivement mon compte" })).toBeVisible();
  // envoyé hors du navigateur : sur la machine de test, Chromium voit disparaître l'interface réseau du
  // lab supprimé (ERR_NETWORK_CHANGED) et abandonnerait la réponse ; un vrai navigateur n'est pas concerné
  const deleted = await page.request.post("/compte/supprimer", {
    form: { confirmation: email },
    headers: { Origin: new URL(page.url()).origin },
    timeout: 120_000,
  });
  expect(deleted.status()).toBe(200);
  expect(await deleted.text()).toContain("Compte supprimé");
  await page.goto("/compte/");
  await expect(page).toHaveURL(/\/connexion/); // plus de session
  expect((await api.get(`/hub/api/users/${name}`)).status()).toBe(404);
  expect(homeExists(name)).toBe(false);
  expect(sql(`SELECT count(*) FROM users WHERE email = '${email}';`).trim()).toBe("0");
  // les pages légales sont liées depuis le pied de page
  await page.getByRole("link", { name: "Confidentialité" }).click();
  await expect(page.locator("h1")).toHaveText("Politique de confidentialité");
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
