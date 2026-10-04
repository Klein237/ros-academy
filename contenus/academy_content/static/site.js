// Onglets Python / C++, bouton Copier, QCM corrigé par le serveur (via Comptes),
// cours et lab côte à côte (« Cours + lab »), filtres du catalogue.

function setupTabs() {
  for (const group of document.querySelectorAll(".code-tabs")) {
    const figures = [...group.querySelectorAll(":scope > figure.code")];
    const bar = document.createElement("div");
    bar.className = "tab-bar";
    bar.setAttribute("role", "tablist");
    const show = (i) => {
      figures.forEach((f, j) => (f.hidden = i !== j));
      [...bar.children].forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
    };
    figures.forEach((fig, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.textContent = fig.dataset.tab || fig.dataset.lang;
      b.addEventListener("click", () => show(i));
      bar.append(b);
    });
    group.prepend(bar);
    group.classList.add("js");
    show(0);
  }
}

function setupCopy() {
  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".code-copy");
    if (!btn) return;
    const code = btn.closest("figure").querySelector("code").textContent;
    try {
      await navigator.clipboard.writeText(code);
      btn.textContent = "Copié";
    } catch {
      btn.textContent = "Copie impossible";
    }
    setTimeout(() => (btn.textContent = "Copier"), 1500);
  });
}

const fr = (n) => String(n).replace(".", ",");

function loginLink(text) {
  const a = document.createElement("a");
  a.href = `/connexion?suite=${encodeURIComponent(location.pathname + "#qcm")}`;
  a.textContent = text;
  return a;
}

// Le QCM passe par le service Comptes : 2 tentatives, la meilleure note est gardée.
function setupQcm() {
  for (const form of document.querySelectorAll("form.qcm")) {
    const url = `/api/comptes/qcm/${encodeURIComponent(form.dataset.module)}`;
    const status = form.querySelector(".qcm-status");
    const result = form.querySelector(".qcm-result");
    const button = form.querySelector("button[type=submit]");
    const showState = (s) => {
      status.textContent =
        s.restantes > 0
          ? `Tentative${s.restantes > 1 ? "s" : ""} restante${s.restantes > 1 ? "s" : ""} : ${s.restantes} sur 2.` +
            (s.meilleure != null ? ` Meilleure note : ${fr(s.meilleure)} / 20.` : "")
          : `Vous avez utilisé vos 2 tentatives. Note retenue : ${fr(s.meilleure)} / 20.`;
      status.hidden = false;
      button.disabled = s.restantes <= 0;
    };
    const askLogin = () => {
      status.replaceChildren("Connectez-vous pour que votre note soit enregistrée : ", loginLink("se connecter"), ".");
      status.hidden = false;
      button.disabled = true;
    };
    fetch(url, { credentials: "same-origin" })
      .then((r) => (r.status === 401 ? askLogin() : r.ok ? r.json().then(showState) : null))
      .catch(() => {});

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const reponses = {};
      for (const fs of form.querySelectorAll("fieldset[data-question]")) {
        reponses[fs.dataset.question] = [...fs.querySelectorAll("input:checked")].map((i) => Number(i.value));
      }
      button.disabled = true;
      result.hidden = true;
      try {
        const r = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reponses }),
        });
        if (r.status === 401) return askLogin();
        if (r.status === 409) {
          const s = await fetch(url, { credentials: "same-origin" }).then((x) => x.json());
          return showState(s);
        }
        if (!r.ok) throw new Error(String(r.status));
        const data = await r.json();
        for (const q of data.questions) {
          const fb = form.querySelector(`fieldset[data-question="${CSS.escape(q.id)}"] .feedback`);
          fb.hidden = false;
          fb.className = `feedback ${q.juste ? "ok" : "ko"}`;
          fb.textContent = q.juste ? `Juste. ${q.explication}` : "Pas tout à fait : relisez le cours.";
        }
        result.textContent = `Note : ${fr(data.note)} / 20 (${data.justes} réponse${data.justes > 1 ? "s" : ""} juste${data.justes > 1 ? "s" : ""} sur ${data.total})`;
        result.hidden = false;
        showState(data);
      } catch {
        result.textContent = "La correction est indisponible, réessayez dans un instant.";
        result.hidden = false;
        button.disabled = false;
      }
    });
  }
}

