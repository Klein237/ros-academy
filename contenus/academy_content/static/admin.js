// Espace d'administration : tableau de bord, éditeur de module, parcours.

const root = document.getElementById("admin");

async function api(method, path, body) {
  const r = await fetch(`/admin/api${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (r.status === 401) {
    location.reload();
    throw new Error("Session expirée");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.erreur || `Erreur ${r.status}`);
  return data;
}

function el(tag, props = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "text") e.textContent = v;
    else if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v !== undefined && v !== null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c !== null && c !== undefined && c !== false) e.append(c);
  return e;
}

const fmtDate = (iso) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

// --- Tableau de bord ------------------------------------------------------------------

async function tableau() {
  let polling = null;

  function renderPublication(pub, aPublier) {
    const etat = document.getElementById("pub-etat");
    const bouton = document.getElementById("pub-lancer");
    const texts = {
      aucune: aPublier ? "Le brouillon contient des modifications non publiées." : "Tout est publié.",
      en_cours: `Publication en cours${pub.module_en_cours ? ` : test du module ${pub.module_en_cours}` : ""}… (${pub.duree} s)`,
      ok: `Dernière publication réussie (${pub.duree} s).${aPublier ? " De nouvelles modifications attendent." : ""}`,
      echec: "Dernière publication refusée : les étudiants voient toujours la version précédente.",
    };
    etat.textContent = texts[pub.etat] || pub.etat;
    etat.className = pub.etat === "echec" ? "form-error" : "muted";
    bouton.disabled = pub.etat === "en_cours" || !aPublier;
    const box = document.getElementById("pub-rapports");
    box.replaceChildren();
    if (pub.erreurs.length) {
      box.append(el("h3", { text: "Erreurs de format" }), el("ul", { class: "errors" }, ...pub.erreurs.map((e) => el("li", { text: e }))));
    }
    for (const r of pub.rapports) {
      box.append(
        el("h3", {}, `Module ${r.module} `, el("span", { class: `badge ${r.ok ? "ok" : "ko"}`, text: r.ok ? "tests réussis" : "tests en échec" })),
        el("pre", { class: "report", text: r.resume }),
        el("details", {}, el("summary", { text: "Journal complet" }), el("pre", { class: "report", text: r.journal })),
      );
    }
    if (pub.etat === "en_cours" && !polling) polling = setTimeout(refresh, 2000);
  }

  async function refresh() {
    polling = null;
    const etat = await api("GET", "/etat");
    const tbody = document.querySelector("#modules tbody");
    tbody.replaceChildren(
      ...etat.modules.map((m) =>
        el("tr", {},
          el("td", {}, el("code", { text: m.id })),
          el("td", { text: m.titre }),
          el("td", {},
            m.erreurs.length ? el("span", { class: "badge ko", title: m.erreurs.join("\n"), text: `${m.erreurs.length} erreur(s)` })
              : el("span", { class: "badge ok", text: "valide" }),
            " ",
            m.modifie ? el("span", { class: "badge modif", text: "modifié, non publié" }) : null,
          ),
          el("td", { class: "actions" },
            el("a", { class: "button", href: `/admin/modules/${encodeURIComponent(m.id)}/`, text: "Éditer" }), " ",
            el("a", { class: "button", href: `/admin/apercu/modules/${encodeURIComponent(m.id)}/`, text: "Aperçu" }),
          ),
        ),
      ),
    );
    document.getElementById("parcours").replaceChildren(
      ...etat.parcours.map((p) =>
        el("li", {}, el("a", { href: `/admin/parcours/${encodeURIComponent(p.id)}/`, text: p.titre }),
          el("span", { class: "muted small", text: ` — ${p.modules.length} module(s) : ${p.modules.join(", ")}` })),
      ),
    );
    renderPublication(etat.publication, etat.a_publier);
    const hist = await api("GET", "/historique");
    document.querySelector("#historique tbody").replaceChildren(
      ...hist.commits.map((c, i) =>
        el("tr", {},
          el("td", { text: fmtDate(c.date) }),
          el("td", {}, c.message, c.publie ? el("span", { class: "badge ok", text: " version publiée" }) : null),
          el("td", { class: "actions" }, i === 0 ? null : el("button", {
            class: "button", type: "button", text: "Restaurer",
            onclick: async () => {
              if (!confirm(`Restaurer le brouillon dans l'état du ${fmtDate(c.date)} ?`)) return;
              try { await api("POST", "/historique/restaurer", { sha: c.sha }); refresh(); } catch (e) { alert(e.message); }
            },
          })),
        ),
      ),
    );
  }

  document.getElementById("pub-lancer").addEventListener("click", async () => {
    try {
      const pub = await api("POST", "/publication");
      renderPublication(pub, true);
    } catch (e) {
      alert(e.message);
    }
  });

  const form = document.getElementById("nouveau-module");
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const err = form.querySelector(".form-error");
    err.hidden = true;
    const data = Object.fromEntries(new FormData(form));
    try {
      await api("POST", "/modules", data);
      location.href = `/admin/modules/${encodeURIComponent(data.id)}/`;
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  });

  await refresh();
}

