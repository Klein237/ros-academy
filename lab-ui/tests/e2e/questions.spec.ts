import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "./fixtures";
import { comptesLogs, loginStudent, newEmail } from "./helpers";

// Questions et réponses d'un module, de bout en bout : deux étudiants et l'équipe (ADMIN_EMAILS).
const MODULE = "/modules/05-noeud/";
const trainerEmail = process.env.ADMIN_EMAILS?.split(",")[0]?.trim();

async function student(browser: import("@playwright/test").Browser, viewport = { width: 1280, height: 900 }): Promise<Page> {
  const page = await browser.newPage({ ignoreHTTPSErrors: true, viewport });
  page.on("dialog", (d) => void d.accept());
  await loginStudent(page, newEmail(), MODULE);
  return page;
}

async function openQuestions(page: Page, hash = "#questions"): Promise<void> {
  await page.goto("about:blank"); // vrai chargement, même si seule l'ancre change
  await page.goto(MODULE + hash);
  await expect(page.locator("#questions")).toBeVisible();
}

const thread = (page: Page, title: string) =>
  page.locator(".fil").filter({ has: page.locator(".fil-titre", { hasText: title }) });

async function expand(page: Page, title: string) {
  const t = thread(page, title);
  if (!(await t.evaluate((d) => (d as HTMLDetailsElement).open))) await t.locator(":scope > summary").click();
  return t;
}

async function ask(page: Page, title: string, text: string, privee = false): Promise<void> {
  await page.getByRole("button", { name: "Poser une question" }).click();
  const form = page.locator(".question-form");
  await form.getByLabel("Titre").fill(title);
  await form.getByLabel("Votre question").fill(text);
  if (privee) await form.getByLabel(/Question privée/).check();
  await form.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect(thread(page, title)).toHaveCount(1);
}

/** Lien d'une notification écrite dans les journaux de Comptes (sans SMTP) : « <libellé> pour <adresse> : <lien> ». */
function mailed(label: string, email: string): boolean {
  return comptesLogs().split("\n").some((l) => l.includes(`${label} pour ${email} : `));
}

test.beforeEach(() => {
  test.skip(!trainerEmail, "ADMIN_EMAILS non défini");
});

test("question publique : même question, réponses, réponse de l'équipe prévenue par e-mail, résolue", async ({ browser }) => {
  const id = randomBytes(3).toString("hex");
  const title = `Le robot ne bouge pas après ros2 run ${id}`;
  const alice = await student(browser);
  const aliceEmail = (await (await alice.request.get("/api/comptes/moi")).json()).email as string;
  await openQuestions(alice);
  await ask(alice, title, "Rien sur /odom.\n```\n$ ros2 topic echo /cmd_vel\n```\n<img src=x onerror=\"window.__xss=1\">");
  const own = thread(alice, title);
  await expect(own.locator(".fil-texte pre code")).toHaveText("$ ros2 topic echo /cmd_vel");
  await expect(own.locator(".fil-texte")).toContainText("<img src=x"); // texte, jamais du HTML
  expect(await alice.evaluate(() => (window as { __xss?: number }).__xss)).toBeUndefined();

  // un autre étudiant : suggestion pendant la saisie, « J'ai la même question », réponse
  const bob = await student(browser);
  const bobEmail = (await (await bob.request.get("/api/comptes/moi")).json()).email as string;
  await openQuestions(bob);
  await bob.getByRole("button", { name: "Poser une question" }).click();
  await bob.locator(".question-form").getByLabel("Titre").fill(`Mon robot ne bouge pas avec ros2 run ${id}`);
  await expect(bob.locator(".question-similaires")).toContainText(title);
  await bob.locator(".question-form").getByRole("button", { name: "Annuler" }).click();
  let t = await expand(bob, title);
  await t.getByRole("button", { name: "J'ai la même question" }).click();
  await expect(thread(bob, title).locator(":scope > summary")).toContainText("1 a la même question");
  t = thread(bob, title);
  await t.locator(".fil-repondre textarea").fill("Vérifie le nom du topic dans create_subscription.");
  await t.getByRole("button", { name: "Répondre", exact: true }).click();
  await expect(thread(bob, title).locator(".fil-reponse")).toHaveCount(1);
  await expect.poll(() => mailed("réponse à une question", aliceEmail)).toBe(true);
  // la question d'un autre : ni résolue, ni masquée par un étudiant
  const qid = Number((await thread(bob, title).getAttribute("id"))!.replace("question-", ""));
  const origin = { Origin: new URL(bob.url()).origin };
  expect((await bob.request.post(`/api/comptes/questions/${qid}/resolue`, { data: { valeur: true }, headers: origin })).status()).toBe(403);
  expect((await bob.request.post(`/api/comptes/questions/${qid}/masquer`, { data: { valeur: true }, headers: origin })).status()).toBe(403);

  // l'équipe : la question attend dans sa liste ; « Répondre » ouvre le fil ; Alice et Bob sont prévenus
  const trainer = await browser.newPage({ ignoreHTTPSErrors: true });
  await loginStudent(trainer, trainerEmail!, "/compte/formateur/questions");
  await trainer.goto("/compte/formateur/questions");
  const waiting = trainer.locator("section", { has: trainer.getByRole("heading", { name: "Sans réponse de l'équipe" }) });
  const history = trainer.locator("section", { has: trainer.getByRole("heading", { name: "Historique" }) });
  const row = waiting.getByRole("row", { name: new RegExp(title) });
  await expect(row).toContainText("1 étudiant de plus a la même question");
  await row.getByRole("link", { name: "Répondre" }).click();
  t = thread(trainer, title);
  await expect(t).toHaveJSProperty("open", true);
  await t.locator(".fil-repondre textarea").fill("Le topic s'écrit cmd_vel :\n```\nself.create_subscription(Twist, 'cmd_vel', ...)\n```");
  await t.locator(".fil-repondre").getByLabel(/partie de la solution/).check();
  await t.getByRole("button", { name: "Répondre (équipe)" }).click();
  await expect(thread(trainer, title).locator(":scope > summary")).toContainText("Réponse de l'équipe");
  await thread(trainer, title).getByRole("button", { name: "Valider cette réponse" }).click();
  await expect(thread(trainer, title).locator(".fil-reponse.validee")).toHaveCount(1);
  await expect.poll(() => mailed("réponse à une question suivie", bobEmail)).toBe(true);
  await trainer.goto("/compte/formateur/questions");
  await expect(waiting.getByRole("row", { name: new RegExp(title) })).toHaveCount(0);
  await expect(history.getByRole("row", { name: new RegExp(title) })).toContainText("Réponse de l'équipe"); // gardée

  // Alice : lien de l'e-mail (#question-…), solution repliée, résolue
  await openQuestions(alice, `#question-${qid}`);
  t = thread(alice, title);
  await expect(t).toHaveJSProperty("open", true);
  const teamAnswer = t.locator(".fil-reponse.equipe");
  await expect(teamAnswer.locator("details.fil-solution")).toHaveJSProperty("open", false);
  await expect(t.locator(".fil-badge", { hasText: "Validée par l'équipe" })).toHaveCount(1);
  await t.getByRole("button", { name: "Marquer comme résolue" }).click();
  await expect(thread(alice, title).locator(":scope > summary")).toContainText("Résolue");
  // l'équipe la supprime depuis l'historique (deux clics) : elle disparaît du module
  await trainer.goto("/compte/formateur/questions");
  const traitee = history.getByRole("row", { name: new RegExp(title) });
  await expect(traitee).toContainText("Résolue");
  await traitee.getByText("Supprimer", { exact: true }).click();
  await traitee.getByRole("button", { name: "Supprimer définitivement" }).click();
  await expect(history.getByRole("row", { name: new RegExp(title) })).toHaveCount(0);
  await openQuestions(bob);
  await expect(thread(bob, title)).toHaveCount(0);
  for (const p of [alice, bob, trainer]) await p.close();
});

