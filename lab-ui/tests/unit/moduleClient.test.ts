import { expect, it, vi } from "vitest";
import { NoAccount } from "../../src/api/comptes";
import { ModuleClient } from "../../src/api/module";

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

it("envoie la session de l'étudiant : le cours lui est réservé", async () => {
  const fetchFn = vi.fn(async () => json(200, { files: [{ path: "a", content: "b" }] }));
  const files = await new ModuleClient("02-noeud", fetchFn).labFiles();
  expect(files).toEqual([{ path: "a", content: "b" }]);
  expect(fetchFn).toHaveBeenCalledWith("/api/contenus/modules/02-noeud/lab", { credentials: "same-origin" });
});

it("401 : session absente ou expirée", async () => {
  const client = new ModuleClient("02-noeud", async () => json(401, { erreur: "Connexion requise" }));
  await expect(client.exercise()).rejects.toBeInstanceOf(NoAccount);
  const other = new ModuleClient("02-noeud", async () => json(404));
  await expect(other.info()).rejects.not.toBeInstanceOf(NoAccount);
});
