import { expect, it, vi } from "vitest";
import { ComptesClient, ComptesError, NoAccount, reloginUrl } from "../../src/api/comptes";
import { json } from "./fakes";

it("appelle Comptes avec le cookie de session, sans jeton du Hub", async () => {
  const fetchFn = vi.fn(async () => json(200, { html: "<p>indice</p>" }));
  const c = new ComptesClient(fetchFn);
  expect(await c.hint("02-noeud", 2)).toBe("<p>indice</p>");
  expect(fetchFn).toHaveBeenCalledWith("/api/comptes/exercices/02-noeud/indices/2", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
  });
});

it("401 → NoAccount ; autre erreur → ComptesError avec le statut", async () => {
  await expect(new ComptesClient(async () => json(401)).me()).rejects.toBeInstanceOf(NoAccount);
  const err = await new ComptesClient(async () => json(403)).explanation("02-noeud").catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ComptesError);
  expect((err as ComptesError).status).toBe(403);
});

it("vérification et file d'attente en POST / DELETE", async () => {
  const calls: [string, string][] = [];
  const c = new ComptesClient(async (url, init) => {
    calls.push([init?.method ?? "", url]);
    return json(200, { ticket: "t/1", position: 2, a_vous: false });
  });
  await c.verify("02-noeud");
  await c.joinQueue();
  await c.beat("t/1");
  await c.leaveQueue("t/1");
  expect(calls).toEqual([
    ["POST", "/api/comptes/exercices/02-noeud/verification"],
    ["POST", "/api/comptes/file"],
    ["POST", "/api/comptes/file/t%2F1"],
    ["DELETE", "/api/comptes/file/t%2F1"],
  ]);
});

it("le lien de reconnexion rouvre la page courante du lab", () => {
  expect(reloginUrl({ pathname: "/lab/", search: "?module=02-noeud&exercice=1" })).toBe(
    "/compte/lab?suite=%2Flab%2F%3Fmodule%3D02-noeud%26exercice%3D1",
  );
});