// --- Éditeur de module ----------------------------------------------------------------

function stripFrontMatter(text) {
  if (!text.startsWith("---\n")) return text;
  const end = text.indexOf("\n---\n", 4);
  return end === -1 ? text : text.slice(end + 5);
}

async function editeur() {
  const moduleId = root.dataset.module;
  const area = document.getElementById("contenu");
  const qcmBox = document.getElementById("qcm-editor");
  const status = document.getElementById("etat-fichier");
  const saveBtn = document.getElementById("enregistrer");
  const delBtn = document.getElementById("supprimer-fichier");
  const preview = document.getElementById("apercu");
  let current = null;
  let saved = "";
  let previewTimer = null;

  const dirty = () => current !== null && current !== "qcm.yaml#form" && area.value !== saved;
  const setStatus = (text) => (status.textContent = text);

  function showErrors(erreurs) {
    const box = document.getElementById("erreurs");
    box.replaceChildren(...erreurs.map((e) => el("li", { text: e })));
    box.hidden = erreurs.length === 0;
  }

  async function loadFiles() {
    const data = await api("GET", `/modules/${moduleId}/fichiers`);
    showErrors(data.erreurs);
    const list = document.getElementById("fichiers");
    list.replaceChildren();
    // Ordre de lecture d'un module : cours, QCM, lab guidé, exercice, puis le reste ; par dossier.
    const rank = (f) => ["index.md", "qcm.yaml", "lab", "exercice", "lab_test.sh"].indexOf(f.split("/")[0]) >>> 0;
    const dirOf = (f) => (f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "");
    const fichiers = [...data.fichiers].sort((a, b) =>
      rank(a) - rank(b) || dirOf(a).localeCompare(dirOf(b)) || a.localeCompare(b));
    let lastDir = null;
    for (const f of fichiers) {
      const dir = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "";
      if (dir !== lastDir) {
        if (dir) list.append(el("li", { class: "dir", text: `${dir}/` }));
        lastDir = dir;
      }
      list.append(el("li", {}, el("button", {
        type: "button", "data-path": f, "aria-current": String(f === current),
        text: f.slice(dir ? dir.length + 1 : 0), title: f, onclick: () => open(f),
      })));
      if (f === "qcm.yaml") {
        list.append(el("li", {}, el("button", {
          type: "button", "data-path": "qcm.yaml#form", "aria-current": String(current === "qcm.yaml#form"),
          text: "↳ QCM (formulaire)", onclick: () => open("qcm.yaml#form"),
        })));
      }
    }
  }

  function updatePreview() {
    clearTimeout(previewTimer);
    if (!current || !current.endsWith(".md")) {
      preview.replaceChildren(el("p", { class: "muted", text: "L'aperçu s'affiche pour les fichiers Markdown." }));
      return;
    }
    previewTimer = setTimeout(async () => {
      try {
        const { html } = await api("POST", "/apercu", { module: moduleId, markdown: stripFrontMatter(area.value) });
        preview.innerHTML = html; // HTML produit par le serveur (Markdown sans HTML brut)
      } catch {
        // l'aperçu n'est pas critique
      }
    }, 350);
  }

  async function open(path) {
    if (dirty() && !confirm(`${current} n'est pas enregistré. Changer de fichier quand même ?`)) return;
    current = path;
    for (const b of document.querySelectorAll("#fichiers button")) b.setAttribute("aria-current", String(b.dataset.path === path));
    document.getElementById("chemin").textContent = path === "qcm.yaml#form" ? "QCM" : path;
    setStatus("");
    if (path === "qcm.yaml#form") {
      area.hidden = true;
      qcmBox.hidden = false;
      saveBtn.disabled = delBtn.disabled = true;
      await renderQcm();
      updatePreview();
      return;
    }
    area.hidden = false;
    qcmBox.hidden = true;
    try {
      const data = await api("GET", `/modules/${moduleId}/fichier?chemin=${encodeURIComponent(path)}`);
      area.value = saved = data.contenu;
      area.disabled = false;
      saveBtn.disabled = false;
      delBtn.disabled = false;
    } catch (e) {
      area.value = saved = "";
      area.disabled = true;
      saveBtn.disabled = delBtn.disabled = true;
      setStatus(e.message);
    }
    updatePreview();
  }

  async function save() {
    if (!current || current === "qcm.yaml#form" || area.disabled) return;
    setStatus("Enregistrement…");
    try {
      const data = await api("PUT", `/modules/${moduleId}/fichier?chemin=${encodeURIComponent(current)}`, { content: area.value });
      saved = area.value;
      showErrors(data.erreurs);
      setStatus(data.erreurs.length ? "Enregistré — le module contient des erreurs" : "Enregistré");
    } catch (e) {
      setStatus(`Échec : ${e.message}`);
    }
  }

  area.addEventListener("input", () => {
    setStatus(dirty() ? "Modifié" : "");
    updatePreview();
  });
  area.addEventListener("keydown", (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
      ev.preventDefault();
      save();
    } else if (ev.key === "Tab" && !ev.shiftKey && !ev.ctrlKey && !ev.altKey && !ev.metaKey) {
      // Tab insère des espaces ; Échap puis Tab pour quitter la zone de texte.
      if (area.dataset.escaped === "1") { area.dataset.escaped = ""; return; }
      ev.preventDefault();
      const indent = /\.(ya?ml|xml|xacro|urdf|launch)$/.test(current || "") ? "  " : "    ";
      area.setRangeText(indent, area.selectionStart, area.selectionEnd, "end");
      area.dispatchEvent(new Event("input"));
    } else if (ev.key === "Escape") {
      area.dataset.escaped = "1";
    }
  });
  saveBtn.addEventListener("click", save);
  delBtn.addEventListener("click", async () => {
    if (!current || !confirm(`Supprimer ${current} ?`)) return;
    try {
      const data = await api("DELETE", `/modules/${moduleId}/fichier?chemin=${encodeURIComponent(current)}`);
      showErrors(data.erreurs);
      current = null;
      area.value = saved = "";
      area.disabled = true;
      saveBtn.disabled = delBtn.disabled = true;
      document.getElementById("chemin").textContent = "Choisissez un fichier";
      await loadFiles();
    } catch (e) {
      alert(e.message);
    }
  });
  document.getElementById("nouveau-fichier").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const chemin = ev.target.chemin.value.trim().replace(/^\/+/, "");
    try {
      await api("PUT", `/modules/${moduleId}/fichier?chemin=${encodeURIComponent(chemin)}`, { content: "" });
      ev.target.reset();
      await loadFiles();
      await open(chemin);
    } catch (e) {
      alert(e.message);
    }
  });
  document.getElementById("supprimer-module").addEventListener("click", async () => {
    if (!confirm(`Supprimer définitivement le module ${moduleId} du brouillon ? (il reste dans l'historique)`)) return;
    try {
      await api("DELETE", `/modules/${moduleId}`);
      location.href = "/admin/";
    } catch (e) {
      alert(e.message);
    }
  });
  window.addEventListener("beforeunload", (ev) => {
    if (dirty()) ev.preventDefault();
  });

  // --- QCM en formulaire
  async function renderQcm() {
    let data;
    try {
      data = await api("GET", `/modules/${moduleId}/qcm`);
    } catch (e) {
      qcmBox.replaceChildren(el("p", { class: "form-error", text: e.message }));
      return;
    }
    const questions = (data.questions || []).map((q) => ({
      id: q.id || "", question: q.question || "", explication: q.explication || "",
      choix: (q.choix || []).map((c) => ({ texte: c.texte || "", correct: Boolean(c.correct) })),
    }));
    const err = el("p", { class: "form-error", role: "alert", hidden: true });

    function draw() {
      qcmBox.replaceChildren(
        ...questions.map((q, i) =>
          el("div", { class: "qcm-question" },
            el("div", { class: "row-actions" },
              el("strong", { text: `Question ${i + 1}` }),
              el("button", { type: "button", class: "link", text: "monter", disabled: i === 0, onclick: () => { [questions[i - 1], questions[i]] = [questions[i], questions[i - 1]]; draw(); } }),
              el("button", { type: "button", class: "link", text: "descendre", disabled: i === questions.length - 1, onclick: () => { [questions[i + 1], questions[i]] = [questions[i], questions[i + 1]]; draw(); } }),
              el("button", { type: "button", class: "link", text: "supprimer", onclick: () => { questions.splice(i, 1); draw(); } }),
            ),
            el("label", {}, "Identifiant (unique, minuscules)", el("input", { value: q.id, oninput: (e) => (q.id = e.target.value) })),
            el("label", {}, "Question", el("textarea", { rows: 2, oninput: (e) => (q.question = e.target.value) }, q.question)),
            el("div", {}, el("span", { class: "small muted", text: "Choix (cochez la ou les bonnes réponses)" }),
              ...q.choix.map((c, j) =>
                el("div", { class: "qcm-choice" },
                  el("input", { type: "checkbox", checked: c.correct, "aria-label": "bonne réponse", onchange: (e) => (c.correct = e.target.checked) }),
                  el("input", { type: "text", value: c.texte, "aria-label": `choix ${j + 1}`, oninput: (e) => (c.texte = e.target.value) }),
                  el("button", { type: "button", class: "link", text: "retirer", onclick: () => { q.choix.splice(j, 1); draw(); } }),
                ),
              ),
              el("button", { type: "button", class: "link", text: "+ ajouter un choix", onclick: () => { q.choix.push({ texte: "", correct: false }); draw(); } }),
            ),
            el("label", {}, "Explication (montrée quand la réponse est juste)", el("textarea", { rows: 2, oninput: (e) => (q.explication = e.target.value) }, q.explication)),
          ),
        ),
        el("p", { class: "row-actions" },
          el("button", { type: "button", class: "button", text: "+ Ajouter une question", onclick: () => { questions.push({ id: `q${questions.length + 1}`, question: "", explication: "", choix: [{ texte: "", correct: true }, { texte: "", correct: false }] }); draw(); } }),
          el("button", {
            type: "button", class: "button primary", text: "Enregistrer le QCM",
            onclick: async () => {
              err.hidden = true;
              try {
                const res = await api("PUT", `/modules/${moduleId}/qcm`, { questions });
                showErrors(res.erreurs);
                setStatus("QCM enregistré");
              } catch (e) {
                err.textContent = e.message;
                err.hidden = false;
              }
            },
          }),
        ),
        err,
      );
    }
    draw();
  }

  await loadFiles();
  await open("index.md");
}

