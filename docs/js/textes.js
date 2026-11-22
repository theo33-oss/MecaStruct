"use strict";
// Pages sans calcul : texte (LIMITES.md, copié par construire_web.py) et pages encore réservées au bureau.

(() => {
  const { el } = App;

  App.genre("texte", async (contenu, page, { perime = () => false } = {}) => {
    const zone = el("article", { class: "texte" }, App.message("info", "Chargement…"));
    contenu.append(el("h1", { texte: page.titre }), zone); // le texte markdown commence au niveau h2
    try {
      const r = await fetch(page.source, { cache: "no-cache" });
      if (perime()) return; // l'utilisateur a changé de page pendant le chargement : rien à ajouter
      if (!r.ok) throw new Error(r.status);
      const texte = await r.text();
      if (perime()) return;
      zone.innerHTML = App.markdown(texte); // markdown() échappe le texte avant de poser ses balises
    } catch (e) {
      if (perime()) return;
      zone.replaceChildren(App.message("erreur", "Le texte n'a pas pu être chargé. Il est aussi sur GitHub : "),
        el("a", { href: App.DEPOT + "/blob/main/" + page.source, texte: page.source }));
    }
  });

  App.genre("references", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: "Normes et cours sur lesquels l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année sont donnés : les textes des normes sont protégés (AFNOR) et se consultent chez l'éditeur, les cours appartiennent à leurs auteurs. Les mentions sont celles imprimées sur les documents (« non indiqué » sinon). Avant tout usage professionnel, vérifiez les valeurs et les clauses dans le texte officiel et dans l'annexe nationale du pays." }));
    if (!pret) return contenu.append(App.attente("Le calcul se charge : les références apparaîtront dans quelques secondes."));
    const r = App.calculer("references");
    if (!r.ok) return contenu.append(App.message("erreur", r.erreur));
    const GENRES = [["norme", "Normes"], ["cours", "Cours (Université de Bordeaux)"], ["document", "Documents techniques et données de matériaux"]];
    for (const [genre, titre] of GENRES) {
      const liste = r.sortie.filter((n) => (n.genre || "norme") === genre);
      if (!liste.length) continue;
      contenu.append(el("h2", { texte: titre }), el("div", { class: "cartes" }, liste.map((n) => el("section", { class: "carte" },
        el("h3", { texte: n.numero }), el("p", { class: "legende", texte: n.annee }), el("p", { texte: n.titre }),
        el("p", { class: "legende", texte: "Dans l'application : " + n.role }),
        n.lien ? el("p", {}, el("a", { href: n.lien, target: "_blank", rel: "noopener noreferrer", texte: "Ouvrir la source" })) : null))));
    }
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