// --- Cours + lab : le lab (même origine, /lab/?integre=1) dans un panneau à droite du cours.
// « Ouvrir dans le lab » ouvre le fichier dans l'éditeur du panneau, « Lancer dans le lab » tape la
// commande dans son terminal (messages postMessage, voir lab-ui/src/lab.ts). Écrans larges seulement ;
// le choix et la largeur sont retenus d'une page à l'autre.
const COTE_A_COTE = "rosacademy.coteACote";
const LARGEUR_LAB = "rosacademy.largeurLab";
const memoire = {
  lire(cle) {
    try {
      return localStorage.getItem(cle);
    } catch {
      return null;
    }
  },
  ecrire(cle, valeur) {
    try {
      if (valeur === null) localStorage.removeItem(cle);
      else localStorage.setItem(cle, valeur);
    } catch {
      // stockage indisponible (navigation privée) : le choix n'est pas retenu
    }
  },
};

function setupSideBySide() {
  const toggle = document.querySelector("button.cote-a-cote");
  if (!toggle) return;
  const large = window.matchMedia("(min-width: 1100px)");
  let dock = null;
  let frame = null;

  const post = (message) => frame?.contentWindow?.postMessage(message, location.origin);
  const setWidth = (px) => {
    const w = Math.round(Math.min(window.innerWidth * 0.75, Math.max(420, px)));
    document.body.style.setProperty("--lab-w", `${w}px`);
    return w;
  };

  function open(src) {
    if (dock) {
      if (src && frame.getAttribute("src") !== src) frame.src = src;
      return;
    }
    frame = document.createElement("iframe");
    frame.title = "Lab ROS 2";
    frame.src = src;
    frame.allow = "clipboard-read; clipboard-write; fullscreen";
    const handle = document.createElement("div");
    handle.className = "lab-dock-poignee";
    handle.title = "Glisser pour régler la largeur du lab";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fermer le lab";
    close.addEventListener("click", () => shut());
    const bar = document.createElement("div");
    bar.className = "lab-dock-bar";
    const title = document.createElement("strong");
    title.textContent = "Lab";
    bar.append(title, close);
    dock = document.createElement("aside");
    dock.className = "lab-dock";
    dock.setAttribute("aria-label", "Lab à côté du cours");
    dock.append(handle, bar, frame);
    document.body.append(dock);
    document.body.classList.add("cote-a-cote");
    const saved = Number(memoire.lire(LARGEUR_LAB));
    if (saved > 0) setWidth(saved);
    handle.addEventListener("pointerdown", (ev) => {
      handle.setPointerCapture(ev.pointerId);
      dock.classList.add("glisse");
      const move = (e) => memoire.ecrire(LARGEUR_LAB, String(setWidth(window.innerWidth - e.clientX)));
      const up = () => {
        dock.classList.remove("glisse");
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
    });
    for (const b of document.querySelectorAll(".code-run")) b.hidden = false;
    toggle.textContent = "Cours seul";
    toggle.setAttribute("aria-pressed", "true");
    memoire.ecrire(COTE_A_COTE, "1");
  }

  function shut(remember = true) {
    if (!dock) return;
    dock.remove();
    dock = null;
    frame = null;
    document.body.classList.remove("cote-a-cote");
    for (const b of document.querySelectorAll(".code-run")) b.hidden = true;
    toggle.textContent = "Cours + lab";
    toggle.setAttribute("aria-pressed", "false");
    if (remember) memoire.ecrire(COTE_A_COTE, null);
  }

  const follow = () => {
    toggle.hidden = !large.matches;
    if (!large.matches) shut(false); // fenêtre devenue étroite : le cours reprend toute la place
  };
  large.addEventListener("change", follow);
  follow();
  toggle.addEventListener("click", () => (dock ? shut() : open(toggle.dataset.lab)));
  if (large.matches && memoire.lire(COTE_A_COTE) === "1") open(toggle.dataset.lab);

  document.addEventListener("click", (ev) => {
    if (!dock) return;
    const openLink = ev.target.closest("a.code-open[data-open]");
    if (openLink) {
      ev.preventDefault();
      post({ type: "rosacademy:open", path: openLink.dataset.open });
      return;
    }
    const run = ev.target.closest(".code-run");
    if (run) {
      post({ type: "rosacademy:run", command: run.closest("figure").querySelector("code").textContent });
      return;
    }
    if (ev.target.closest("a.exercice-lab")) {
      ev.preventDefault();
      open(toggle.dataset.exercice);
    }
  });

  // Lire le cours compte comme de l'activité : le lab ouvert à côté ne s'arrête pas pour inactivité
  let last = 0;
  for (const type of ["scroll", "keydown", "pointerdown"]) {
    window.addEventListener(
      type,
      () => {
        const now = Date.now();
        if (!dock || now - last < 30_000) return;
        last = now;
        post({ type: "rosacademy:activity" });
      },
      { passive: true },
    );
  }
}

// Page d'un module : étape et section en cours, progression de lecture, barre du bas (téléphone)
function setupModule() {
  const corps = document.querySelector(".module-contenu");
  if (!corps) return;
  const etapes = [...document.querySelectorAll(".etapes-module [data-etape]")];
  const liens = [...document.querySelectorAll(".sommaire [data-section], .sommaire-mobile [data-section]")];
  const cibles = [...corps.querySelectorAll(".cours h2[id], #exercice, #qcm")];
  const barre = document.querySelector(".lecture-barre");
  const suivante = document.querySelector("[data-suivante]");
  const SUITES = {
    cours: ["#exercice", "Aller à l'exercice"],
    exercice: ["#qcm", "Aller au QCM"],
    qcm: [document.querySelector(".prev-next .suivant")?.getAttribute("href") || "#cours", document.querySelector(".prev-next .suivant") ? "Module suivant" : "Revoir le cours"],
  };

  let courante = "";
  const marquer = () => {
    // la dernière cible dont le haut a dépassé le premier quart de l'écran
    const seuil = window.innerHeight * 0.25;
    let id = cibles[0]?.id || "";
    for (const c of cibles) if (c.getBoundingClientRect().top <= seuil) id = c.id;
    const etape = id === "exercice" || id === "qcm" ? id : "cours";
    if (barre) {
      const r = corps.getBoundingClientRect();
      const lu = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - window.innerHeight)));
      barre.style.transform = `scaleX(${lu})`;
    }
    if (id === courante) return;
    courante = id;
    for (const a of liens) {
      if (a.dataset.section === id) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    }
    for (const a of etapes) {
      if (a.dataset.etape === etape) a.setAttribute("aria-current", "step");
      else a.removeAttribute("aria-current");
    }
    if (suivante) [suivante.href, suivante.textContent] = SUITES[etape];
  };
  let prevu = false;
  window.addEventListener("scroll", () => {
    if (prevu) return;
    prevu = true;
    requestAnimationFrame(() => { prevu = false; marquer(); });
  }, { passive: true });
  window.addEventListener("resize", marquer);
  // sommaire du téléphone : on le referme une fois la section choisie
  for (const a of document.querySelectorAll(".sommaire-mobile a")) {
    a.addEventListener("click", () => a.closest("details").removeAttribute("open"));
  }
  marquer();
}

// Catalogue : recherche et filtre par niveau, sans rechargement
function setupCatalogue() {
  const form = document.querySelector("[data-filtres]");
  if (!form) return;
  const cartes = [...document.querySelectorAll("[data-cartes] > .carte-parcours")];
  const aucun = document.querySelector("[data-aucun]");
  let niveau = "";
  const appliquer = () => {
    const q = form.q.value.trim().toLowerCase();
    let visibles = 0;
    for (const c of cartes) {
      const ok = (!niveau || c.dataset.niveau === niveau) && (!q || c.dataset.recherche.includes(q));
      c.hidden = !ok;
      if (ok) visibles++;
    }
    aucun.hidden = visibles > 0;
  };
  form.addEventListener("submit", (ev) => ev.preventDefault());
  form.q.addEventListener("input", appliquer);
  for (const b of form.querySelectorAll("[data-niveau]")) {
    b.addEventListener("click", () => {
      niveau = b.dataset.niveau;
      for (const o of form.querySelectorAll("[data-niveau]")) o.setAttribute("aria-pressed", String(o === b));
      appliquer();
    });
  }
  form.hidden = false;
}

setupTabs();
setupCopy();
setupCatalogue();
setupModule();
setupQcm();
setupSideBySide();
