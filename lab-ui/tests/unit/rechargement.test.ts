import { expect, it } from "vitest";
import { CLE, doitRecharger, rechargerSiModuleIntrouvable, type Stockage } from "../../src/rechargement";

class Memoire implements Stockage {
  valeurs = new Map<string, string>();
  getItem(cle: string) {
    return this.valeurs.get(cle) ?? null;
  }
  setItem(cle: string, valeur: string) {
    this.valeurs.set(cle, valeur);
  }
}

it("recharge au plus une fois par minute", () => {
  expect(doitRecharger(null, 1_000_000)).toBe(true);
  expect(doitRecharger("1000000", 1_030_000)).toBe(false);
  expect(doitRecharger("1000000", 1_060_000)).toBe(true);
  expect(doitRecharger("abc", 1_000_000)).toBe(true);
  expect(doitRecharger("2000000", 1_000_000)).toBe(true); // horloge revenue en arrière
});

it("module introuvable : recharge la page et retient l'heure, puis laisse passer l'erreur suivante", () => {
  const stockage = new Memoire();
  let recharges = 0;
  const ev1 = new Event("vite:preloadError", { cancelable: true });
  expect(rechargerSiModuleIntrouvable(ev1, stockage, () => recharges++, 5_000_000)).toBe(true);
  expect(ev1.defaultPrevented).toBe(true);
  expect(stockage.getItem(CLE)).toBe("5000000");
  const ev2 = new Event("vite:preloadError", { cancelable: true });
  expect(rechargerSiModuleIntrouvable(ev2, stockage, () => recharges++, 5_010_000)).toBe(false);
  expect(ev2.defaultPrevented).toBe(false); // l'erreur n'est pas masquée
  expect(recharges).toBe(1);
});

it("sans stockage, ne recharge jamais (pas de boucle)", () => {
  const ev = new Event("vite:preloadError", { cancelable: true });
  let recharges = 0;
  expect(rechargerSiModuleIntrouvable(ev, null, () => recharges++)).toBe(false);
  const casse: Stockage = { getItem: () => null, setItem: () => { throw new Error("plein"); } };
  expect(rechargerSiModuleIntrouvable(ev, casse, () => recharges++)).toBe(false);
  expect(recharges).toBe(0);
});
