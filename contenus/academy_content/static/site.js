// Onglets Python / C++, bouton Copier, QCM corrigé par le serveur (via Comptes),
// cours et lab côte à côte (« Ouvrir le lab » sur écran large), filtres du catalogue.

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
  const labSeul = document.querySelector("a.lab-seul");
  const pleinEcran = document.querySelector("a.lab-plein-ecran");
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
    // fermeture : « Masquer le lab » dans la barre du module (un seul bouton pour ça)
    dock = document.createElement("aside");
    dock.className = "lab-dock";
    dock.setAttribute("aria-label", "Lab à côté du cours");
    dock.append(handle, frame);
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
    toggle.textContent = "Masquer le lab";
    toggle.classList.remove("primary");
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
    toggle.textContent = "Ouvrir le lab";
    toggle.classList.add("primary");
    toggle.setAttribute("aria-pressed", "false");
    if (remember) memoire.ecrire(COTE_A_COTE, null);
  }

  const follow = () => {
    toggle.hidden = !large.matches;
    if (labSeul) labSeul.hidden = large.matches;
    if (pleinEcran) pleinEcran.hidden = !large.matches;
    if (!large.matches) shut(false); // fenêtre devenue étroite : le cours reprend toute la place
  };
  large.addEventListener("change", follow);
  follow();
  toggle.addEventListener("click", () => (dock ? shut() : open(toggle.dataset.lab)));
  if (large.matches && memoire.lire(COTE_A_COTE) === "1") open(toggle.dataset.lab);

  document.addEventListener("click", (ev) => {
    // « Ouvrir l'exercice dans le lab » : à côté de l'énoncé dès que l'écran le permet
    if (large.matches && ev.target.closest("a.exercice-lab")) {
      ev.preventDefault();
      open(toggle.dataset.exercice);
      return;
    }
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
    // module de cours, sans exercice : du cours directement au QCM
    cours: document.getElementById("exercice") ? ["#exercice", "Aller à l'exercice"] : ["#qcm", "Aller au QCM"],
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

// Page d'un parcours : état de chaque module et « Reprendre », si une session est ouverte
async function setupProgression() {
  const carte = document.querySelector("[data-progression]");
  if (!carte) return;
  let p;
  try {
    const r = await fetch(`/api/comptes/progression/${encodeURIComponent(carte.dataset.progression)}`);
    if (!r.ok) return;
    p = await r.json();
  } catch {
    return;
  }
  if (!p.connecte) return;
  const TEXTES = { termine: "Terminé", en_cours: "En cours", a_faire: "À faire" };
  for (const li of document.querySelectorAll(".programme li[data-module]")) {
    const m = p.modules[li.dataset.module];
    if (!m) continue;
    li.dataset.etat = m.etat;
    const badge = document.createElement("span");
    badge.className = "etat-module";
    badge.textContent = m.note != null ? `${TEXTES[m.etat]} · ${String(m.note.toFixed(1)).replace(".", ",")} / 20` : TEXTES[m.etat];
    li.append(badge);
  }
  const titre = carte.querySelector(".carte-reprise-titre");
  const texte = carte.querySelector("p");
  const bouton = carte.querySelector("a");
  titre.textContent = "Votre progression";
  texte.textContent = `${p.termines} module${p.termines > 1 ? "s" : ""} terminé${p.termines > 1 ? "s" : ""} sur ${p.total}`;
  const jauge = document.createElement("progress");
  jauge.className = "jauge";
  jauge.max = p.total;
  jauge.value = p.termines;
  jauge.setAttribute("aria-label", "Modules terminés");
  texte.after(jauge);
  if (p.acces === false) {
    // parcours pas encore acheté (ou offert avec un certificat) : la page d'achat dit comment l'ouvrir
    bouton.href = `/compte/acheter/${encodeURIComponent(carte.dataset.progression)}`;
    bouton.textContent = "Ouvrir le parcours";
  } else if (p.prochain) {
    bouton.href = `/modules/${encodeURIComponent(p.prochain)}/`;
    bouton.textContent = p.termines || Object.values(p.modules).some((m) => m.etat !== "a_faire")
      ? `Reprendre : ${p.prochain_titre}` : "Commencer le module 1";
  } else {
    bouton.href = "/compte/resultats";
    bouton.textContent = "Parcours terminé : voir mes notes";
  }
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

// --- Questions et réponses du module : l'étudiant bloqué demande, l'équipe et les autres étudiants
// répondent (API de Comptes). Le texte n'est jamais interprété comme du HTML : textContent seulement ;
// un bloc entre deux lignes ``` devient du code.
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  e.append(...children.filter((c) => c != null && c !== false));
  return e;
}

function texteRiche(texte) {
  const bloc = el("div", { class: "fil-texte" });
  texte.split(/^```[^\n]*$/m).forEach((part, i) => {
    const t = part.replace(/^\n|\n$/g, "");
    if (!t) return;
    bloc.append(i % 2 ? el("pre", {}, el("code", { text: t })) : el("p", { text: t }));
  });
  return bloc;
}

function repliable(contenu, solution) {
  if (!solution) return contenu;
  return el("details", { class: "fil-solution" }, el("summary", { text: "Contient une partie de la solution : afficher quand même" }), contenu);
}

const dateFr = (iso) => new Date(iso).toLocaleDateString("fr-FR");

// Questions qui ressemblent à celle qu'on écrit : mots en commun (sans accents ni mots outils),
// ceux du titre comptent double.
const MOTS_OUTILS = new Set(("les des une pour dans par sur avec pas que qui quoi est sont mais ont ici fait faire "
  + "mon mes ton tes son ses cette ces leur aux elle ils nous vous comment pourquoi quand quel quelle "
  + "plus moins tout tous rien bien aussi encore alors donc car comme the and").split(" "));
function mots(texte) {
  return new Set((texte || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .split(/[^a-z0-9_]+/).filter((m) => m.length >= 3 && !MOTS_OUTILS.has(m)));
}
function ressemblantes(questions, titre, texte, max = 3) {
  const cherches = new Set([...mots(titre), ...mots(texte)]);
  if (!cherches.size) return [];
  return questions
    .map((q) => {
      const t = mots(q.titre), c = mots(q.texte);
      let score = 0;
      for (const m of cherches) score += t.has(m) ? 2 : c.has(m) ? 1 : 0;
      return { q, score };
    })
    .filter((x) => x.score >= 2)
    .sort((a, b) => b.score - a.score || b.q.meme - a.q.meme)
    .slice(0, max)
    .map((x) => x.q);
}

function setupQuestions() {
  const section = document.getElementById("questions");
  if (!section) return;
  const module = section.dataset.module;
  const liste = section.querySelector(".questions-liste");
  const form = section.querySelector(".question-form");
  const status = form.querySelector(".question-status");
  const base = "/api/comptes";
  let equipe = false;

  const envoyer = async (url, body = {}) => {
    const r = await fetch(base + url, {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.erreur || "L'envoi a échoué, réessayez dans un instant.");
    return data;
  };

  const badge = (texte, kind) => el("span", { class: `fil-badge ${kind}`, text: texte });

  function reponse(q, a) {
    const actions = el("div", { class: "fil-actions" });
    if (equipe && !a.equipe) {
      actions.append(el("button", { type: "button", class: "lien", text: a.validee ? "Retirer la validation" : "Valider cette réponse" }));
      actions.lastChild.addEventListener("click", () => agir(`/reponses/${a.id}/valider`, { valeur: !a.validee }));
    }
    if (equipe) {
      actions.append(el("button", { type: "button", class: "lien", text: a.masquee ? "Rétablir" : "Masquer" }));
      actions.lastChild.addEventListener("click", () => agir(`/reponses/${a.id}/masquer`, { valeur: !a.masquee }));
    } else if (!a.moi) {
      actions.append(signaler(`/reponses/${a.id}/signaler`));
    }
    return el("li", { class: `fil-reponse${a.equipe ? " equipe" : ""}${a.validee ? " validee" : ""}${a.masquee ? " masquee" : ""}` },
      el("p", { class: "fil-meta" }, el("strong", { text: a.auteur }),
        a.equipe ? badge("Réponse de l'équipe", "equipe") : null,
        a.validee ? badge("Validée par l'équipe", "ok") : null,
        a.masquee ? badge(`Masquée${a.signalements ? ` · ${a.signalements} signalement(s)` : ""}`, "ko") : null,
        el("span", { class: "muted", text: ` · ${dateFr(a.cree_le)}` })),
      repliable(texteRiche(a.texte), a.solution), actions);
  }

  function signaler(url) {
    const b = el("button", { type: "button", class: "lien muted", text: "Signaler" });
    b.addEventListener("click", async () => {
      if (!confirm("Signaler ce message à l'équipe (contenu déplacé ou erroné) ?")) return;
      try { await envoyer(url); b.replaceWith(el("span", { class: "muted small", text: "Signalé, merci." })); } catch (e) { alert(e.message); }
    });
    return b;
  }

  function fil(q, ouvert) {
    const reponses = el("ol", { class: "fil-reponses" }, ...q.reponses.map((a) => reponse(q, a)));
    const repondre = el("form", { class: "fil-repondre" },
      el("label", {}, "Votre réponse", el("textarea", { name: "texte", rows: "3", maxlength: "5000", required: true })),
      el("label", { class: "check" }, el("input", { type: "checkbox", name: "solution" }), " Ma réponse montre une partie de la solution"),
      el("p", { class: "row" }, el("button", { type: "submit", class: "button", text: equipe ? "Répondre (équipe)" : "Répondre" })));
    repondre.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const bouton = repondre.querySelector("button");
      bouton.disabled = true;
      try {
        const d = await envoyer(`/questions/${q.id}/reponses`, { texte: repondre.texte.value, solution: repondre.solution.checked });
        remplacer(d.question, true);
      } catch (e) { alert(e.message); bouton.disabled = false; }
    });
    const actions = el("div", { class: "fil-actions" });
    if (!q.moi) {
      actions.append(el("button", { type: "button", class: `lien${q.moi_meme ? " actif" : ""}`, "aria-pressed": String(q.moi_meme),
        text: q.moi_meme ? "J'ai la même question ✓ (retirer)" : "J'ai la même question" }));
      actions.lastChild.addEventListener("click", () => agir(`/questions/${q.id}/meme`, { valeur: !q.moi_meme }));
    }
    if (q.moi || equipe) {
      actions.append(el("button", { type: "button", class: "lien", text: q.resolue ? "Rouvrir la question" : "Marquer comme résolue" }));
      actions.lastChild.addEventListener("click", () => agir(`/questions/${q.id}/resolue`, { valeur: !q.resolue }));
    }
    if (equipe) {
      actions.append(el("button", { type: "button", class: "lien", text: q.masquee ? "Rétablir la question" : "Masquer la question" }));
      actions.lastChild.addEventListener("click", () => agir(`/questions/${q.id}/masquer`, { valeur: !q.masquee }));
    } else if (!q.moi) {
      actions.append(signaler(`/questions/${q.id}/signaler`));
    }
    const nb = q.reponses.length;
    return el("details", { class: `fil${q.resolue ? " resolue" : ""}${q.masquee ? " masquee" : ""}`, id: `question-${q.id}`, open: ouvert },
      el("summary", {},
        el("span", { class: "fil-titre", text: q.titre }),
        q.resolue ? badge("Résolue", "ok") : null,
        q.reponse_equipe ? badge("Réponse de l'équipe", "equipe") : null,
        q.prive ? badge("Privée", "") : null,
        q.meme ? badge(`${q.meme} ${q.meme > 1 ? "ont" : "a"} la même question`, "") : null,
        q.masquee ? badge(`Masquée${q.signalements ? ` · ${q.signalements} signalement(s)` : ""}`, "ko") : null,
        el("span", { class: "fil-compte muted small", text: `${nb} réponse${nb > 1 ? "s" : ""}` })),
      el("p", { class: "fil-meta" }, el("strong", { text: q.auteur }), el("span", { class: "muted", text: ` · ${dateFr(q.cree_le)}` })),
      repliable(texteRiche(q.texte), q.solution),
      equipe && q.journal ? el("details", { class: "fil-journal" }, el("summary", { text: "Dernière vérification jointe (équipe seulement)" }), el("pre", {}, el("code", { text: q.journal }))) : null,
      reponses, actions, repondre);
  }

  let questions = [];
  function afficher(ouvrir) {
    if (!questions.length) {
      liste.replaceChildren(el("p", { class: "muted", text: "Aucune question pour l'instant : soyez le premier à demander, d'autres se posent sûrement la même." }));
      return;
    }
    liste.replaceChildren(...questions.map((q) => fil(q, q.id === ouvrir)));
  }
  function remplacer(q, ouvrir) {
    const i = questions.findIndex((x) => x.id === q.id);
    if (i >= 0) questions[i] = q; else questions.unshift(q);
    afficher(ouvrir ? q.id : null);
  }
  async function agir(url, body) {
    try { remplacer((await envoyer(url, body)).question, true); } catch (e) { alert(e.message); }
  }

  const ouvrirFormulaire = (bloque) => {
    form.hidden = false;
    if (bloque && form.joindre_verification) form.joindre_verification.checked = true;
    form.titre.focus();
  };
  const similaires = form.querySelector(".question-similaires");
  let attente = null;
  const suggerer = () => {
    const trouvees = ressemblantes(questions.filter((q) => !q.moi), form.titre.value, form.texte.value);
    if (!trouvees.length) { similaires.hidden = true; return; }
    similaires.replaceChildren(
      el("p", { class: "small", text: "Ces questions ressemblent à la vôtre : la réponse y est peut-être déjà." }),
      el("ul", {}, ...trouvees.map((q) => {
        const b = el("button", { type: "button", class: "lien", text: q.titre });
        b.addEventListener("click", () => {
          const d = document.getElementById(`question-${q.id}`);
          if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); }
        });
        return el("li", {}, b, q.resolue ? badge("Résolue", "ok") : null, q.reponse_equipe ? badge("Réponse de l'équipe", "equipe") : null);
      })));
    similaires.hidden = false;
  };
  for (const champ of [form.titre, form.texte]) {
    champ.addEventListener("input", () => { clearTimeout(attente); attente = setTimeout(suggerer, 250); });
  }
  section.querySelector('[data-questions="poser"]').addEventListener("click", () => ouvrirFormulaire(false));
  form.querySelector('[data-questions="annuler"]').addEventListener("click", () => { form.hidden = true; });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const bouton = form.querySelector("button[type=submit]");
    bouton.disabled = true;
    status.hidden = true;
    try {
      const d = await envoyer(`/questions/${encodeURIComponent(module)}`, {
        titre: form.titre.value, texte: form.texte.value, prive: form.prive.checked, solution: form.solution.checked,
        joindre_verification: Boolean(form.joindre_verification?.checked),
      });
      form.reset();
      form.hidden = true;
      similaires.hidden = true;
      remplacer(d.question, true);
      document.getElementById(`question-${d.question.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      status.textContent = e.message;
      status.hidden = false;
    } finally {
      bouton.disabled = false;
    }
  });

  fetch(`${base}/questions/${encodeURIComponent(module)}`, { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d) return; // sans session (ou sans accès) : pas de rubrique
      equipe = d.equipe;
      questions = d.questions;
      section.hidden = false;
      for (const l of document.querySelectorAll(".questions-lien")) l.hidden = false;
      const cible = /^#question-(\d+)$/.exec(location.hash);
      afficher(cible ? Number(cible[1]) : null);
      if (cible) document.getElementById(`question-${cible[1]}`)?.scrollIntoView({ block: "start" });
      // « Je suis bloqué » dans le lab : le formulaire s'ouvre, avec la dernière vérification jointe
      if (new URLSearchParams(location.search).has("bloque")) {
        section.scrollIntoView({ block: "start" });
        ouvrirFormulaire(true);
      } else if (location.hash === "#questions") {
        section.scrollIntoView({ block: "start" });
      }
    })
    .catch(() => {});
}

