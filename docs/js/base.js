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
      const r = App.calculer("base.materiaux", { categories: [...choisies], recherche: recherche.value });
      tableau.replaceChildren(r.ok ? App.tableau(r.sortie) : App.message("erreur", r.erreur));
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
    const apres = (r, ok) => {
      garder(r);
      message.replaceChildren(App.message(r.ok ? "succes" : "erreur", r.ok ? r.sortie.message : r.erreur));
      if (r.ok) { const c = App.calculer("base.catalogue").sortie; suppr.replaceChildren(...c.utilisateur.map((n) => el("option", { value: n, texte: n }))); dessiner(); }
    };
    panneau.append(
      el("details", { class: "groupe", open: true }, el("summary", { texte: "Catégories" }), el("div", { class: "grille" }, cases)),
      el("label", { class: "large" }, "Rechercher un matériau", recherche), tableau,
      el("p", { class: "legende", texte: "Les matériaux « Base complémentaire » viennent d'un rapport de synthèse (2026) : valeurs typiques, à vérifier sur la fiche matière du fournisseur avant un usage professionnel." }),
      el("h3", { texte: "Ajouter un matériau" }),
      el("p", { class: "legende", texte: "Les ajouts restent dans ce navigateur (rien n'est envoyé sur Internet) et sont proposés dans tous les calculs." }),
      el("div", { class: "grille" }, f.champs),
      el("p", { class: "ligne" }, el("button", { type: "button", class: "primaire", texte: "Ajouter / remplacer", onclick: () => {
        const s = f.lire();
        if (!s) return message.replaceChildren(App.message("avertissement", "Corrigez les champs signalés en rouge."));
        apres(App.calculer("base.ajouter_materiau", s));
      } })),
      el("p", { class: "ligne" }, suppr, el("button", { type: "button", class: "secondaire", texte: "Supprimer ce matériau utilisateur", onclick: () => {
        if (suppr.value) apres(App.calculer("base.supprimer_materiau", { nom: suppr.value }));
      } })),
      message);
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
      el("h3", { texte: "Ajouter un profilé à la famille choisie" }),
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
    if (!pret) return contenu.append(App.message("info", "Le calcul se charge : la base apparaîtra dans quelques secondes."));
    const c = App.calculer("base.catalogue");
    if (!c.ok) return contenu.append(App.message("erreur", c.erreur));
    contenu.append(App.onglets([
      { id: "mat", titre: "Matériaux", rendu: (p) => materiaux(p, App.calculer("base.catalogue").sortie) },
      { id: "pro", titre: "Profilés", rendu: (p) => profils(p, c.sortie) },
      { id: "mata", titre: "Pressions de matage", rendu: (p) => matage(p, c.sortie) },
      { id: "fic", titre: "Mes ajouts", rendu: fichiers },
    ], "page.base"));
  });
})();
