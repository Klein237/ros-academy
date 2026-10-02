// Onglets Python / C++, bouton Copier, QCM corrigé par le serveur.

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

function setupQcm() {
  for (const form of document.querySelectorAll("form.qcm")) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const reponses = {};
      for (const fs of form.querySelectorAll("fieldset[data-question]")) {
        reponses[fs.dataset.question] = [...fs.querySelectorAll("input:checked")].map((i) => Number(i.value));
      }
      const result = form.querySelector(".qcm-result");
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        const r = await fetch(`/api/contenus/modules/${encodeURIComponent(form.dataset.module)}/qcm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reponses }),
        });
        if (!r.ok) throw new Error(String(r.status));
        const data = await r.json();
        for (const q of data.questions) {
          const fb = form.querySelector(`fieldset[data-question="${CSS.escape(q.id)}"] .feedback`);
          fb.hidden = false;
          fb.className = `feedback ${q.juste ? "ok" : "ko"}`;
          fb.textContent = q.juste ? `Juste. ${q.explication}` : "Pas tout à fait : relisez le cours.";
        }
        result.textContent = `Note : ${String(data.note).replace(".", ",")} / 20 (${data.justes} réponse${data.justes > 1 ? "s" : ""} juste${data.justes > 1 ? "s" : ""} sur ${data.total})`;
      } catch {
        result.textContent = "La correction est indisponible, réessayez dans un instant.";
      }
      result.hidden = false;
      button.disabled = false;
    });
  }
}

setupTabs();
setupCopy();
setupQcm();
