"use strict";
// Pages sans calcul : texte (LIMITES.md, copié par construire_web.py) et pages encore réservées au bureau.

(() => {
  const { el } = App;

  App.genre("texte", async (contenu, page) => {
    const zone = el("article", { class: "texte" }, App.message("info", "Chargement…"));
    contenu.append(zone);
    try {
      const r = await fetch(page.source, { cache: "no-cache" });
      if (!r.ok) throw new Error(r.status);
      zone.innerHTML = App.markdown(await r.text()); // markdown() échappe le texte avant de poser ses balises
    } catch (e) {
      zone.replaceChildren(App.message("erreur", "Le texte n'a pas pu être chargé. Il est aussi sur GitHub : "),
        el("a", { href: App.DEPOT + "/blob/main/" + page.source, texte: page.source }));
    }
  });

  App.genre("references", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: "Normes sur lesquelles l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année sont donnés : les textes sont protégés (AFNOR) et se consultent chez l'éditeur. Avant tout usage professionnel, vérifiez les valeurs et les clauses dans le texte officiel et dans l'annexe nationale du pays." }));
    if (!pret) return contenu.append(App.message("info", "Le calcul se charge : les références apparaîtront dans quelques secondes."));
    const r = App.calculer("references");
    if (!r.ok) return contenu.append(App.message("erreur", r.erreur));
    contenu.append(el("div", { class: "cartes" }, r.sortie.map((n) => el("section", { class: "carte" },
      el("h2", { texte: n.numero }), el("p", { class: "legende", texte: n.annee }), el("p", { texte: n.titre }),
      el("p", { class: "legende", texte: "Dans l'application : " + n.role })))));
  });

  App.genre("bureau", (contenu, page) => {
    contenu.append(
      el("h1", { texte: page.titre }),
      el("p", { class: "intro", texte: page.texte }),
      App.message("info", "Cette page est déjà dans l'application de bureau pour Windows. Elle arrive dans le navigateur dans une prochaine version."),
      el("p", { class: "ligne" },
        el("a", { class: "bouton primaire", href: App.DEPOT + "/releases/latest", texte: "Télécharger pour Windows" }),
        el("a", { class: "bouton secondaire", href: "#/accueil", texte: "Voir les pages disponibles ici" })),
      el("figure", { class: "capture" },
        el("img", { src: `captures/${page.capture}.jpg`, alt: `Page ${page.titre} dans l'application de bureau`, loading: "lazy", width: "1400" }),
        el("figcaption", { class: "legende", texte: `La page ${page.titre} dans l'application de bureau.` })));
  });
})();
