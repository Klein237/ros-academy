// Onglets Python / C++, bouton Copier, QCM corrigé par le serveur (via Comptes).

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

setupTabs();
setupCopy();
setupQcm();
