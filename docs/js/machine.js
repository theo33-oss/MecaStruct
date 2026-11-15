"use strict";
// Page générique de calcul : champs → verdict, schéma, graphiques, tableaux, explications, dossier de validation.
// Les champs viennent du pont (calcul « formulaires ») : aucun libellé n'est écrit ici.
// Calcul automatique (pages légères) ou bouton « Calculer » (auto: false, pages plus lourdes : Poutres, Treillis…).

(() => {
  const { el } = App;
  let formulaires = null;

  function lireFormulaires(neuf = false) {
    if (!formulaires || neuf) {
      const r = App.calculer("formulaires");
      if (r.ok) formulaires = r.sortie;
    }
    return formulaires;
  }

  // Nombre affiché sans bruit de calcul : 2848,0000000000005 → 2848.
  const affiche = (v) => (typeof v === "number" && Number.isFinite(v) ? App.fr(Number(v.toPrecision(10))) : App.fr(v ?? ""));
  const copie = (x) => JSON.parse(JSON.stringify(x));

  // Saisie gardée dans le navigateur, sinon valeurs de l'exemple ; les clés inconnues sont ignorées.
  function saisieDepart(ident, f) {
    const gardee = App.memoire.lire("saisie." + ident, {});
    const s = copie(f.defaut);
    for (const k of Object.keys(s)) if (k in gardee) s[k] = gardee[k];
    return s;
  }

  function verifierNombre(c, texte) {
    const v = App.nombre(texte);
    if (v === "" || Number.isNaN(v)) return [NaN, "Nombre attendu."];
    if (c.entier && !Number.isInteger(v)) return [NaN, "Nombre entier attendu."];
    if (c.min !== null && c.min !== undefined && v < c.min) return [NaN, `Minimum ${App.fr(c.min)}.`];
    if (c.max !== null && c.max !== undefined && v > c.max) return [NaN, `Maximum ${App.fr(c.max)}.`];
    return [v, ""];
  }

  // ---------- champs ----------

  function champ(c, saisie, changer, outils) {
    const aide = c.aide || undefined;
    const titre = c.libelle + (c.unite ? ` (${c.unite})` : "");
    const valeur = saisie[c.id];
    if (c.type === "case") {
      const input = el("input", { type: "checkbox" });
      input.checked = !!valeur;
      input.addEventListener("change", () => changer(c.id, input.checked));
      return el("label", { class: "case", aide }, input, " " + c.libelle);
    }
    if (c.type === "liste") {
      const select = el("select", {}, c.options.map((o, i) => el("option", { value: String(o), texte: c.etiquettes ? c.etiquettes[i] : String(o) })));
      select.value = String(valeur);
      select.addEventListener("change", () => changer(c.id, typeof c.options[0] === "number" ? Number(select.value) : select.value));
      select.dataset.id = c.id;
      return el("label", { aide }, titre, select);
    }
    if (c.type === "texte") {
      const input = el("input", { type: "text", value: valeur ?? "" });
      input.addEventListener("input", () => changer(c.id, input.value));
      return el("label", { aide }, titre, input);
    }
    if (c.type === "tableau") return tableauEditable(c, saisie, changer);
    if (c.type === "action") return action(c, saisie, outils);
    const input = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false" });
    input.value = affiche(valeur);
    const erreur = el("span", { class: "erreur-champ", hidden: true });
    input.addEventListener("input", () => {
      const [v, texte] = verifierNombre(c, input.value);
      input.classList.toggle("invalide", !!texte);
      input.setAttribute("aria-invalid", String(!!texte));
      erreur.textContent = texte;
      erreur.hidden = !texte;
      changer(c.id, v);
    });
    return el("label", { aide }, titre, input, erreur);
  }

  // Liste + bouton : le choix part au calcul indiqué, qui rend des valeurs à recopier dans la saisie (profilé…).
  function action(c, saisie, outils) {
    const select = el("select");
    const remplir = () => {
      const o = c.options_de;
      const r = o ? App.calculer(o.calcul, { [o.cle]: saisie[o.depuis] }) : { ok: true, sortie: c.options || [] };
      select.replaceChildren(...(r.ok ? r.sortie : []).map((x) => el("option", { value: x, texte: x })));
    };
    remplir();
    outils.surChangement((id) => { if (c.options_de && id === c.options_de.depuis) remplir(); });
    const bouton = el("button", { type: "button", class: "secondaire", texte: c.bouton, onclick: () => {
      const r = App.calculer(c.calcul, { ...saisie, choix: select.value });
      if (r.ok) outils.fusionner(r.sortie, `${c.libelle} : ${select.value} appliqué.`);
      else outils.signaler("erreur", r.erreur);
    } });
    return el("div", { class: "action", aide: c.aide || undefined }, el("label", {}, c.libelle, select), bouton);
  }

  // Tableau éditable : une ligne par élément, ajout et retrait de lignes, collage depuis Excel (tabulations).
  function tableauEditable(c, saisie, changer) {
    let lignes = copie(saisie[c.id] || []);
    const corps = el("tbody");
    const publier = () => {
      const invalide = corps.querySelector(".invalide");
      changer(c.id, invalide ? NaN : copie(lignes));
    };
    const cellule = (ligne, k) => {
      if (k.genre === "case") {
        const i = el("input", { type: "checkbox", "aria-label": k.libelle });
        i.checked = !!ligne[k.id];
        i.addEventListener("change", () => { ligne[k.id] = i.checked; publier(); });
        return i;
      }
      if (k.genre === "liste") {
        const s = el("select", { "aria-label": k.libelle }, k.options.map((o) => el("option", { value: o, texte: o })));
        s.value = ligne[k.id] ?? k.defaut;
        s.addEventListener("change", () => { ligne[k.id] = s.value; publier(); });
        return s;
      }
      const i = el("input", { type: "text", "aria-label": k.libelle, inputmode: k.genre === "nombre" ? "decimal" : undefined });
      i.value = k.genre === "nombre" ? affiche(ligne[k.id]) : (ligne[k.id] ?? "");
      i.addEventListener("input", () => {
        if (k.genre !== "nombre") { ligne[k.id] = i.value; return publier(); }
        const [v, texte] = verifierNombre({ entier: k.entier }, i.value);
        i.classList.toggle("invalide", !!texte);
        i.title = texte;
        if (!texte) ligne[k.id] = v;
        publier();
      });
      i.addEventListener("paste", (e) => coller(e, lignes.indexOf(ligne), c.colonnes.indexOf(k)));
      return i;
    };
    const dessiner = () => {
      corps.replaceChildren(...lignes.map((ligne, n) => el("tr", {},
        c.colonnes.map((k) => el("td", {}, cellule(ligne, k))),
        el("td", {}, el("button", { type: "button", class: "secondaire petit", "aria-label": `Retirer la ligne ${n + 1}`, texte: "×",
          disabled: lignes.length <= (c.min || 0), onclick: () => { lignes.splice(n, 1); dessiner(); publier(); } })))));
    };
    // Collage de plusieurs cellules (Excel) : remplit à partir de la case, ajoute les lignes manquantes.
    function coller(e, n0, k0) {
      const texte = (e.clipboardData || window.clipboardData).getData("text");
      if (!/[\t\n]/.test(texte.trim())) return;
      e.preventDefault();
      texte.replace(/\r/g, "").split("\n").filter((l) => l.trim()).forEach((l, dn) => {
        const n = n0 + dn;
        if (!lignes[n]) lignes.push(nouvelleLigne());
        l.split("\t").forEach((v, dk) => {
          const k = c.colonnes[k0 + dk];
          if (!k) return;
          if (k.genre === "nombre") { const x = App.nombre(v); if (typeof x === "number" && !Number.isNaN(x)) lignes[n][k.id] = x; }
          else if (k.genre === "case") lignes[n][k.id] = /^(1|vrai|oui|true|x)$/i.test(v.trim());
          else lignes[n][k.id] = v.trim();
        });
      });
      dessiner();
      publier();
    }
    const nouvelleLigne = () => Object.fromEntries(c.colonnes.map((k) => [k.id, k.defaut]));
    dessiner();
    return el("div", { class: "tableau-saisie" },
      el("div", { class: "titre-tableau", aide: c.aide || undefined }, c.libelle),
      el("div", { class: "defile" }, el("table", { class: "editable" },
        el("thead", {}, el("tr", {}, c.colonnes.map((k) => el("th", { scope: "col", texte: k.libelle })), el("th", { scope: "col" }, el("span", { class: "cache", texte: "Retirer" })))),
        corps)),
      el("button", { type: "button", class: "secondaire petit", texte: "Ajouter une ligne", onclick: () => { lignes.push(nouvelleLigne()); dessiner(); publier(); } }));
  }

  // ---------- un calcul : formulaire et résultat ----------

  function blocCalcul(ident, f) {
    let saisie = saisieDepart(ident, f);
    const auto = f.auto !== false;
    const invalides = new Set();
    const abonnes = [];
    let calculee = null; // empreinte de la saisie du dernier résultat affiché
    const zoneSchema = el("div", { class: "schema" });
    const zoneMessage = el("div");
    const zoneResultat = el("div", { class: "resultat", "aria-live": "polite" });
    let minuterie = null;
    const enregistrer = () => App.memoire.ecrire("saisie." + ident, saisie);

    const changer = (id, v) => {
      if (typeof v === "number" && Number.isNaN(v)) invalides.add(id);
      else {
        invalides.delete(id);
        saisie[id] = v;
        enregistrer();
        const suite = (f.suites || {})[id];
        if (suite) {
          const r = App.calculer(suite.calcul, { nom: v, champs: suite.champs });
          if (r.ok) { for (const [k, x] of Object.entries(r.sortie)) if (x !== null) saisie[k] = x; enregistrer(); dessinerChamps(); }
        }
        abonnes.forEach((a) => a(id));
      }
      clearTimeout(minuterie);
      minuterie = setTimeout(() => (auto ? relancer() : apercu()), auto ? 250 : 400);
    };
    const outils = {
      surChangement: (a) => abonnes.push(a),
      fusionner: (valeurs, texte) => { Object.assign(saisie, valeurs); enregistrer(); dessinerChamps(); apercu(); signaler("succes", texte); },
      signaler: (n, t) => signaler(n, t),
    };
    function signaler(niveau, texte) {
      zoneMessage.replaceChildren(App.message(niveau, texte));
      setTimeout(() => zoneMessage.replaceChildren(), 6000);
    }

    const formulaire = el("form", { class: "saisie", onsubmit: (e) => { e.preventDefault(); relancer(); } });
    function dessinerChamps() {
      abonnes.length = 0;
      const haut = el("div", { class: "actions-saisie" });
      if (!auto) haut.append(el("button", { type: "submit", class: "primaire", texte: "Calculer", aide: "Lance le calcul (Entrée dans un champ)." }));
      if ((f.exemples || []).length) {
        const choix = el("select", { "aria-label": "Exemple" }, f.exemples.map((n) => el("option", { value: n, texte: n })));
        haut.append(choix, el("button", { type: "button", class: "secondaire", texte: "Charger l'exemple", onclick: () => {
          const r = App.calculer(ident + ".exemple", { nom: choix.value });
          if (!r.ok) return signaler("erreur", r.erreur);
          saisie = { ...copie(f.defaut), ...r.sortie };
          invalides.clear();
          enregistrer();
          dessinerChamps();
          relancer();
        } }));
      } else {
        haut.append(el("button", { type: "button", class: "secondaire", texte: "Valeurs de l'exemple", aide: "Remet les valeurs de l'exemple du cours ou du classeur.",
          onclick: () => { saisie = copie(f.defaut); invalides.clear(); App.memoire.oublier("saisie." + ident); dessinerChamps(); relancer(); } }));
      }
      if (f.norme) {
        haut.append(el("button", { type: "button", class: "secondaire", texte: "Valeurs conseillées par la norme", aide: "Qualités, lissage et jeu de montage conseillés pour ce diamètre.",
          onclick: () => {
            const r = App.calculer(ident + ".norme", saisie);
            if (r.ok && r.sortie) { Object.assign(saisie, r.sortie); enregistrer(); dessinerChamps(); relancer(); }
            else signaler("avertissement", "Diamètre hors table : saisissez les valeurs.");
          } }));
      }
      formulaire.replaceChildren(haut, zoneMessage, ...f.groupes.map((g) => {
        const champs = g.champs.map((c) => champ(c, saisie, changer, outils));
        return el("details", { class: "groupe", open: g.ouvert !== false }, el("summary", { texte: g.titre }),
          el("div", { class: g.ligne ? "grille ligne-champs" : "grille" }, champs),
          g.note ? el("p", { class: "legende note", texte: g.note }) : null);
      }));
      if (auto) formulaire.append(el("button", { type: "submit", hidden: true, texte: "Calculer" }));
      if (f.note) formulaire.append(el("p", { class: "legende note", texte: f.note }));
    }

    function apercu() {
      if (!f.apercu || invalides.size) return;
      const a = App.calculer(ident + ".apercu", saisie);
      zoneSchema.replaceChildren(a.ok && a.sortie && a.sortie.data ? App.figure(a.sortie, "figure schema-figure")
        : App.message("info", "Schéma indisponible pour cette saisie" + (a.erreur ? " : " + a.erreur : ".")));
      if (calculee !== null && calculee !== JSON.stringify(saisie)) perime();
    }
    function perime() {
      if (zoneResultat.querySelector(".perime")) return;
      const m = App.message("avertissement", "Saisie modifiée depuis le dernier calcul : les résultats ci-dessous datent de l'ancienne saisie. Cliquez sur « Calculer ».");
      m.classList.add("perime");
      zoneResultat.prepend(m);
    }

    function relancer() {
      if (!App.pret) return;
      if (invalides.size) {
        zoneResultat.replaceChildren(App.message("avertissement", "Corrigez les champs signalés en rouge : le calcul reprendra dès qu'ils seront valides."));
        return;
      }
      if (f.apercu && auto) apercu();
      const lancer = () => {
        const r = App.calculer(ident, saisie);
        calculee = JSON.stringify(saisie);
        if (!r.ok) return zoneResultat.replaceChildren(App.message("erreur", r.erreur));
        afficherResultat(r.sortie);
        if (r.sortie.options) majOptions(r.sortie);
        if (!auto && f.apercu) apercu();
      };
      if (auto) lancer();
      else { // laisse le navigateur afficher « Calcul en cours » avant un calcul de quelques dixièmes de seconde
        zoneResultat.replaceChildren(App.message("info", "Calcul en cours…"));
        setTimeout(lancer, 30);
      }
    }

    function majOptions(s) {
      for (const [id, options] of Object.entries(s.options)) {
        const select = formulaire.querySelector(`select[data-id="${id}"]`);
        if (!select) continue;
        select.replaceChildren(...options.map((o) => el("option", { value: o, texte: o })));
        select.value = s.saisie[id];
        saisie[id] = s.saisie[id];
      }
    }

    function afficherResultat(s) {
      const niveau = s.ok === true ? "succes" : s.ok === false ? "erreur" : "info";
      const prefixe = s.ok === true ? "Vérifié. " : s.ok === false ? "Non vérifié. " : "";
      const verdict = App.message(niveau, prefixe + App.decimalesFr(s.status));
      verdict.classList.add("verdict");
      const liste = [];
      for (const g of s.figures || []) liste.push({ id: "fig-" + g.titre, titre: g.titre, rendu: (p) => p.append(App.figure(g.figure)) });
      if (s.figure) liste.push({ id: "graphique", titre: "Graphique", rendu: (p) => p.append(App.figure(s.figure)) });
      const tables = Object.entries(s.tables || {});
      if (tables.length) liste.push({ id: "synthese", titre: tables.length > 1 ? "Tableaux" : "Synthèse", rendu: (p) => tables.forEach(([nom, t]) => p.append(App.tableau(t, tables.length > 1 ? nom : null))) });
      if ((s.explications || []).length || (s.latex || []).length || (s.rapport || []).length) {
        liste.push({ id: "explications", titre: "Explications du calcul", rendu: (p) => explications(p, s) });
      }
      const metriques = (s.metriques || []).length
        ? el("div", { class: "metriques" }, s.metriques.map(([n, v]) => el("div", { class: "metrique" }, el("span", { texte: n }), el("strong", { texte: App.decimalesFr(v) }))))
        : null;
      zoneResultat.replaceChildren(verdict, metriques || "", liste.length ? App.onglets(liste, ident) : "", f.dossier ? boutonDossier() : "");
    }

    function explications(p, s) {
      if ((s.explications || []).length) {
        p.append(el("h4", { texte: "Équations appliquées à vos données" }),
          el("p", { class: "legende", texte: "Chaque grandeur est refaite à la main, puis comparée au résultat du solveur." }));
        for (const r of s.explications) {
          if (r.titre) { p.append(el("h4", { class: "sous-titre", texte: r.titre })); continue; }
          p.append(el("p", { class: "explication", texte: r.label }), App.formule(r.latex),
            el("p", { class: "legende " + (r.ok ? "concorde" : "ecart"), texte: App.decimalesFr(r.note) }));
        }
      }
      if ((s.latex || []).length) p.append(el("h4", { texte: "Formules appliquées à vos données" }), ...s.latex.map(App.formule));
      if ((s.blocs || []).length) {
        const d = el("details", { class: "groupe" }, el("summary", { texte: "Équations écrites par le solveur" }));
        for (const b of s.blocs) d.append(el("h4", { texte: b.nom }), ...b.formules.map(App.formule));
        p.append(d);
      }
      if ((s.rapport || []).length) p.append(el("h4", { texte: "Démarche" }), el("ul", {}, s.rapport.filter((l) => String(l).trim()).map((l) => el("li", { texte: App.decimalesFr(l) }))));
    }

    function boutonDossier() {
      const b = el("button", { type: "button", class: "secondaire", texte: "Dossier de validation (HTML)",
        aide: "Refait chaque grandeur à la main, la compare au solveur et réunit données, hypothèses et résultats dans un fichier à joindre à votre note de calcul. Pour un PDF : ouvrez le fichier, puis Imprimer, Enregistrer en PDF." });
      b.addEventListener("click", () => {
        b.disabled = true;
        b.textContent = "Préparation du dossier…";
        setTimeout(async () => {
          if (!await App.paquets(["jinja2"])) { b.disabled = false; b.textContent = "Dossier de validation (HTML)"; return signaler("erreur", "Le générateur de dossier n'a pas pu se charger."); }
          const r = App.calculer(ident + ".dossier", saisie);
          b.disabled = false;
          b.textContent = "Dossier de validation (HTML)";
          if (!r.ok) return signaler("erreur", r.erreur);
          App.telecharger(r.sortie.nom, r.sortie.html, "text/html");
        }, 30);
      });
      return el("p", { class: "ligne" }, b);
    }

    dessinerChamps();
    const bloc = el("div", { class: "calcul" },
      el("div", { class: "colonne-saisie" }, formulaire),
      el("div", { class: "colonne-resultat" }, f.apercu ? el("h3", { texte: "Schéma" }) : null, f.apercu ? zoneSchema : null,
        el("h3", { texte: "Résultat" }), zoneResultat));
    if (App.pret) {
      if (auto) requestAnimationFrame(relancer);
      else {
        requestAnimationFrame(apercu);
        zoneResultat.replaceChildren(App.message("info", "Renseignez les données, puis cliquez sur « Calculer »."));
      }
    }
    return bloc;
  }

  App.genre("machine", async (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) {
      contenu.append(App.message("info", "Le calcul se charge : les champs apparaîtront dans quelques secondes."));
      return;
    }
    if (page.pont) {
      const attente = App.message("info", "Chargement des bibliothèques de cette page (scipy, shapely)… quelques secondes la première fois.");
      contenu.append(attente);
      if (!await App.preparer(page)) {
        attente.replaceWith(App.message("erreur", "Les bibliothèques de cette page n'ont pas pu se charger. Rechargez la page (Ctrl+F5)."));
        return;
      }
      attente.remove();
      lireFormulaires(true);
    }
    const tous = lireFormulaires();
    if (!tous || page.calculs.some((id) => !tous[id])) {
      contenu.append(App.message("erreur", "Les formulaires de cette page n'ont pas pu être lus."));
      return;
    }
    if (page.calculs.length === 1) contenu.append(blocCalcul(page.calculs[0], tous[page.calculs[0]]));
    else contenu.append(App.onglets(page.calculs.map((id) => ({ id, titre: tous[id].titre, rendu: (p) => p.append(blocCalcul(id, tous[id])) })), "page." + page.id));
  });
})();
