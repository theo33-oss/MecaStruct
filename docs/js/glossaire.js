"use strict";
// Glossaire des symboles : un tableau symbole / nom / unité / pages, filtré au fil de la frappe. Les entrées viennent du calcul
// « glossaire » du pont (services/glossaire.py : libellés, unités et aides des formulaires, variables des fiches de formules).

(() => {
  const { el } = App;

  // Comparaison sans accents ni majuscules, lettres grecques comprises (« sigma » trouve « σ ») : celle de la recherche globale.
  const norme = (t) => (App.recherche && App.recherche.norme ? App.recherche.norme(t) : String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase());

  // Le symbole en KaTeX (texte brut si KaTeX n'est pas chargé : le texte du symbole reste lisible et cherchable).
  function symbole(e) {
    const s = el("span", { class: "symbole", "data-symbole": e.symbole });
    if (window.katex) {
      try { katex.render(e.latex, s, { displayMode: false, throwOnError: false, strict: "ignore" }); return s; } catch (err) { /* texte brut */ }
    }
    s.textContent = e.symbole;
    return s;
  }

  const lignePages = (pages) => {
    const liens = [];
    pages.forEach((id, i) => {
      const p = App.page(id);
      if (!p) return;
      if (i) liens.push(", ");
      liens.push(el("a", { href: "#/" + id, texte: p.titre }));
    });
    return liens;
  };

  App.genre("glossaire", async (contenu, page, { pret, perime = () => false }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) return contenu.append(App.attente("Le calcul se charge : le glossaire apparaîtra dans quelques secondes.", page));
    const attente = App.message("info", "Chargement des formulaires (scipy, shapely)… quelques secondes la première fois.");
    contenu.append(attente);
    const prete = await App.preparer(page);
    if (perime()) return;
    if (!prete) return attente.replaceWith(App.messageEchec("Les bibliothèques de cette page n'ont pas pu se charger. Vérifiez la connexion Internet, puis réessayez."));
    attente.remove();
    const r = App.calculer("glossaire");
    if (!r.ok) return contenu.append(App.message("erreur", r.erreur));
    const entrees = r.sortie.entrees;

    const champ = el("input", { type: "search", id: "glossaire-filtre", autocomplete: "off", placeholder: "Symbole, nom, unité ou page (ex. : σ, module, MPa, roulements)" });
    const etat = el("p", { class: "legende", role: "status", "aria-live": "polite" });
    const vide = App.message("info", "Aucun symbole ne correspond à ce filtre.");
    vide.hidden = true;

    const lignes = entrees.map((e) => {
      const titres = e.pages.map((id) => (App.page(id) || {}).titre || id);
      const tr = el("tr", {},
        el("th", { scope: "row" }, symbole(e)),
        el("td", {}, el("span", { texte: e.nom }), e.aide ? el("div", { class: "legende", texte: e.aide }) : null),
        el("td", { class: "unite", texte: e.unite || "–" }),
        el("td", {}, lignePages(e.pages)));
      return { tr, texte: norme([e.symbole, e.nom, e.unite, e.aide, ...titres].join(" ")) };
    });

    const filtrer = () => {
      const mots = norme(champ.value).split(" ").filter(Boolean);
      let n = 0;
      for (const l of lignes) {
        const ok = mots.every((m) => l.texte.includes(m));
        l.tr.hidden = !ok;
        if (ok) n++;
      }
      vide.hidden = n > 0;
      etat.textContent = mots.length ? `${n} symbole${n > 1 ? "s" : ""} sur ${lignes.length}` : `${lignes.length} symboles`;
    };
    champ.addEventListener("input", filtrer);

    contenu.append(
      el("p", { class: "legende", texte: "Chaque entrée est lue dans les libellés, les unités et les aides des champs de l'application, et dans les variables du « Formulaire rapide ». Une entrée par sens : un même symbole peut désigner deux grandeurs selon la page. L'unité est celle des champs de saisie ; les formules du « Formulaire rapide » sont en unités du Système international." }),
      el("label", { for: "glossaire-filtre" }, "Filtrer le glossaire", champ),
      etat,
      el("div", { class: "defile" }, el("table", { class: "glossaire", "aria-label": "Glossaire des symboles" },
        el("thead", {}, el("tr", {}, ["Symbole", "Nom", "Unité", "Pages"].map((t) => el("th", { scope: "col", texte: t })))),
        el("tbody", {}, lignes.map((l) => l.tr)))),
      vide);
    filtrer();
  });
})();