test("question privée et modération : invisible des autres étudiants, masquée puis rétablie", async ({ browser }) => {
  const id = randomBytes(3).toString("hex");
  const privee = `Tout mon code ${id}`;
  const publique = `Question publique ${id}`;
  const alice = await student(browser);
  await openQuestions(alice);
  await ask(alice, privee, "Mon fichier complet.", true);
  await expect(thread(alice, privee).locator(".fil-badge", { hasText: "Privée" })).toHaveCount(1);
  await ask(alice, publique, "Une question pour tous.");
  const privateId = Number((await thread(alice, privee).getAttribute("id"))!.replace("question-", ""));

  const bob = await student(browser);
  await openQuestions(bob);
  await expect(thread(bob, publique)).toHaveCount(1);
  await expect(thread(bob, privee)).toHaveCount(0);
  const origin = { Origin: new URL(bob.url()).origin };
  expect((await bob.request.post(`/api/comptes/questions/${privateId}/reponses`, { data: { texte: "x" }, headers: origin })).status()).toBe(404);
  await (await expand(bob, publique)).locator(":scope > .fil-actions").getByRole("button", { name: "Signaler" }).click();
  await expect(thread(bob, publique)).toContainText("Signalé, merci.");

  const trainer = await browser.newPage({ ignoreHTTPSErrors: true });
  await loginStudent(trainer, trainerEmail!, MODULE);
  await openQuestions(trainer);
  await expect(thread(trainer, privee)).toHaveCount(1); // l'équipe voit les questions privées
  await (await expand(trainer, publique)).getByRole("button", { name: "Masquer la question" }).click();
  await expect(thread(trainer, publique).locator(":scope > summary")).toContainText("Masquée");
  await openQuestions(bob);
  await expect(thread(bob, publique)).toHaveCount(0);
  await openQuestions(trainer);
  await (await expand(trainer, publique)).getByRole("button", { name: "Rétablir la question" }).click();
  await openQuestions(bob);
  await expect(thread(bob, publique)).toHaveCount(1);
  for (const p of [alice, bob, trainer]) await p.close();
});

test("téléphone : la barre du bas s'efface pendant la saisie ; un lien vers une question suit la page ouverte", async ({ browser }) => {
  const id = randomBytes(3).toString("hex");
  const page = await student(browser, { width: 390, height: 844 });
  await openQuestions(page);
  await ask(page, `Sur téléphone ${id}`, "Réponse attendue.");
  const bar = page.locator(".barre-mobile");
  await expect(bar).toBeVisible();
  const reply = (await expand(page, `Sur téléphone ${id}`)).locator(".fil-repondre textarea");
  await reply.focus();
  await expect(bar).toBeHidden(); // sinon elle recouvre le champ, clavier ouvert
  await reply.blur();
  await expect(bar).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  // une question arrive après le chargement ; son lien (#question-…) l'ouvre sans recharger
  const origin = { Origin: new URL(page.url()).origin };
  const later = await page.request.post("/api/comptes/questions/05-noeud", {
    data: { titre: `Arrivée après le chargement ${id}`, texte: "y" }, headers: origin,
  });
  const laterId = ((await later.json()) as { question: { id: number } }).question.id;
  await page.evaluate((qid) => { location.hash = `#question-${qid}`; }, laterId);
  await expect(page.locator(`#question-${laterId}`)).toHaveJSProperty("open", true);
  await page.close();
});
