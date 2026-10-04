// En-tête commun (Contenus et Comptes) : menu sur téléphone, avatar quand une session est ouverte.

function setupMenu() {
  const header = document.querySelector(".site-header");
  const toggle = header?.querySelector(".menu-toggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const open = header.classList.toggle("ouvert");
    toggle.setAttribute("aria-expanded", String(open));
  });
}

function initiales(nom, email) {
  const mots = (nom || "").trim().split(/\s+/).filter(Boolean);
  if (mots.length >= 2) return (mots[0][0] + mots[1][0]).toUpperCase();
  if (mots.length === 1) return mots[0].slice(0, 2).toUpperCase();
  return (email || "?").slice(0, 2).toUpperCase();
}

async function setupCompte() {
  const zone = document.querySelector("[data-compte]");
  if (!zone) return;
  let moi;
  try {
    const r = await fetch("/api/comptes/session", { credentials: "same-origin" });
    if (!r.ok) return;
    moi = await r.json();
    if (!moi.connecte) return; // « Se connecter » reste affiché
  } catch {
    return;
  }
  const a = document.createElement("a");
  a.className = "avatar";
  a.href = "/compte/";
  a.title = "Mon compte";
  a.setAttribute("aria-label", `Mon compte (${moi.nom || moi.email})`);
  a.textContent = initiales(moi.nom, moi.email);
  zone.replaceChildren(a);
  document.body.classList.add("connecte");
}

setupMenu();
setupCompte();
