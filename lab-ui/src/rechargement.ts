/**
 * Un fichier de la page chargé à la demande (le lab, l'éditeur, la vue 3D…) n'a pas pu être
 * téléchargé : réseau qui change (Wi-Fi, VPN), coupure brève, ou nouvelle version déployée
 * pendant que l'onglet était ouvert (les anciens fichiers n'existent plus). Sans rien faire, la
 * page reste blanche ou à moitié chargée ; on la recharge, une fois par minute au plus pour ne
 * jamais boucler si le serveur est vraiment injoignable.
 */
export const CLE = "roboforge:rechargement";
export const INTERVALLE_MS = 60_000;

export interface Stockage {
  getItem(cle: string): string | null;
  setItem(cle: string, valeur: string): void;
}

/** Vrai si la page n'a pas déjà été rechargée pour cette raison dans la dernière minute. */
export function doitRecharger(dernier: string | null, maintenant: number, intervalle = INTERVALLE_MS): boolean {
  const t = Number(dernier);
  return !dernier || !Number.isFinite(t) || maintenant - t >= intervalle || t > maintenant;
}

export function rechargerSiModuleIntrouvable(
  ev: Event,
  stockage: Stockage | null,
  recharger: () => void,
  maintenant = Date.now(),
): boolean {
  // Sans mémoire du dernier rechargement (stockage indisponible), on ne recharge pas : un
  // serveur vraiment injoignable ferait recharger la page en boucle.
  if (!stockage) return false;
  try {
    if (!doitRecharger(stockage.getItem(CLE), maintenant)) return false; // déjà essayé : l'erreur suit son cours
    stockage.setItem(CLE, String(maintenant));
  } catch {
    return false;
  }
  ev.preventDefault();
  recharger();
  return true;
}

export function installerRechargement(): void {
  let stockage: Stockage | null = null;
  try {
    stockage = window.sessionStorage;
  } catch {
    stockage = null;
  }
  window.addEventListener("vite:preloadError", (ev) => {
    const cause = (ev as Event & { payload?: unknown }).payload;
    if (rechargerSiModuleIntrouvable(ev, stockage, () => location.reload())) {
      console.warn("Fichier de la page introuvable : rechargement de la page", cause);
    } else {
      console.warn("Fichier de la page introuvable, page déjà rechargée il y a moins d'une minute", cause);
    }
  });
}
