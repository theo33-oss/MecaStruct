"use strict";
// Page générique « champs → verdict, schéma, graphique, synthèse, explications » des éléments de machines.
// Les champs viennent du pont (calcul « formulaires ») : aucun libellé n'est écrit ici. Le calcul se relance seul à
// chaque saisie valide (il dure quelques millisecondes) : le résultat affiché correspond toujours aux champs.

(() => {
  const { el } = App;
  let formulaires = null;

  function lireFormulaires() {
    if (!formulaires) {
      const r = App.calculer("formulaires");
      if (r.ok) formulaires = r.sortie;
    }
    return formulaires;
  }

  // Saisie gardée dans le navigateur, sinon valeurs de l'exemple ; les clés inconnues sont ignorées.
  function saisieDepart(ident, f) {
    const gardee = App.memoire.lire("saisie." + ident, {});
    const s = { ...f.defaut };
    for (const k of Object.keys(s)) if (k in gardee) s[k] = gardee[k];
    return s;
  }

  // Un champ du formulaire ; lire() rend la valeur typée comme la valeur de départ, ou NaN si invalide.
  function champ(c, valeur, changer) {
    const aide = c.aide || undefined;
    const titre = c.libelle + (c.unite ? ` (${c.unite})` : "");
    if (c.type === "case") {
      const input = el("input", { type: "checkbox" });
      input.checked = !!valeur;
      input.addEventListener("change", () => changer(c.id, input.checked));
      return el("label", { class: "case", aide }, input, " " + c.libelle);
    }
    if (c.type === "liste") {
      const select = el("select", {}, c.options.map((o) => el("option", { value: String(o), texte: String(o) })));
      select.value = String(valeur);
      select.addEventListener("change", () => changer(c.id, typeof c.options[0] === "number" ? Number(select.value) : select.value));
      select.dataset.id = c.id;
      return el("label", { aide }, titre, select);
    }
    const input = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false" });
    input.value = App.fr(valeur);
    const erreur = el("span", { class: "erreur-champ", hidden: true });
    const verifier = () => {
      const v = App.nombre(input.value);
      let texte = "";
      if (v === "" || Number.isNaN(v)) texte = "Nombre attendu.";
      else if (c.min !== null && c.min !== undefined && v < c.min) texte = `Minimum ${App.fr(c.min)}.`;
      else if (c.max !== null && c.max !== undefined && v > c.max) texte = `Maximum ${App.fr(c.max)}.`;
      input.classList.toggle("invalide", !!texte);
      input.setAttribute("aria-invalid", String(!!texte));
      erreur.textContent = texte;
      erreur.hidden = !texte;
      return texte ? NaN : v;
    };
    input.addEventListener("input", () => changer(c.id, verifier()));
    input.dataset.id = c.id;
    return el("label", { aide }, titre, input, erreur);
  }

  // Bloc d'un calcul : formulaire à gauche, résultats à droite (l'un sous l'autre sur un écran étroit).
  function blocCalcul(ident, f) {
    let saisie = saisieDepart(ident, f);
    const invalides = new Set();
    const zoneSchema = el("div", { class: "schema" });
    const zoneResultat = el("div", { class: "resultat", "aria-live": "polite" });
    let minuterie = null;

    const changer = (id, v) => {
      if (Number.isNaN(v)) invalides.add(id);
      else {
        invalides.delete(id);
        saisie[id] = v;
        App.memoire.ecrire("saisie." + ident, saisie);
      }
      clearTimeout(minuterie);
      minuterie = setTimeout(relancer, 250);
    };

    const formulaire = el("form", { class: "saisie", onsubmit: (e) => { e.preventDefault(); relancer(); } });
    const dessinerChamps = () => {
      formulaire.replaceChildren(...f.groupes.map((g) => {
        const champs = g.champs.map((c) => champ(c, saisie[c.id], changer));
        return el("details", { class: "groupe", open: g.ouvert !== false }, el("summary", { texte: g.titre }),
          el("div", { class: g.ligne ? "grille ligne-champs" : "grille" }, champs));
      }));
      const actions = el("div", { class: "actions-saisie" });
      actions.append(el("button", { type: "button", class: "secondaire", texte: "Valeurs de l'exemple", aide: "Remet les valeurs de l'exemple du cours ou du classeur.",
        onclick: () => { saisie = { ...f.defaut }; invalides.clear(); App.memoire.oublier("saisie." + ident); dessinerChamps(); relancer(); } }));
      if (f.norme) {
        actions.append(el("button", { type: "button", class: "secondaire", texte: "Valeurs conseillées par la norme", aide: "Qualités, lissage et jeu de montage conseillés pour ce diamètre.",
          onclick: () => {
            const r = App.calculer(ident + ".norme", saisie);
            if (r.ok && r.sortie) { Object.assign(saisie, r.sortie); App.memoire.ecrire("saisie." + ident, saisie); dessinerChamps(); relancer(); }
            else zoneResultat.prepend(App.message("avertissement", "Diamètre hors table : saisissez les valeurs."));
          } }));
      }
      formulaire.append(actions, el("button", { type: "submit", hidden: true, texte: "Calculer" }));
      if (f.note) formulaire.append(el("p", { class: "legende note", texte: f.note }));
    };

    function relancer() {
      if (!App.pret) return;
      if (invalides.size) {
        zoneResultat.replaceChildren(App.message("avertissement", "Corrigez les champs signalés en rouge : le résultat reprendra dès qu'ils seront valides."));
        return;
      }
      if (f.apercu) {
        const a = App.calculer(ident + ".apercu", saisie);
        zoneSchema.replaceChildren(a.ok && a.sortie && a.sortie.data ? App.figure(a.sortie, "figure schema-figure")
          : App.message("info", "Schéma indisponible pour cette saisie" + (a.erreur ? " : " + a.erreur : ".")));
      }
      const r = App.calculer(ident, saisie);
      if (!r.ok) {
        zoneResultat.replaceChildren(App.message("erreur", r.erreur));
        return;
      }
      afficherResultat(ident, r.sortie);
      if (r.sortie.options) majOptions(r.sortie);
    }

    // Règles de montage : les listes « rotation » et « charge » dépendent de la bague choisie.
    function majOptions(s) {
      for (const [id, options] of Object.entries(s.options)) {
        const select = formulaire.querySelector(`select[data-id="${id}"]`);
        if (!select) continue;
        select.replaceChildren(...options.map((o) => el("option", { value: o, texte: o })));
        select.value = s.saisie[id];
        saisie[id] = s.saisie[id];
      }
    }

    function afficherResultat(id, s) {
      const niveau = s.ok === true ? "succes" : s.ok === false ? "erreur" : "info";
      const prefixe = s.ok === true ? "Vérifié. " : s.ok === false ? "Non vérifié. " : "";
      const verdict = App.message(niveau, prefixe + App.decimalesFr(s.status));
      verdict.classList.add("verdict");
      const liste = [];
      if (s.figure) liste.push({ id: "graphique", titre: "Graphique", rendu: (p) => p.append(App.figure(s.figure)) });
      const tables = Object.entries(s.tables || {});
      if (tables.length) liste.push({ id: "synthese", titre: "Synthèse", rendu: (p) => tables.forEach(([nom, t]) => p.append(App.tableau(t, tables.length > 1 ? nom : null))) });
      if ((s.latex || []).length || (s.rapport || []).length) {
        liste.push({ id: "explications", titre: "Explications du calcul", rendu: (p) => {
          if (s.latex.length) p.append(el("h4", { texte: "Formules appliquées à vos données" }), ...s.latex.map(App.formule));
          if (s.rapport.length) p.append(el("h4", { texte: "Démarche" }), el("ul", {}, s.rapport.map((l) => el("li", { texte: App.decimalesFr(l) }))));
        } });
      }
      zoneResultat.replaceChildren(verdict, liste.length ? App.onglets(liste, id) : "");
    }

    dessinerChamps();
    const bloc = el("div", { class: "calcul" },
      el("div", { class: "colonne-saisie" }, formulaire),
      el("div", { class: "colonne-resultat" }, f.apercu ? el("h3", { texte: "Schéma" }) : null, f.apercu ? zoneSchema : null, el("h3", { texte: "Résultat" }), zoneResultat));
    bloc._relancer = relancer;
    if (App.pret) requestAnimationFrame(relancer);
    else zoneResultat.replaceChildren(App.message("info", "Le calcul se charge : le résultat apparaîtra ici dans quelques secondes."));
    return bloc;
  }

  App.genre("machine", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) {
      contenu.append(App.message("info", "Le calcul se charge : les champs apparaîtront dans quelques secondes."));
      return;
    }
    const tous = lireFormulaires();
    if (!tous) {
      contenu.append(App.message("erreur", "Les formulaires n'ont pas pu être lus."));
      return;
    }
    if (page.calculs.length === 1) {
      contenu.append(blocCalcul(page.calculs[0], tous[page.calculs[0]]));
    } else {
      contenu.append(App.onglets(page.calculs.map((id) => ({ id, titre: tous[id].titre, rendu: (p) => p.append(blocCalcul(id, tous[id])) })), "page." + page.id));
    }
  });
})();