// --- Parcours -------------------------------------------------------------------------

async function parcours() {
  const pid = root.dataset.parcours;
  const form = document.getElementById("parcours-form");
  const err = form.querySelector(".form-error");
  const [data, etat] = await Promise.all([api("GET", `/parcours/${pid}`), api("GET", "/etat")]);
  const titres = Object.fromEntries(etat.modules.map((m) => [m.id, m.titre]));
  const modules = (data.modules || []).map((m) => ({ id: m.id, coef: m.coef ?? 1, partie: m.partie || "", bonus: !!m.bonus }));
  form.titre.value = data.titre || "";
  form.description.value = data.description || "";
  form.accroche.value = data.accroche || "";
  form.statut.value = data.statut || "disponible";
  form.niveau.value = data.niveau || "debutant";
  form.ordre.value = data.ordre ?? 100;
  form.objectifs.value = (data.objectifs || []).join("\n");
  form.prerequis.value = (data.prerequis || []).join("\n");
  const lignes = (v) => v.split("\n").map((l) => l.trim()).filter(Boolean);

  function draw() {
    document.querySelector("#parcours-modules tbody").replaceChildren(
      ...modules.map((m, i) =>
        el("tr", {},
          el("td", {}, el("code", { text: m.id }), " ", titres[m.id] || ""),
          el("td", {}, el("input", { type: "number", min: "0.5", max: "10", step: "0.5", value: m.coef, "aria-label": `coefficient de ${m.id}`, oninput: (e) => (m.coef = Number(e.target.value)) })),
          el("td", {}, el("input", { type: "text", maxlength: "80", value: m.partie, placeholder: "ex. Les bases", "aria-label": `partie de ${m.id}`, oninput: (e) => (m.partie = e.target.value) })),
          el("td", {}, el("input", { type: "checkbox", checked: m.bonus, "aria-label": `${m.id} en bonus`, onchange: (e) => (m.bonus = e.target.checked) })),
          el("td", { class: "actions" },
            el("button", { type: "button", class: "link", text: "monter", disabled: i === 0, onclick: () => { [modules[i - 1], modules[i]] = [modules[i], modules[i - 1]]; draw(); } }), " ",
            el("button", { type: "button", class: "link", text: "descendre", disabled: i === modules.length - 1, onclick: () => { [modules[i + 1], modules[i]] = [modules[i], modules[i + 1]]; draw(); } }), " ",
            el("button", { type: "button", class: "link", text: "retirer", onclick: () => { modules.splice(i, 1); draw(); } }),
          ),
        ),
      ),
    );
    const select = document.getElementById("ajout-module");
    const used = new Set(modules.map((m) => m.id));
    select.replaceChildren(...etat.modules.filter((m) => !used.has(m.id)).map((m) => el("option", { value: m.id, text: `${m.id} — ${m.titre}` })));
    document.getElementById("ajouter").disabled = select.options.length === 0;
  }
  document.getElementById("ajouter").addEventListener("click", () => {
    const id = document.getElementById("ajout-module").value;
    if (id) { modules.push({ id, coef: 1, partie: modules.at(-1)?.partie || "", bonus: false }); draw(); }
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    err.hidden = true;
    try {
      await api("PUT", `/parcours/${pid}`, {
        titre: form.titre.value, description: form.description.value, accroche: form.accroche.value,
        statut: form.statut.value, niveau: form.niveau.value, ordre: Number(form.ordre.value || 100),
        objectifs: lignes(form.objectifs.value), prerequis: lignes(form.prerequis.value), modules,
      });
      document.getElementById("parcours-etat").textContent = "Enregistré (à publier depuis le tableau de bord)";
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  });
  draw();
}

const pages = { tableau, editeur, parcours };
pages[root?.dataset.page]?.().catch((e) => alert(e.message));