// --- Avis sur le module (phase de test) : demandé à l'étudiant connecté, jamais bloquant.
// Sans avis, « Module suivant » propose d'abord de le donner ; « Plus tard » vaut pour la session.
const NOTES_TEXTE = { 1: "Pas utile", 2: "Peu utile", 3: "Utile", 4: "Très utile", 5: "Indispensable" };

function setupAvis() {
  const section = document.getElementById("avis");
  if (!section) return;
  const form = section.querySelector("form");
  const status = section.querySelector(".avis-status");
  const button = form.querySelector("button[type=submit]");
  const texte = section.querySelector(".avis-note-texte");
  const dialog = document.querySelector("dialog.avis-rappel");
  const url = `/api/comptes/avis/${encodeURIComponent(section.dataset.module)}`;
  const plusTardCle = `rosacademy.avisPlusTard.${section.dataset.module}`;
  let actif = false;
  let donne = false;
  let destination = "";

  const dire = (message, kind = "") => {
    status.textContent = message;
    status.className = `avis-status ${kind}`;
    status.hidden = false;
  };
  const remplir = (a) => {
    for (const input of form.querySelectorAll("input[type=radio]")) {
      input.checked = (input.name === "note" && Number(input.value) === a.note) ||
        (input.name === "difficulte" && input.value === a.difficulte);
    }
    form.commentaire.value = a.commentaire || "";
    texte.textContent = NOTES_TEXTE[a.note] || "";
    const le = new Date(a.modifie_le).toLocaleDateString("fr-FR");
    dire(`Merci ! Votre avis du ${le} est enregistré. Vous pouvez le modifier à tout moment.`, "ok");
    button.textContent = "Modifier mon avis";
    donne = true;
  };

  form.addEventListener("change", (ev) => {
    if (ev.target.name === "note") texte.textContent = NOTES_TEXTE[ev.target.value] || "";
  });
  fetch(url, { credentials: "same-origin" })
    .then((r) => {
      if (!r.ok) return null; // sans session : pas d'encart
      actif = true;
      section.hidden = false;
      for (const l of document.querySelectorAll(".avis-lien")) l.hidden = false;
      return r.json().then((d) => d.avis && remplir(d.avis));
    })
    .catch(() => {});

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const note = form.querySelector("input[name=note]:checked");
    const difficulte = form.querySelector("input[name=difficulte]:checked");
    if (!note || !difficulte) return dire("Choisissez une note et une difficulté.", "ko");
    button.disabled = true;
    try {
      const r = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: Number(note.value), difficulte: difficulte.value, commentaire: form.commentaire.value }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) return dire(data.erreur || "Votre avis n'a pas pu être enregistré, réessayez dans un instant.", "ko");
      remplir(data.avis);
      if (destination) location.href = destination; // envoyé depuis le rappel : on continue vers la suite
    } catch {
      dire("Votre avis n'a pas pu être enregistré, réessayez dans un instant.", "ko");
    } finally {
      button.disabled = false;
    }
  });

  const plusTard = {
    lire: () => { try { return sessionStorage.getItem(plusTardCle); } catch { return null; } },
    ecrire: () => { try { sessionStorage.setItem(plusTardCle, "1"); } catch { /* navigation privée */ } },
  };
  for (const a of document.querySelectorAll(".prev-next .suivant, [data-suivante]")) {
    a.addEventListener("click", (ev) => {
      const href = a.getAttribute("href") || "";
      if (!actif || donne || !href.startsWith("/modules/") || plusTard.lire() || !dialog?.showModal) return;
      ev.preventDefault();
      destination = href;
      dialog.showModal();
    });
  }
  dialog?.querySelector('[data-avis="donner"]').addEventListener("click", () => {
    dialog.close();
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    (form.querySelector("input[name=note]:checked") || form.querySelector("#avis-note-5"))?.focus({ preventScroll: true });
  });
  dialog?.querySelector('[data-avis="plus-tard"]').addEventListener("click", () => {
    plusTard.ecrire();
    dialog.close();
    location.href = destination;
  });
}

