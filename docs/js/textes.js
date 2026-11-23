"use strict";
// Pages sans calcul : texte (LIMITES.md, copié par construire_web.py) et pages encore réservées au bureau.

(() => {
  const { el } = App;

  // Section « Vérifications indépendantes » de la page Limites : cas à solution exacte (services/verifications.py), calculés
  // à l'ouverture de la page seulement (le calcul des poutres demande scipy, chargé à ce moment-là).
  function verifications(zone, page, { pret, perime }) {
    const corps = el("div", {});
    zone.append(el("section", { class: "verifications", "aria-labelledby": "verif-titre" },
      el("h2", { id: "verif-titre", texte: "Vérifications indépendantes" }),
      el("p", { texte: "Chaque ligne compare MecaStruct à une formule fermée de manuel, refaite à la main dans le code : aucune valeur ne vient d'une norme ni de la mémoire. L'écart est relatif ; la ligne est conforme quand il ne dépasse pas la tolérance (1e-9, soit de l'arrondi de calcul). Ces calculs sont refaits à chaque ouverture de cette page." }),
      corps));

    const tableau = (lignes) => {
      const groupes = [...new Set(lignes.map((l) => l.page))];
      const corpsTable = [];
      for (const g of groupes) {
        corpsTable.push(el("tr", { class: "verif-groupe" }, el("th", { scope: "colgroup", colspan: "6", texte: g })));
        for (const l of lignes.filter((x) => x.page === g)) {
          corpsTable.push(el("tr", { "data-id": l.id },
            el("td", {}, el("strong", { texte: l.titre }),
              l.donnees ? el("div", { class: "legende", texte: l.donnees }) : null,
              l.reference ? el("div", { class: "legende", texte: l.reference }) : null,
              l.erreur ? el("div", { class: "ecart", texte: l.erreur }) : null),
            el("td", { texte: l.formule }),
            el("td", { class: "num", texte: `${l.cible_txt} ${l.unite}` }),
            el("td", { class: "num", texte: `${l.calculee_txt} ${l.unite}` }),
            el("td", { class: "num", texte: l.ecart_txt }),
            el("td", { class: "verdict " + (l.ok ? "succes" : "erreur"), texte: l.ok ? "✓ conforme" : "✗ hors tolérance" })));
        }
      }
      return el("div", { class: "defile" }, el("table", { "aria-label": "Vérifications indépendantes de MecaStruct" },
        el("thead", {}, el("tr", {}, ["Calcul", "Formule de manuel", "Valeur attendue", "Valeur MecaStruct", "Écart relatif", "Verdict"].map((t) => el("th", { scope: "col", texte: t })))),
        el("tbody", {}, corpsTable)));
    };

    const afficher = async () => {
      if (perime()) return;
      corps.replaceChildren(App.message("info", "Calcul des vérifications… (la première fois, les bibliothèques de calcul se chargent : quelques secondes)"));
      const prete = await App.preparer(page);
      if (perime()) return;
      if (!prete) {
        corps.replaceChildren(App.messageEchec("Les bibliothèques de calcul n'ont pas pu se charger. Vérifiez la connexion Internet, puis réessayez."));
        return;
      }
      const r = App.calculer("verifications");
      if (perime()) return;
      if (!r.ok) {
        corps.replaceChildren(App.message("erreur", r.erreur));
        return;
      }
      const { lignes, resume } = r.sortie;
      const n = (k, mot) => `${k} ${mot}${k > 1 ? "s" : ""}`;
      corps.replaceChildren(
        App.message(resume.tout_ok ? "succes" : "erreur",
          resume.tout_ok
            ? `Les ${resume.total} vérifications sont conformes. Écart relatif maximal : ${resume.ecart_max_txt}.`
            : `${n(resume.total - resume.ok, "vérification")} sur ${resume.total} hors tolérance : ne vous fiez pas aux pages concernées avant correction.`),
        tableau(lignes));
    };

    if (pret) afficher();
    else {
      corps.append(App.attente("Le calcul se charge : les vérifications apparaîtront dans quelques secondes."));
      document.addEventListener("mecastruct:pret", afficher, { once: true });
    }
  }

  App.genre("texte", async (contenu, page, { pret, perime = () => false } = {}) => {
    const zone = el("article", { class: "texte" }, App.message("info", "Chargement…"));
    contenu.append(el("h1", { texte: page.titre }), zone); // le texte markdown commence au niveau h2
    try {
      const r = await fetch(page.source, { cache: "no-cache" });
      if (perime()) return; // l'utilisateur a changé de page pendant le chargement : rien à ajouter
      if (!r.ok) throw new Error(r.status);
      const texte = await r.text();
      if (perime()) return;
      zone.innerHTML = App.markdown(texte); // markdown() échappe le texte avant de poser ses balises
      if (page.verifications) verifications(zone, page, { pret, perime });
    } catch (e) {
      if (perime()) return;
      zone.replaceChildren(App.message("erreur", "Le texte n'a pas pu être chargé. Il est aussi sur GitHub : "),
        el("a", { href: App.DEPOT + "/blob/main/" + page.source, texte: page.source }));
    }
  });

  App.genre("references", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: "Normes et cours sur lesquels l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année sont donnés : les textes des normes sont protégés (AFNOR) et se consultent chez l'éditeur, les cours appartiennent à leurs auteurs. Les mentions sont celles imprimées sur les documents (« non indiqué » sinon). Avant tout usage professionnel, vérifiez les valeurs et les clauses dans le texte officiel et dans l'annexe nationale du pays." }));
    if (!pret) return contenu.append(App.attente("Le calcul se charge : les références apparaîtront dans quelques secondes.", page));
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
