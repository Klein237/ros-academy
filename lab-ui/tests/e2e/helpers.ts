import { execSync } from "node:child_process";
import { createHmac, randomBytes } from "node:crypto";
import { expect, request, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "https://localhost";

function b64url(data: string | Buffer): string {
  return Buffer.from(data).toString("base64url");
}

/** Jeton de connexion signé comme le fera le service Comptes. */
export function mint(sub: string, plan = "free", ttl = 300): string {
  const secret = process.env.JWT_SECRET;
  if (!secret) throw new Error("JWT_SECRET manquant");
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = b64url(JSON.stringify({ sub, plan, aud: "ros-lab", iat: now, exp: now + ttl }));
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

/** Lien de connexion à l'éditeur (rôle admin). */
export function mintAdmin(ttl = 300): string {
  const secret = process.env.JWT_SECRET;
  if (!secret) throw new Error("JWT_SECRET manquant");
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = b64url(JSON.stringify({ sub: "admin-e2e", role: "admin", aud: "ros-academy-admin", iat: now, exp: now + ttl }));
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

export function newStudent(): string {
  return `e2e${randomBytes(4).toString("hex")}`;
}

export async function admin(): Promise<APIRequestContext> {
  const token = process.env.HUB_ADMIN_TOKEN;
  if (!token) throw new Error("HUB_ADMIN_TOKEN manquant");
  return request.newContext({
    baseURL: BASE,
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { Authorization: `token ${token}` },
  });
}

/** Arrête le serveur et supprime l'étudiant (fin de test). */
export async function cleanup(api: APIRequestContext, name: string): Promise<void> {
  await api.delete(`/hub/api/users/${name}/server`);
  for (let i = 0; i < 30; i++) {
    const r = await api.get(`/hub/api/users/${name}`);
    if (r.status() === 404) return;
    const body = await r.json();
    if (!body.servers || Object.keys(body.servers).length === 0) break;
    await new Promise((res) => setTimeout(res, 2000));
  }
  await api.delete(`/hub/api/users/${name}`);
}

/** Connexion par le lien du site, puis attente du lab prêt. */
export async function openLab(page: Page, name: string, query = ""): Promise<void> {
  const next = `/lab/${query}`;
  await page.goto(`/hub/jwt_login?token=${mint(name)}&next=${encodeURIComponent(next)}`);
  await expect(page).toHaveURL(/\/lab\//);
  await waitReady(page);
}

/** Échoue si la page enfreint sa CSP ou lève une erreur JavaScript. */
export function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" && /Content Security Policy|Refused to/i.test(m.text())) errors.push(m.text());
  });
  return errors;
}

export async function waitReady(page: Page): Promise<void> {
  await expect(page.locator(".overlay")).toBeHidden({ timeout: 180_000 });
  await expect(activeTerminal(page)).toHaveAttribute("data-status", "open", { timeout: 60_000 });
}

export function activeTerminal(page: Page) {
  return page.locator(".terminal-host:not([hidden])");
}

/** Tape une commande dans le terminal visible et attend un texte dans sa sortie. */
export async function run(page: Page, command: string, expected?: string | RegExp, timeout = 60_000): Promise<void> {
  const term = activeTerminal(page);
  await term.click();
  await page.keyboard.type(command);
  await page.keyboard.press("Enter");
  if (expected !== undefined) await expect(term.locator(".xterm-rows")).toContainText(expected, { timeout });
}

/** Colle du texte dans Monaco (le collage ne réindente pas, contrairement à la frappe). */
export async function pasteInEditor(page: Page, text: string): Promise<void> {
  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.evaluate((t) => navigator.clipboard.writeText(t), text);
  await page.keyboard.press("ControlOrMeta+V");
}

// --- Service Comptes

export function newEmail(): string {
  return `e2e-${randomBytes(4).toString("hex")}@exemple.fr`;
}

/**
 * Journaux du service Comptes : sans SMTP, le lien de connexion y est écrit.
 * COMPTES_LOGS remplace la commande (déploiement local).
 */
function comptesLogs(): string {
  return execSync(process.env.COMPTES_LOGS ?? "docker logs deploy-comptes-1 2>&1", { encoding: "utf8", maxBuffer: 64 << 20 });
}

/** Requête SQL dans la base de Comptes (PSQL remplace la commande). */
export function sql(query: string): string {
  // ON_ERROR_STOP : une requête en erreur fait échouer le test au lieu de passer inaperçue
  const cmd = `${process.env.PSQL ?? "docker exec -i deploy-postgres-1 psql -U comptes -d comptes -tA"} -v ON_ERROR_STOP=1`;
  return execSync(cmd, { input: query, encoding: "utf8" }).trim();
}

/** Connexion par lien magique (lu dans les journaux) ; renvoie le nom de l'étudiant dans le Hub. */
export async function loginStudent(page: Page, email: string, suite = "/"): Promise<string> {
  await page.goto(`/connexion?suite=${encodeURIComponent(suite)}`);
  await page.getByLabel("Adresse e-mail").fill(email);
  await page.getByRole("button", { name: "Recevoir un lien de connexion" }).click();
  await expect(page.getByText(`Un lien de connexion a été envoyé à ${email}`)).toBeVisible();
  let link = "";
  await expect
    .poll(() => {
      const lines = comptesLogs().split("\n").filter((l) => l.includes(`lien de connexion pour ${email}`));
      link = lines.at(-1)?.split(" : ").at(-1)?.trim() ?? "";
      return link;
    })
    .toMatch(/\/connexion\/email\//);
  await page.goto(new URL(link).pathname);
  const me = await page.request.get("/api/comptes/moi");
  expect(me.ok()).toBe(true);
  return ((await me.json()) as { hub: string }).hub;
}

/** Lab ouvert comme depuis le site : /compte/lab vérifie le quota et émet le jeton du Hub. */
export async function openLabViaAccount(page: Page, query = ""): Promise<void> {
  await page.goto(`/compte/lab?suite=${encodeURIComponent(`/lab/${query}`)}`);
  await expect(page).toHaveURL(/\/lab\//);
  await waitReady(page);
}

/** Limites du conteneur de l'étudiant (DockerSpawner traduit cpu_limit en CpuQuota / CpuPeriod). */
export function containerLimits(name: string): { cpus: number; memory: number; pids: number } {
  const fmt = "{{.HostConfig.NanoCpus}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}} {{.HostConfig.Memory}} {{.HostConfig.PidsLimit}}";
  const [nano, quota, period, memory, pids] = execSync(`docker inspect -f '${fmt}' jupyter-${name}`, { encoding: "utf8" })
    .trim()
    .split(" ")
    .map(Number);
  return { cpus: nano ? nano / 1e9 : quota / period, memory, pids };
}

/** Arrête le serveur de l'étudiant et attend qu'il ait disparu (le compte est gardé). */
export async function stopServer(api: APIRequestContext, name: string): Promise<void> {
  await api.delete(`/hub/api/users/${name}/server`);
  await expect
    .poll(async () => Object.keys((await (await api.get(`/hub/api/users/${name}`)).json()).servers ?? {}).length, {
      timeout: 60_000,
    })
    .toBe(0);
}