/**
 * Vidéos muettes de l'accueil ([data-video-auto]) : l'image d'attente suffit sur petit écran, en
 * économie de données ou avec « réduire les animations » (rien n'est téléchargé) ; sinon la vidéo
 * se lance quand elle est visible et s'arrête hors de l'écran ou onglet caché.
 */
function setupVideos() {
  const videos = [...document.querySelectorAll("video[data-video-auto]")];
  if (!videos.length) return;
  const calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const petit = window.matchMedia("(max-width: 720px)").matches;
  if (calme || petit || navigator.connection?.saveData || !("IntersectionObserver" in window)) return;
  const visibles = new Set();
  const jouer = (v) => {
    v.muted = true;
    v.play().catch(() => {}); // lecture refusée : l'image d'attente reste
  };
  const observateur = new IntersectionObserver((entrees) => {
    for (const e of entrees) {
      if (e.isIntersecting) { visibles.add(e.target); if (!document.hidden) jouer(e.target); }
      else { visibles.delete(e.target); e.target.pause(); }
    }
  }, { threshold: 0.2 });
  for (const v of videos) {
    v.preload = "auto";
    observateur.observe(v);
  }
  document.addEventListener("visibilitychange", () => {
    for (const v of visibles) document.hidden ? v.pause() : jouer(v);
  });
}

setupVideos();
setupTabs();
setupCopy();
setupCatalogue();
setupModule();
setupProgression();
setupQcm();
setupQuestions();
setupAvis();
setupSideBySide();
