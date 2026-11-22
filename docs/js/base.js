"use strict";
// Matériaux et profilés : consultation, ajouts de l'utilisateur (gardés dans ce navigateur), import et export.

(() => {
  const { el } = App;

  // Ajouts renvoyés par le pont après chaque changement : gardés ici, rejoués au démarrage (app.js).
  const garder = (r) => { if (r.ok && r.sortie.utilisateur) App.memoire.ecrire("utilisateur", r.sortie.utilisateur); };

  // Mini-formulaire de champs { id, libelle, valeur, genre } → { champs, lire() } ; lire() rend la saisie ou null si invalide.
  function formulaire(defs) {
    const entrees = defs.map((d) => {
      const i = el("input", { type: "text", inputmode: d.texte ? undefined : "decimal", value: App.fr(d.valeur) });
      return { d, i };
    });
    return {
      champs: entrees.map(({ d, i }) => el("label", {}, d.libelle, i)),
      lire() {
        const s = {};
        for (const { d, i } of entrees) {
          const v = d.texte ? i.value : App.nombre(i.value);
          i.classList.toggle("invalide", !d.texte && (v === "" || Number.isNaN(v)));
          s[d.id] = v;
        }
        return entrees.some(({ d, i }) => i.classList.contains("invalide")) ? null : s;
      },
    };
  }

  function materiaux(panneau, catalogue) {
    const tableau = el("div"), message = el("div");
    const choisies = new Set(catalogue.categories);
    const recherche = el("input", { type: "search", placeholder: "Nom du matériau", "aria-label": "Rechercher un matériau" });
    const dessiner = () => {
      if (!choisies.size) { // aucune catégorie cochée : aucun matériau (pas « tous »), et le dire
        tableau.replaceChildren(App.message("info", "Aucune catégorie cochée : cochez-en au moins une pour afficher des matériaux."));
        return;
      }
      const r = App.calculer("base.materiaux", { categories: [...choisies], recherche: recherche.value.trim() });
      tableau.replaceChildren(r.ok ? (r.sortie.lignes.length ? App.tableau(r.sortie) : App.message("info", "Aucun matériau ne correspond à cette recherche.")) : App.message("erreur", r.erreur));
    };
    recherche.addEventListener("input", dessiner);
    const cases = catalogue.categories.map((c) => {
      const i = el("input", { type: "checkbox" });
      i.checked = true;
      i.addEventListener("change", () => { if (i.checked) choisies.add(c); else choisies.delete(c); dessiner(); });
      return el("label", { class: "case" }, i, " " + c);
    });
    const f = formulaire([
      { id: "nom", libelle: "Nom", valeur: "Acier utilisateur", texte: true }, { id: "categorie", libelle: "Catégorie", valeur: "Utilisateur", texte: true },
      { id: "E", libelle: "E (GPa)", valeur: 210 }, { id: "G", libelle: "G (GPa), 0 = calculé par E/(2(1+ν))", valeur: 0 }, { id: "nu", libelle: "ν", valeur: 0.3 },
      { id: "Re", libelle: "Re (MPa)", valeur: 300 }, { id: "Rm", libelle: "Rm (MPa)", valeur: 500 }, { id: "alpha", libelle: "α (10⁻⁶/°C)", valeur: 12 },
      { id: "rho", libelle: "ρ (kg/m³)", valeur: 7850 }, { id: "auteur", libelle: "Ajouté par", valeur: "Utilisateur", texte: true },
    ]);
    const suppr = el("select", { "aria-label": "Matériau à supprimer" }, catalogue.utilisateur.map((n) => el("option", { value: n, texte: n })));
    const boutonSuppr = el("button", { type: "button", class: "secondaire", texte: "Supprimer ce matériau utilisateur" });
    const aucun = el("span", { class: "legende", texte: "Aucun matériau utilisateur à supprimer." });
    const majSuppr = () => { // liste vide : rien à supprimer, le bouton ne fait pas semblant
      boutonSuppr.disabled = !suppr.options.length;
      suppr.disabled = !suppr.options.length;
      aucun.hidden = !!suppr.options.length;
    };
    const apres = (r, ok) => {
      garder(r);
      message.replaceChildren(App.message(r.ok ? "succes" : "erreur", r.ok ? r.sortie.message : r.erreur));
      if (r.ok) { const c = App.calculer("base.catalogue").sortie; suppr.replaceChildren(...c.utilisateur.map((n) => el("option", { value: n, texte: n }))); majSuppr(); dessiner(); }
    };
    // Confirmation en ligne (même principe que dans « Comparer des études »), sans boîte de dialogue.
    const demander = (texte, libelle, fn) => message.replaceChildren(el("p", { class: "message avertissement", role: "status" }, texte, " ",
      el("button", { type: "button", class: "primaire petit", texte: libelle, onclick: () => { message.replaceChildren(); fn(); } }), " ",
      el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: () => message.replaceChildren() })));
    boutonSuppr.addEventListener("click", () => {
      const nom = suppr.value;
      if (!nom) return message.replaceChildren(App.message("info", "Aucun matériau utilisateur à supprimer."));
      demander(`Supprimer le matériau « ${nom} » ? Il disparaît de la liste des matériaux de tous les calculs de ce navigateur ; un calcul qui l'utilise devra changer de matériau.`,
        "Supprimer", () => apres(App.calculer("base.supprimer_materiau", { nom })));
    });
    panneau.append(
      el("details", { class: "groupe", open: true }, el("summary", { texte: "Catégories" }), el("div", { class: "grille" }, cases)),
      el("label", { class: "large" }, "Rechercher un matériau", recherche), tableau,
      el("p", { class: "legende", texte: "Les matériaux « Base complémentaire » viennent d'un rapport de synthèse (2026) : valeurs typiques, à vérifier sur la fiche matière du fournisseur avant un usage professionnel." }),
      el("h2", { class: "titre-bloc", texte: "Ajouter un matériau" }),
      el("p", { class: "legende", texte: "Les ajouts restent dans ce navigateur (rien n'est envoyé sur Internet) et sont proposés dans tous les calculs." }),
      el("div", { class: "grille" }, f.champs),
      el("p", { class: "ligne" }, el("button", { type: "button", class: "primaire", texte: "Ajouter / remplacer", onclick: () => {
        const s = f.lire();
        if (!s) return message.replaceChildren(App.message("avertissement", "Corrigez les champs signalés en rouge."));
        apres(App.calculer("base.ajouter_materiau", s));
      } })),
      el("p", { class: "ligne" }, suppr, boutonSuppr, aucun),
      message);
    majSuppr();
    dessiner();
  }

  function profils(panneau, catalogue) {
    const tableau = el("div"), message = el("div");
    const famille = el("select", { "aria-label": "Famille de profilés" }, catalogue.familles.map((n) => el("option", { value: n, texte: n })));
    const dessiner = () => {
      const r = App.calculer("base.profils", { famille: famille.value });
      tableau.replaceChildren(r.ok ? App.tableau(r.sortie) : App.message("erreur", r.erreur));
    };
    famille.addEventListener("change", dessiner);
    const f = formulaire([
      { id: "nom", libelle: "Désignation", valeur: "IPE 210 util", texte: true }, { id: "h", libelle: "h (mm)", valeur: 210 }, { id: "b", libelle: "b (mm)", valeur: 105 },
      { id: "a", libelle: "a, âme (mm)", valeur: 6 }, { id: "e", libelle: "e, aile (mm)", valeur: 9 }, { id: "r", libelle: "r, congé (mm)", valeur: 12 },
      { id: "auteur", libelle: "Ajouté par", valeur: "Utilisateur", texte: true },
    ]);
    panneau.append(el("label", { class: "large" }, "Famille de profilés", famille),
      el("p", { class: "legende", texte: "Convention : Iz = axe fort (= Iy Eurocode), Iy = axe faible." }), tableau,
      el("h2", { class: "titre-bloc", texte: "Ajouter un profilé à la famille choisie" }),
      el("p", { class: "legende", texte: "S, Iz, Iy, W et r sont calculés sur la géométrie simplifiée (épaisseurs constantes)." }),
      el("div", { class: "grille" }, f.champs),
      el("p", { class: "ligne" }, el("button", { type: "button", class: "primaire", texte: "Ajouter le profilé", onclick: () => {
        const s = f.lire();
        if (!s) return message.replaceChildren(App.message("avertissement", "Corrigez les champs signalés en rouge."));
        const r = App.calculer("base.ajouter_profil", { ...s, famille: famille.value });
        garder(r);
        message.replaceChildren(App.message(r.ok ? "succes" : "erreur", r.ok ? r.sortie.message : r.erreur));
        if (r.ok) dessiner();
      } })), message);
    dessiner();
  }

  function matage(panneau, catalogue) {
    panneau.append(el("p", { class: "legende", texte: "Pressions de matage admissibles (MPa) selon la liaison et les conditions." }), App.tableau(catalogue.matage));
  }

  // Abaques de concentration de contrainte (Peterson) : Kt pour d/W (plaque) ou r/d et D/d (arbre épaulé).
  function abaques(panneau) {
    const cat = App.calculer("kt.catalogue").sortie;
    const choix = el("select", { "aria-label": "Abaque" }, cat.map((c) => el("option", { value: c.id, texte: c.titre })));
    const garde = App.memoire.lire("kt", {});
    choix.value = cat.some((c) => c.id === garde.id) ? garde.id : "arbre_epaulement_flexion";
    const champs = { p1: el("input", { type: "text", inputmode: "decimal" }), p2: el("input", { type: "text", inputmode: "decimal" }) };
    const etiquettes = { p1: el("span"), p2: el("span") };
    const sortie = el("div", { "aria-live": "polite" });
    const description = el("div");
    const bornes = { plaque: { p1: [0, 0.999, 0.3, "d/W (-)"] }, arbre: { p1: [0.01, 0.3, 0.1, "r/d (-)"], p2: [1.01, 6, 1.5, "D/d (-)"] } };
    const forme = () => (cat.find((c) => c.id === choix.value).plaque ? "plaque" : "arbre");

    const calculer = () => {
      const b = bornes[forme()];
      const s = { id: choix.value };
      for (const k of ["p1", "p2"]) {
        if (!b[k]) { s[k] = 0; continue; }
        const [mini, maxi] = b[k];
        const v = App.nombre(champs[k].value);
        const faux = v === "" || Number.isNaN(v) || v < mini || v > maxi;
        champs[k].classList.toggle("invalide", faux);
        if (faux) return sortie.replaceChildren(App.message("avertissement", `${b[k][3]} : nombre entre ${App.fr(mini)} et ${App.fr(maxi)}.`));
        s[k] = v;
      }
      App.memoire.ecrire("kt", { ...App.memoire.lire("kt", {}), id: s.id, [s.id]: s });
      const r = App.calculer("kt", s);
      if (!r.ok) return sortie.replaceChildren(App.message("erreur", r.erreur));
      const k = r.sortie;
      sortie.replaceChildren(
        el("div", { class: "metriques" }, el("div", { class: "metrique" }, el("span", { texte: "Kt" }), el("strong", { texte: App.fr(Number(k.Kt.toPrecision(4))) }))),
        k.dansLeDomaine ? "" : App.message("avertissement", "Paramètres hors du domaine de validité de l'abaque : valeur extrapolée, à prendre avec prudence."),
        ...k.latex.map(App.formule), App.figure(k), el("ul", {}, k.rapport.map((l) => el("li", { texte: App.decimalesFr(l) }))));
    };
    const poser = () => {
      const c = cat.find((x) => x.id === choix.value), b = bornes[forme()];
      const enregistre = App.memoire.lire("kt", {})[choix.value] || {};
      description.replaceChildren(el("p", { texte: c.description }), App.formule(c.latex));
      for (const k of ["p1", "p2"]) {
        champs[k].closest("label").hidden = !b[k];
        if (b[k]) { etiquettes[k].textContent = b[k][3]; champs[k].value = App.fr(enregistre[k] ?? b[k][2]); }
      }
      calculer();
    };
    for (const k of ["p1", "p2"]) champs[k].addEventListener("input", calculer);
    choix.addEventListener("change", poser);
    panneau.append(el("p", { class: "legende", texte: "Concentration de contrainte : la contrainte maximale vaut Kt fois la contrainte nominale. Ajustements de Peterson (domaines de validité indiqués)." }),
      el("label", { class: "large" }, "Abaque", choix), description,
      el("div", { class: "grille" }, el("label", {}, etiquettes.p1, champs.p1), el("label", {}, etiquettes.p2, champs.p2)), sortie);
    poser();
  }

  function fichiers(panneau) {
    const message = el("div");
    const entree = el("input", { type: "file", accept: ".json,application/json", hidden: true });
    entree.addEventListener("change", async () => {
      const fic = entree.files[0];
      entree.value = "";
      if (!fic) return;
      if (fic.size > 600000) return message.replaceChildren(App.message("erreur", "Fichier trop gros pour des ajouts MecaStruct."));
      const r = App.calculer("base.importer", { texte: await fic.text() });
      garder(r);
      message.replaceChildren(App.message(r.ok ? "succes" : "erreur", r.ok ? r.sortie.message : r.erreur));
    });
    panneau.append(
      el("p", { texte: "Enregistrez vos ajouts (matériaux et profilés) dans un fichier, pour les retrouver sur un autre poste ou dans l'application de bureau." }),
      el("p", { class: "ligne" },
        el("button", { type: "button", class: "secondaire", texte: "Enregistrer mes ajouts", onclick: () => {
          const r = App.calculer("base.exporter");
          if (r.ok) App.telecharger(r.sortie.nom, r.sortie.texte);
        } }),
        el("button", { type: "button", class: "secondaire", texte: "Importer un fichier d'ajouts", onclick: () => entree.click() }),
        entree),
      message);
  }

  App.genre("base", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) return contenu.append(App.attente("Le calcul se charge : la base apparaîtra dans quelques secondes.", page));
    const c = App.calculer("base.catalogue");
    if (!c.ok) return contenu.append(App.message("erreur", c.erreur));
    contenu.append(App.onglets([
      { id: "mat", titre: "Matériaux", rendu: (p) => materiaux(p, App.calculer("base.catalogue").sortie) },
      { id: "pro", titre: "Profilés", rendu: (p) => profils(p, c.sortie) },
      { id: "mata", titre: "Pressions de matage", rendu: (p) => matage(p, c.sortie) },
      { id: "kt", titre: "Abaques Kt", rendu: abaques },
      { id: "fic", titre: "Mes ajouts", rendu: fichiers },
    ], "page.base", "Matériaux et profilés"));
  });
})();
