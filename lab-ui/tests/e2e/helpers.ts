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
