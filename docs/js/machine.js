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
    const lue = App.memoire.lire("saisie." + ident, {});
    const gardee = lue && typeof lue === "object" && !Array.isArray(lue) ? lue : {}; // jamais « null » ni un tableau
    const s = copie(f.defaut);
    for (const k of Object.keys(s)) if (k in gardee) s[k] = gardee[k];
    return s;
  }

  function verifierNombre(c, texte) {
    const v = App.nombre(texte);
    const u = c.unite ? " " + c.unite : ""; // la borne s'écrit avec l'unité du champ : « Minimum 0 mm. »
    if (v === "" || Number.isNaN(v)) return [NaN, "Nombre attendu (ex. 12,5), sans unité."];
    if (c.entier && !Number.isInteger(v)) return [NaN, "Nombre entier attendu."];
    if (c.min !== null && c.min !== undefined && (c.minExclu ? v <= c.min : v < c.min))
      return [NaN, c.minExclu ? `Doit être supérieur à ${App.fr(c.min)}${u}.` : `Minimum ${App.fr(c.min)}${u}.`];
    if (c.max !== null && c.max !== undefined && v > c.max) return [NaN, `Maximum ${App.fr(c.max)}${u}.`];
    if (Math.abs(v) > 1e18) return [NaN, "Valeur démesurée (au plus 10¹⁸) : vérifiez l'unité."]; // même plafond que le calcul (pont/noyau.py)
    return [v, ""];
  }

  // ---------- champs ----------

  const securiteEnMarge = () => App.memoire.lire("securite", "coef") === "marge"; // réglage commun à toutes les pages

  // « Aller à la cause » : pour chaque calcul (ou calcul complémentaire), le champ à corriger en premier pour un critère de
  // services/criteres.py ; « g:Titre » désigne un groupe de champs. Le premier motif qui correspond à « groupe|mode » l'emporte.
  // Un calcul ou un critère absent d'ici n'a pas de lien : on ne relie que ce qui est sûr. La cible est le LEVIER de conception
  // (section, longueur, diamètre…), pas la charge imposée ; revue métier faite. Dans `pal`, « Collerette » doit rester avant « Pression ».
  const CAUSES = {
    beam: [[/./, ["g:Section"]]],
    "beam.ec3": [[/Déversement/, ["Lcr"]], [/./, ["g:Section"]]],
    "beam.fatigue": [[/./, ["g:Fatigue (Goodman)"]]],
    ossature: [[/./, ["g:Nœuds et pièces"]]],
    truss: [[/Résistance/, ["S"]], [/Flambage/, ["Imin"]]],
    tra: [[/./, ["S0"]]],
    cis: [[/^Matage\|/, ["Sm"]], [/^Clavette\|/, ["Lk"]], [/^Goupille\|/, ["dp"]], [/\|Jourawski/, ["g:Section pour Jourawski"]],
      [/\|Cisaillement : τ max/, ["S"]]],
    tor: [[/./, ["D"]]],
    fle: [[/./, ["g:Reprendre la section et les efforts"]]],
    fla: [[/./, ["g:Section"]]],
    ten: [[/./, ["sig"]]],
    fre: [[/Adhérence/, ["L"]], [/./, ["g:Tolérances et montage"]]],
    pal: [[/Collerette/, ["Dfl"]], [/Vitesse/, ["materiau"]], [/Pression/, ["L"]]],
    rlt: [[/./, ["C"]]],
    eng: [[/./, ["m"]]],
    emb: [[/./, ["ts"]]],
    mot: [[/Couple nominal/, ["Cn"]], [/Couple maxi/, ["Cmax"]], [/Vitesse maxi/, ["Nmax"]]],
  };

  const VERDICTS = { ok: ["✓", "Conforme"], neutre: ["⚠", "À vérifier"], ko: ["✗", "Non conforme"], info: ["ℹ", "Information"] };
  // « info » : calcul qui rend des valeurs sans critère de conformité (pas de mode de ruine, ni verdict vrai ou faux)
  const nombreOuNull = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
  // Avertissements du bloc « Décision », par calcul : fonction (saisie du calcul) → texte, ou null s'il n'y a rien à dire.
  // Une ligne par réserve connue ; ajouter ici, sans toucher au reste, une limite de modèle que la saisie peut franchir.
  const AVERTISSEMENTS = {
    eng: (s) => (nombreOuNull(s.alpha) !== null && s.alpha !== 20
      ? "α ≠ 20° : la contrainte en pied de dent reste calculée pour un profil à 20°." : null),
    beam: (s) => { // dernier appui (colonne « pos » du tableau « sup ») loin de l'extrémité L : porte-à-faux
      const L = nombreOuNull(s.L);
      const appuis = Array.isArray(s.sup) ? s.sup.map((a) => nombreOuNull(a && a.pos)).filter((x) => x !== null) : [];
      if (L === null || L <= 0 || appuis.length < 2) return null; // un seul appui : console, pas un oubli
      const dernier = Math.max(...appuis);
      if (L - dernier > 0.01 * L) return `La longueur L (${affiche(L)} m) dépasse le dernier appui (${affiche(dernier)} m) : la poutre a un porte-à-faux.`;
      if (dernier - L > 0.01 * L) return `Un appui (${affiche(dernier)} m) est au-delà de la longueur L (${affiche(L)} m) : vérifiez les positions.`;
      return null;
    },
  };
  const tauxDe = (c) => (Number.isFinite(c.taux) ? c.taux : Infinity);
  // Même nom de mode dans plusieurs études (Pression de matage P : matage, clavette, goupille) : l'étude lève le doute
  const libelleMode = (c, crit) => (c.groupe && crit.filter((x) => x.mode === c.mode).length > 1 ? `${c.mode} (${c.groupe})` : c.mode);

  // Barre résumé du bas d'écran (petit écran) : état partagé par les calculs affichés (un seul à la fois en pratique)
  const blocsResume = new Map(); // bloc monté → son observateur
  const barresVisibles = new Set();
  const petitEcran = matchMedia("(max-width: 1099.98px)");
  function majPageResume() {
    for (const [b, io] of blocsResume) if (!b.isConnected) { io.disconnect(); blocsResume.delete(b); barresVisibles.delete(b); }
    document.body.classList.toggle("avec-resume", petitEcran.matches && blocsResume.size > 0); // marge basse du contenu
    document.documentElement.classList.toggle("resume-visible", petitEcran.matches && barresVisibles.size > 0); // décale languette IA et messages
  }
  petitEcran.addEventListener("change", majPageResume);
  window.addEventListener("hashchange", () => setTimeout(majPageResume, 500));

  // Repère data-id d'un champ (focus conservé quand les champs sont redessinés) ; les boutons n'ont pas toujours d'identifiant
  const repere = (c) => c.id ?? `${c.type}|${c.calcul || ""}|${c.libelle}`;

  function champ(c, saisie, changer, outils) {
    const aide = c.aide || undefined;
    const titre = c.libelle + (c.unite ? ` (${c.unite})` : "");
    const valeur = saisie[c.id];
    if (c.type === "case") {
      const input = el("input", { type: "checkbox" });
      input.checked = !!valeur;
      input.dataset.id = c.id;
      input.addEventListener("change", () => changer(c.id, input.checked));
      return el("label", { class: "case", aide }, input, " " + c.libelle);
    }
    if (c.type === "liste") {
      let options = c.options;
      if (c.options_de) { // liste qui dépend d'un autre champ (profilés de la famille choisie)
        const r = App.calculer(c.options_de.calcul, { [c.options_de.cle]: saisie[c.options_de.depuis] });
        options = r.ok ? r.sortie : [];
        if (options.length && !options.includes(valeur)) saisie[c.id] = options[0];
      }
      const option = (o, i) => el("option", { value: String(o), texte: c.etiquettes ? c.etiquettes[i] : String(o) });
      let contenu = options.map(option);
      if (c.familles && !c.options_de) { // matériaux rangés par famille
        const noms = [...new Set(c.familles)];
        contenu = noms.map((n) => el("optgroup", { label: n }, options.map((o, i) => (c.familles[i] === n ? option(o, i) : null))));
      }
      const select = el("select", {}, contenu);
      // valeur gardée qui n'est plus proposée (matériau retiré de la base) : pas de repli silencieux sur un autre choix
      let introuvable = null;
      if (!c.options_de && valeur !== undefined && valeur !== null && valeur !== "" && !options.some((o) => String(o) === String(valeur))) {
        select.prepend(el("option", { value: String(valeur), class: "indisponible", texte: `${valeur} (indisponible)` }));
        introuvable = el("span", { class: "erreur-champ", id: "err-" + c.id,
          texte: c.id === "mat" ? "Matériau introuvable : choisissez-en un autre." : `Valeur enregistrée introuvable (« ${valeur} ») : choisissez-en une autre.` });
        select.setAttribute("aria-invalid", "true");
        select.setAttribute("aria-describedby", introuvable.id);
      }
      select.value = String(saisie[c.id]);
      select.addEventListener("change", () => {
        if (introuvable) { select.querySelector("option.indisponible")?.remove(); introuvable.remove(); select.removeAttribute("aria-invalid"); select.removeAttribute("aria-describedby"); introuvable = null; }
        changer(c.id, typeof options[0] === "number" ? Number(select.value) : select.value);
      });
      select.dataset.id = c.id;
      return el("label", { aide }, titre, select, introuvable);
    }
    if (c.type === "matrice") return matrice(c, saisie, changer);
    if (c.type === "bouton") {
      return el("div", { class: "action" }, el("button", { type: "button", class: "secondaire", "data-id": repere(c), texte: c.libelle, aide: c.aide || undefined, onclick: () => {
        const r = App.calculer(c.calcul, saisie);
        if (r.ok) outils.fusionner(r.sortie, `${c.libelle} : fait.`);
        else outils.signaler("erreur", r.erreur);
      } }));
    }
    if (c.type === "liste-fixe") {
      const select = el("select", {}, c.options.map((o, i) => el("option", { value: String(o), texte: c.etiquettes ? c.etiquettes[i] : String(o) })));
      select.value = String(valeur);
      select.addEventListener("change", () => changer(c.id, typeof c.options[0] === "number" ? Number(select.value) : select.value));
      select.dataset.id = c.id;
      return el("label", { aide }, titre, select);
    }
    if (c.type === "texte") {
      const input = el("input", { type: "text", value: valeur ?? "" });
      input.dataset.id = c.id;
      input.addEventListener("input", () => changer(c.id, input.value));
      return el("label", { aide }, titre, input);
    }
    if (c.type === "tableau") return tableauEditable(c, saisie, changer);
    if (c.type === "figure") {
      const zone = el("div", { class: "figure-saisie" });
      let attente = null;
      const dessiner = () => {
        const r = App.calculer(c.calcul, saisie);
        if (!r.ok) zone.replaceChildren(App.message("info", "Dessin indisponible : " + r.erreur));
        else if (r.sortie && r.sortie.vide) zone.replaceChildren(el("p", { class: "legende", texte: r.sortie.vide }));
        else zone.replaceChildren(App.figure(r.sortie, "figure figure-petite"));
      };
      dessiner();
      outils.surChangement((id) => {
        if (!(c.depend || []).includes(id)) return;
        clearTimeout(attente);
        attente = setTimeout(dessiner, 300);
      });
      return el("div", { class: "champ-large" }, el("span", { class: "titre-champ", texte: c.libelle }), zone);
    }
    if (c.type === "action") return action(c, saisie, outils);
    if (c.type === "transfert") { // recopie des champs d'une page dans une autre (section → Poutres, efforts → Sections…)
      return el("div", { class: "action" }, el("button", { type: "button", class: "secondaire", "data-id": repere(c), texte: c.libelle, aide: c.aide || undefined, onclick: () => outils.transfert(c) }));
    }
    if (c.type === "extra") { // calcul complémentaire (combinaisons, Eurocode 3…) : son résultat s'affiche sous le résultat principal
      return el("div", { class: "action" }, el("button", { type: "button", class: "secondaire", "data-id": repere(c), texte: c.libelle, aide: c.aide || undefined, onclick: () => outils.extra(c) })); // secondaire : « Calculer » reste le seul primaire
    }
    // sécurité : coefficient s ou marge en % (marge = s − 1), au choix ; la saisie garde toujours s
    const enMarge = !!c.securite && securiteEnMarge();
    const regle = enMarge ? { ...c, min: 0, max: null, minExclu: false, unite: "%" } : c;
    const input = el("input", { type: "text", inputmode: App.clavierNombre(regle.min), autocomplete: "off", spellcheck: "false" });
    input.value = affiche(enMarge && typeof valeur === "number" ? 100 * (valeur - 1) : valeur);
    input.dataset.id = c.id; // repère pour le mode guidé (js/guide.js)
    // l'étiquette englobe aussi la liste « Coefficient s / Marge » : c'est elle qui la reçoit, le champ garde son propre nom
    if (c.securite) input.setAttribute("aria-label", enMarge ? "Marge de sécurité (%)" : titre);
    const erreur = el("span", { class: "erreur-champ", id: "err-" + c.id, hidden: true });
    const evaluer = () => { // [valeur, message] : NaN et un message si le texte est refusé
      let [v, texte] = verifierNombre(regle, input.value);
      if (enMarge && !texte) v = Number((1 + v / 100).toPrecision(12));
      return [v, texte];
    };
    const montrer = (texte) => {
      input.classList.toggle("invalide", !!texte);
      input.setAttribute("aria-invalid", String(!!texte));
      if (texte) input.setAttribute("aria-describedby", erreur.id); else input.removeAttribute("aria-describedby");
      erreur.textContent = texte;
      erreur.hidden = !texte;
    };
    let attenteErreur = null;
    // Une erreur ne s'affiche qu'à la sortie du champ ou 700 ms après la dernière frappe : jamais pendant la frappe d'un « - » ou d'un « 1e ».
    // Une erreur déjà affichée se met à jour tout de suite, et disparaît dès que le texte est bon.
    const valider = (immediat = false) => {
      const [v, texte] = evaluer();
      clearTimeout(attenteErreur);
      if (texte) input.dataset.refuse = texte; else delete input.dataset.refuse; // état « refusé » lu aussi par le mode guidé
      if (!texte || immediat || input.classList.contains("invalide")) montrer(texte);
      else attenteErreur = setTimeout(() => montrer(evaluer()[1]), 700);
      return v;
    };
    input.addEventListener("input", () => changer(c.id, valider(), input.value));
    input.addEventListener("blur", () => valider(true));
    const brut = outils.brut(c.id); // champ redessiné alors que son texte était refusé : on garde ce qui a été tapé, avec son erreur
    if (brut !== undefined) { input.value = brut; valider(true); }
    else if (outils.controle && evaluer()[1]) { outils.refuser(c.id, input.value); valider(true); } // étude ouverte : chaque champ repasse par la validation
    if (c.securite) {
      const forme = el("select", { "aria-label": "Forme de la sécurité", class: "forme-securite",
        aide: "Coefficient de sécurité s, ou marge en % (marge = s − 1 : 30 % de marge donne s = 1,30). Valable pour toutes les pages." },
        el("option", { value: "coef", texte: "Coefficient s" }), el("option", { value: "marge", texte: "Marge (%)" }));
      forme.value = enMarge ? "marge" : "coef";
      forme.dataset.id = c.id + "|forme";
      forme.addEventListener("change", () => { App.memoire.ecrire("securite", forme.value); outils.rafraichir(); });
      return el("label", { aide: aide || (enMarge ? "Marge de sécurité = s − 1 : on exige σ ≤ Re / (1 + marge)." : undefined) },
        el("span", { class: "titre-securite" }, enMarge ? "Marge de sécurité (%)" : titre, forme), input, erreur);
    }
    return el("label", { aide }, titre, input, erreur);
  }

  // Noms affichés des exemples (les identifiants restent ceux de l'application de bureau).
  const VIDE = "__vide"; // choix « cas personnalisé » de la liste des exemples
  const NOMS_EXEMPLES = { isostatique: "Poutre isostatique", hyperstatique: "Poutre hyperstatique", console: "Console",
    deuxtravees: "Deux travées", gerber: "Poutre Gerber (rotule)", tassement: "Tassement d'appui", constante: "Section constante",
    variable: "Section variable", iso3D: "Hooke 3D isotrope", planeStress: "Contraintes planes", planeStrain: "Déformations planes",
    ortho: "Orthotrope" };

  // Liste + bouton : le choix part au calcul indiqué, qui rend des valeurs à recopier dans la saisie (profilé…).
  function action(c, saisie, outils) {
    const select = el("select", { "data-id": repere(c) + "|liste" });
    const remplir = () => {
      const o = c.options_de;
      const r = o ? App.calculer(o.calcul, { [o.cle]: saisie[o.depuis] }) : { ok: true, sortie: c.options || [] };
      // premier choix vide : la liste ne laisse pas croire que le premier profilé est celui de la saisie
      select.replaceChildren(el("option", { value: "", texte: "— choisir —" }), ...(r.ok ? r.sortie : []).map((x) => el("option", { value: x, texte: x })));
    };
    // la liste montre le profilé réellement utilisé par la section (exemple chargé, profilé appliqué), pas « — choisir — »
    const courant = () => {
      const k = c.courant, sec = k && saisie[k.champ];
      if (!sec || typeof sec !== "object" || !sec[k.nom]) return;
      if (k.famille && c.options_de && String(sec[k.famille]) !== String(saisie[c.options_de.depuis])) return;
      if ([...select.options].some((o) => o.value === sec[k.nom])) select.value = sec[k.nom];
    };
    remplir();
    courant();
    outils.surChangement((id) => { if (c.options_de && id === c.options_de.depuis) { remplir(); courant(); } });
    const bouton = el("button", { type: "button", class: "secondaire", "data-id": repere(c), texte: c.bouton, onclick: () => {
      if (!select.value) return outils.signaler("avertissement", `${c.libelle} : choisissez d'abord une ligne dans la liste.`);
      const r = App.calculer(c.calcul, { ...saisie, choix: select.value });
      if (r.ok) outils.fusionner(r.sortie, `${c.libelle} : ${select.value} appliqué.`);
      else outils.signaler("erreur", r.erreur);
    } });
    return el("div", { class: "action", aide: c.aide || undefined }, el("label", {}, c.libelle, select), bouton);
  }

  // Cellules refusées d'un tableau ou d'une matrice : une ligne de statut sous le tableau (« Ligne 3, colonne L (m) : nombre attendu »).
  function majStatut(statut, racine) {
    const faux = [...racine.querySelectorAll("input.invalide")];
    statut.hidden = !faux.length;
    if (!faux.length) { statut.textContent = ""; return; }
    const i = faux[0];
    const cause = String(i.dataset.refuse || "").replace(/\.$/, "");
    const autres = faux.length > 1 ? ` (et ${faux.length - 1} autre${faux.length > 2 ? "s" : ""} cellule${faux.length > 2 ? "s" : ""})` : "";
    statut.textContent = `Ligne ${i.closest("tr").sectionRowIndex + 1}, colonne ${i.dataset.colonne} : ${cause.charAt(0).toLowerCase() + cause.slice(1)}${autres}`;
  }
  // Validation douce d'une cellule : le texte refusé est noté tout de suite (data-refuse), l'erreur se montre à la sortie de la cellule
  // ou 700 ms après la dernière frappe ; une cellule redevenue bonne se nettoie aussitôt.
  function validationCellule(input, racine, statut) {
    let attente = null;
    const montrer = () => {
      const texte = input.dataset.refuse || "";
      input.classList.toggle("invalide", !!texte);
      input.title = texte;
      input.setAttribute("aria-invalid", String(!!texte));
      if (texte) input.setAttribute("aria-describedby", statut.id); else input.removeAttribute("aria-describedby");
      majStatut(statut, racine);
    };
    input.addEventListener("blur", () => { clearTimeout(attente); montrer(); });
    return {
      refuser(texte, immediat = false) { // texte vide : cellule valide
        clearTimeout(attente);
        if (texte) input.dataset.refuse = texte; else delete input.dataset.refuse;
        if (!texte || immediat || input.classList.contains("invalide")) montrer(); else attente = setTimeout(montrer, 700);
      },
    };
  }

  // Matrice carrée (tenseur) : une case modifiée est recopiée en position symétrique si demandé.
  function matrice(c, saisie, changer) {
    const m = copie(saisie[c.id]);
    const n = m.length;
    const cases = [];
    const statut = el("p", { class: "erreur-champ statut-tableau", id: "err-" + c.id, role: "status", hidden: true });
    const publier = () => changer(c.id, cases.flat().some((i) => i.dataset.refuse) ? NaN : copie(m));
    const corps = el("tbody"); // rempli plus bas : les cellules ont besoin de lui pour la ligne de statut
    corps.append(...m.map((ligne, i) => el("tr", {}, el("th", { scope: "row", texte: c.noms[i] }), ligne.map((v, j) => {
      const input = el("input", { type: "text", inputmode: "text", "aria-label": `σ${c.noms[i]}${c.noms[j]}` }); // contraintes : négatives possibles
      input.value = affiche(v);
      input.dataset.colonne = c.noms[j];
      const validation = validationCellule(input, corps, statut);
      input.validation = validation;
      (cases[i] = cases[i] || [])[j] = input;
      input.addEventListener("input", () => {
        const [x, texte] = verifierNombre({}, input.value);
        validation.refuser(texte);
        if (!texte) {
          m[i][j] = x;
          if (c.symetrique && i !== j) { m[j][i] = x; cases[j][i].value = input.value; cases[j][i].validation.refuser("", true); }
        }
        publier();
      });
      return el("td", {}, input);
    }))));
    return el("div", { class: "tableau-saisie", "data-champ": c.id, aide: c.aide || undefined }, el("div", { class: "titre-tableau", texte: c.libelle }),
      el("table", { class: "editable matrice", "aria-label": c.libelle }, el("thead", {}, el("tr", {}, el("th"), c.noms.map((x) => el("th", { scope: "col", texte: x })))), corps), statut);
  }

  // Tableau éditable : une ligne par élément, ajout et retrait de lignes, collage depuis Excel (tabulations).
  function tableauEditable(c, saisie, changer) {
    let lignes = copie(saisie[c.id] || []);
    const corps = el("tbody");
    const statut = el("p", { class: "erreur-champ statut-tableau", id: "err-" + c.id, role: "status", hidden: true });
    // texte refusé tapé dans une cellule, par ligne : il reste affiché (en rouge) quand les lignes sont redessinées
    const brutCellules = new Map();
    const brutDe = (ligne, id) => (brutCellules.get(ligne) || {})[id];
    const noterBrut = (ligne, id, texte) => {
      const o = brutCellules.get(ligne) || {};
      if (texte === undefined) delete o[id]; else o[id] = texte;
      brutCellules.set(ligne, o);
    };
    const publier = () => {
      const invalide = corps.querySelector("[data-refuse]");
      changer(c.id, invalide ? NaN : copie(lignes));
    };
    // Tableau « polaire » (force inclinée) : F, le plan et α remplissent Fx, Fy, Fz (même règle que services/forces.py) ;
    // taper à la main une composante remet F et α à 0.
    const champs = new Map(); // ligne → { id de colonne : champ de saisie }
    const AXES = { xy: ["Fx", "Fy"], xz: ["Fx", "Fz"], yz: ["Fy", "Fz"] };
    const COMPOSANTES = ["Fx", "Fy", "Fz"];
    function majPolaire(ligne, id) {
      const po = c.polaire;
      if (!po) return;
      if (COMPOSANTES.includes(id)) {
        // première saisie à la main sur une ligne inclinée : les autres composantes venaient de F et α, elles repartent de 0
        if (Number(ligne[po.norme]) !== 0) for (const n of COMPOSANTES) if (n !== id && n in ligne) ligne[n] = 0;
        ligne[po.norme] = 0;
        ligne[po.angle] = 0;
      }
      else if ([po.norme, po.angle, po.plan].includes(id) && Number(ligne[po.norme]) !== 0) {
        const f = Number(ligne[po.norme]), a = (Number(ligne[po.angle]) || 0) * Math.PI / 180;
        const [u, v] = AXES[ligne[po.plan]] || AXES[po.plans[0]];
        const r = (x) => (Math.abs(x) < 1e-12 * Math.abs(f) ? 0 : Number(x.toPrecision(12)));
        for (const n of COMPOSANTES) if (n in ligne) ligne[n] = n === u ? r(f * Math.cos(a)) : n === v ? r(f * Math.sin(a)) : 0;
      } else return;
      for (const [cle, champ] of Object.entries(champs.get(ligne) || {}))
        if (cle !== id && (COMPOSANTES.includes(cle) || cle === po.norme || cle === po.angle)) {
          champ.value = affiche(ligne[cle]); noterBrut(ligne, cle, undefined); champ.validation.refuser("", true);
        }
    }
    const cellule = (ligne, k) => {
      if (k.genre === "case") {
        const i = el("input", { type: "checkbox", "aria-label": k.libelle });
        i.checked = !!ligne[k.id];
        i.addEventListener("change", () => { ligne[k.id] = i.checked; publier(); });
        return i;
      }
      if (k.genre === "liste") {
        const s = el("select", { "aria-label": k.libelle }, k.options.map((o, i) => el("option", { value: o, texte: k.etiquettes ? k.etiquettes[i] : o })));
        s.value = ligne[k.id] ?? k.defaut;
        s.addEventListener("change", () => { ligne[k.id] = s.value; majPolaire(ligne, k.id); publier(); });
        return s;
      }
      const i = el("input", { type: "text", "aria-label": k.libelle, inputmode: k.genre === "nombre" ? App.clavierNombre(k.min) : undefined });
      i.value = k.genre === "nombre" ? affiche(ligne[k.id]) : (ligne[k.id] ?? "");
      i.dataset.colonne = k.libelle;
      i.validation = validationCellule(i, corps, statut);
      if (!champs.has(ligne)) champs.set(ligne, {});
      champs.get(ligne)[k.id] = i;
      if (k.genre === "nombre") {
        // texte refusé gardé d'un dessin à l'autre ; sinon la valeur déjà dans la ligne (étude ouverte) repasse par la validation
        const brut = brutDe(ligne, k.id);
        if (brut !== undefined) { i.value = brut; i.validation.refuser(verifierNombre({ entier: k.entier }, brut)[1] || "Nombre attendu (ex. 12,5), sans unité.", true); }
        else if (typeof ligne[k.id] === "number") { // colonne absente d'une ligne (F, α…) : vide, pas refusée
          const t = verifierNombre({ entier: k.entier }, i.value)[1];
          if (t) { noterBrut(ligne, k.id, i.value); i.validation.refuser(t, true); }
        }
      }
      i.addEventListener("input", () => {
        if (k.genre !== "nombre") { ligne[k.id] = i.value; return publier(); }
        if (c.polaire && [c.polaire.norme, c.polaire.angle].includes(k.id) && i.value.trim() === "") {
          // F ou α vidé = plus de force inclinée : Fx, Fy, Fz gardent leur valeur et se saisissent de nouveau à la main
          noterBrut(ligne, k.id, undefined); i.validation.refuser("", true);
          ligne[k.id] = 0;
          return publier();
        }
        const [v, texte] = verifierNombre({ entier: k.entier }, i.value);
        noterBrut(ligne, k.id, texte ? i.value : undefined);
        i.validation.refuser(texte);
        if (!texte) { ligne[k.id] = v; majPolaire(ligne, k.id); }
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
      majStatut(statut, corps);
    };
    // Collage de plusieurs cellules (Excel) : remplit à partir de la case, ajoute les lignes manquantes.
    function coller(e, n0, k0) {
      const texte = (e.clipboardData || window.clipboardData).getData("text");
      if (!/[\t\n]/.test(texte.trim())) return;
      e.preventDefault();
      texte.replace(/\r/g, "").split("\n").filter((l) => l.trim()).forEach((l, dn) => {
        const n = n0 + dn;
        if (!lignes[n]) lignes.push(nouvelleLigne());
        const collees = [];
        l.split("\t").forEach((v, dk) => {
          const k = c.colonnes[k0 + dk];
          if (!k) return;
          collees.push(k.id);
          if (k.genre === "nombre") {
            const x = App.nombre(v);
            if (typeof x === "number" && !Number.isNaN(x)) { lignes[n][k.id] = x; noterBrut(lignes[n], k.id, undefined); }
            else if (v.trim() !== "") noterBrut(lignes[n], k.id, v.trim()); // collé mais refusé : visible en rouge, pas ignoré en silence
          }
          else if (k.genre === "case") lignes[n][k.id] = /^(1|vrai|oui|true|x)$/i.test(v.trim());
          else lignes[n][k.id] = v.trim();
        });
        if (c.polaire) {
          const po = c.polaire;
          if ([po.norme, po.angle, po.plan].some((x) => collees.includes(x))) majPolaire(lignes[n], po.norme);
          else if (COMPOSANTES.some((x) => collees.includes(x))) majPolaire(lignes[n], "Fx");
        }
      });
      dessiner();
      publier();
    }
    const nouvelleLigne = () => Object.fromEntries(c.colonnes.map((k) => [k.id, k.defaut]));
    dessiner();
    if (corps.querySelector("[data-refuse]")) publier(); // valeur déjà refusée à l'ouverture (étude, mémoire) : le calcul est bloqué, la cellule en rouge
    return el("div", { class: "tableau-saisie", "data-champ": c.id },
      el("div", { class: "titre-tableau", aide: c.aide || undefined }, c.libelle),
      el("div", { class: "defile" }, el("table", { class: "editable", "aria-label": c.libelle },
        el("thead", {}, el("tr", {}, c.colonnes.map((k) => el("th", { scope: "col", texte: k.libelle })), el("th", { scope: "col" }, el("span", { class: "cache", texte: "Retirer" })))),
        corps)),
      statut,
      el("button", { type: "button", class: "secondaire petit", texte: "Ajouter une ligne", onclick: () => { lignes.push(nouvelleLigne()); dessiner(); publier(); } }));
  }

  // ---------- un calcul : formulaire et résultat ----------

  function blocCalcul(ident, f) {
    let saisie = saisieDepart(ident, f);
    const auto = f.auto !== false;
    const invalides = new Set();
    const brutInvalide = new Map(); // champ numérique refusé → texte tapé (réaffiché, en rouge, si les champs sont redessinés)
    const abonnes = [];
    let calculee = null; // empreinte de la saisie du dernier résultat affiché
    const zoneSchema = el("div", { class: "schema" });
    let ctlSchema = null; // pages à schéma : bloc « Représentation » (voir blocSchema)
    const zoneMessage = el("div");
    const zoneResultat = el("div", { class: "resultat" });
    // Tête de résultat « Décision » : hors de zoneResultat, que les calculs en cours ou les erreurs vident ; elle garde donc
    // le résultat précédent (marqué « résultat précédent ») pendant un calcul, un résultat daté ou grisé.
    const zoneDecision = el("div", { class: "zone-decision" });
    // Seule la phrase du bilan est annoncée aux lecteurs d'écran (pas tout le résultat), 800 ms après le dernier calcul.
    const annonce = el("p", { class: "cache", role: "status", "aria-atomic": "true" });
    let minuterieAnnonce = null;
    const annoncer = (texte, force = false) => {
      clearTimeout(minuterieAnnonce);
      minuterieAnnonce = setTimeout(() => {
        if (annonce.textContent === texte && !force) return; // même phrase : rien de neuf à dire
        annonce.textContent = "";
        setTimeout(() => { annonce.textContent = texte; }, 50);
      }, 800);
    };
    let minuterie = null;
    let minuterieCalcul = null; // calcul différé des pages à bouton : un clic de plus remplace le précédent
    let offreAnnuler = false; // un message « Annuler » est affiché
    let comparaison = null; // « Comparer des études » (js/comparer.js)
    const enregistrer = () => App.memoire.ecrire("saisie." + ident, saisie);
    const tousChamps = f.groupes.flatMap((g) => g.champs);
    const conditions = (c) => [].concat(c.si || []); // une condition ou une liste de conditions, toutes requises
    const controleurs = new Set(tousChamps.flatMap((c) => [...conditions(c).map((k) => k.id), c.options_de && c.type === "liste" && c.options_de.depuis].filter(Boolean)));
    const visible = (c) => conditions(c).every((k) => k.valeurs.includes(saisie[k.id]));

    // Matériau changé sur une page à bouton « Calculer » : E, G, Re… sont déjà remplacés dans les champs, mais le résultat affiché
    // date encore de l'ancien matériau. Une notification sous la case le dit, avec un bouton « Actualiser ».
    let matPerime = null; // { id, nom, champs }
    function afficherPerime() {
      formulaire.querySelectorAll(".notif-matPerime").forEach((n) => n.remove());
      if (!matPerime) return;
      const select = formulaire.querySelector(`select[data-id="${matPerime.id}"]`);
      if (!select) return;
      const champs = matPerime.champs.length ? ` (${matPerime.champs.join(", ")})` : "";
      const notif = el("div", { class: "notif-matPerime", role: "status" },
        el("span", { texte: `Matériau changé : ${matPerime.nom}. Les propriétés${champs} sont à jour dans les champs, mais le résultat affiché date de l'ancien matériau.` }),
        el("button", { type: "button", class: "secondaire petit", texte: "Actualiser",
          aide: "Relance le calcul avec le matériau courant et remplace le résultat, le schéma et les graphiques affichés.",
          onclick: () => { matPerime = null; afficherPerime(); relancer(true); } }));
      select.closest("label").after(notif);
    }

    const oublierInvalide = (id) => { invalides.delete(id); brutInvalide.delete(id); };
    const viderInvalides = () => { invalides.clear(); brutInvalide.clear(); };
    const changer = (id, v, brut) => {
      if (offreAnnuler) { zoneMessage.replaceChildren(); offreAnnuler = false; } // la saisie a bougé : « Annuler » ne remettrait plus l'état d'avant
      if (typeof v === "number" && Number.isNaN(v)) {
        invalides.add(id);
        if (brut !== undefined) brutInvalide.set(id, brut); else brutInvalide.delete(id);
      } else {
        oublierInvalide(id);
        saisie[id] = v;
        enregistrer();
        const suite = (f.suites || {})[id];
        if (suite) {
          const r = App.calculer(suite.calcul, { nom: v, champs: suite.champs, saisie });
          if (r.ok) {
            for (const [k, x] of Object.entries(r.sortie)) if (x !== null) { saisie[k] = x; oublierInvalide(k); }
            enregistrer();
            if (!auto && suite.champs.length) matPerime = { id, nom: v, champs: suite.champs };
            if (!suite.discret) dessinerChamps();
            else afficherPerime();
          }
        }
        abonnes.forEach((a) => a(id));
        marquerExtras();
        if (controleurs.has(id)) dessinerChamps(); // champs affichés ou listes qui dépendent de celui-ci
      }
      clearTimeout(minuterie);
      // champ refusé : on attend 700 ms (le temps de finir de taper « -12,5 ») avant de griser le résultat affiché
      minuterie = setTimeout(() => (auto ? relancer() : apercu()), invalides.size ? 700 : auto ? 250 : 400);
    };
    const zoneExtras = el("div", { class: "extras" });
    const extras = {}; // calcul → { saisie au moment du calcul, bloc affiché }
    const extrasEnCours = new Map(); // calcul différé d'un complément → fonction qui l'annule
    const outils = {
      rafraichir: () => { dessinerChamps(); if (derniere) afficherResultat(derniere); },
      // Les saisies des pages sources partent au calcul ; ce qu'il rend est écrit dans la saisie de chaque page cible
      // (fusion champ par champ : un champ absent du résultat garde sa valeur). « self » désigne cette page.
      transfert: (c) => {
        if (invalides.size) return signaler("avertissement", blocage("Corrigez d'abord les champs signalés en rouge :"));
        const demande = { ...(c.params || {}) };
        for (const [cle, page] of Object.entries(c.entrees || {})) demande[cle] = page === "self" ? saisie : App.lireSaisie(page);
        const r = App.calculer(c.calcul, demande);
        if (!r.ok) return signaler("erreur", r.erreur);
        let ici = null;
        for (const [cle, page] of Object.entries(c.sorties || {})) {
          if (page === "self") ici = r.sortie[cle];
          else App.ecrireSaisie(page, { ...App.lireSaisie(page), ...r.sortie[cle] });
        }
        const texte = r.sortie.info || `${c.libelle} : fait.`;
        if (ici) { Object.assign(saisie, ici); Object.keys(ici).forEach(oublierInvalide); enregistrer(); dessinerChamps(); (auto ? relancer : apercu)(); }
        const lien = c.ouvrir ? el("a", { href: "#/" + c.ouvrir[0], texte: c.ouvrir[1] }) : null;
        zoneMessage.replaceChildren(el("p", { class: "message succes", role: "status" }, texte + " ", lien));
      },
      extra: (c) => {
        if (invalides.size) return signaler("avertissement", blocage("Corrigez d'abord les champs signalés en rouge :"));
        const titreExtra = () => App.titreImage(c.titre || c.libelle, () => bloc.querySelector(".bilan, .verdict"), "resultat.png");
        const bloc = el("section", { class: "extra" }, titreExtra(), App.message("info", "Calcul en cours…"));
        extras[c.calcul]?.bloc.remove();
        extrasEnCours.get(c.calcul)?.(); // clics répétés : un seul calcul, un seul « Calcul en cours… »
        zoneExtras.prepend(bloc);
        const attente = setTimeout(() => {
          extrasEnCours.delete(c.calcul);
          const r = App.calculer(c.calcul, saisie);
          bloc.replaceChildren(titreExtra());
          if (!r.ok) return bloc.append(App.message("erreur", r.erreur));
          bloc.append(...construireResultat(r.sortie, c.calcul, "", true, true));
          annoncer(`${c.titre || c.libelle} : ${phraseAnnonce(r.sortie)}`, true);
          extras[c.calcul] = { empreinte: JSON.stringify(saisie), bloc };
        }, 30);
        extrasEnCours.set(c.calcul, () => { clearTimeout(attente); bloc.remove(); });
      },
      surChangement: (a) => abonnes.push(a),
      brut: (id) => brutInvalide.get(id),
      refuser: (id, brut) => { invalides.add(id); brutInvalide.set(id, brut); }, // champ refusé à l'ouverture d'une étude
      controle: false, // vrai pendant le dessin des champs d'une étude ouverte : chaque valeur repasse par la validation
      fusionner: (valeurs, texte) => { Object.assign(saisie, valeurs); Object.keys(valeurs).forEach(oublierInvalide); enregistrer(); dessinerChamps(); apercu(); signaler("succes", texte); },
      signaler: (n, t) => signaler(n, t),
    };
    let minuterieMessage = null;
    // `restaurer` : fonction qui remet l'état d'avant ; le message propose alors un bouton « Annuler » pendant 8 s.
    function signaler(niveau, contenu, restaurer) {
      const p = el("p", { class: "message " + niveau, role: niveau === "erreur" ? "alert" : "status" }, contenu);
      offreAnnuler = !!restaurer;
      if (restaurer) p.append(" ", el("button", { type: "button", class: "secondaire petit", texte: "Annuler", aide: "Remet la saisie d'avant.",
        onclick: () => { clearTimeout(minuterieMessage); zoneMessage.replaceChildren(); offreAnnuler = false; restaurer(); } }));
      zoneMessage.replaceChildren(p);
      clearTimeout(minuterieMessage); // un second message ne doit pas être effacé par le minuteur du premier
      minuterieMessage = setTimeout(() => { zoneMessage.replaceChildren(); offreAnnuler = false; }, restaurer ? 8000 : niveau === "erreur" ? 12000 : 6000);
    }
    // État d'avant une action qui remplace la saisie (exemple chargé…) : rend la fonction qui le remet.
    function memoriser() {
      const avant = { saisie: copie(saisie), invalides: new Set(invalides), brut: new Map(brutInvalide), exemple: App.memoire.lire("exemple." + ident) };
      return () => {
        saisie = avant.saisie;
        invalides.clear(); avant.invalides.forEach((x) => invalides.add(x));
        brutInvalide.clear(); avant.brut.forEach((v, k) => brutInvalide.set(k, v));
        if (avant.exemple !== undefined) App.memoire.ecrire("exemple." + ident, avant.exemple);
        enregistrer();
        dessinerChamps();
        relancer();
        signaler("info", "Saisie d'avant remise.");
      };
    }

    // Champs refusés : leur nom, en boutons qui donnent le focus au champ.
    const nomChamp = (id) => { const c = tousChamps.find((x) => x.id === id); return c ? c.libelle + (c.unite ? ` (${c.unite})` : "") : id; };
    // Donne le focus au champ (ou au groupe « g:Titre »), ouvre le groupe replié, fait défiler (le menu collant est pris en compte
    // par scroll-padding-top = --barre) et met la cible en évidence 2 s (classe cause-surlignee, sans animation nécessaire).
    // Rend faux si la cible n'est pas affichée avec la saisie actuelle.
    let minuterieCause = null;
    function aller(id) {
      const zone = id.startsWith("g:") ? null : formulaire.querySelector(`.tableau-saisie[data-champ="${id}"]`);
      const cible = id.startsWith("g:") ? [...formulaire.querySelectorAll("details.groupe")].find((d) => d.dataset.titre === id.slice(2))
        : zone ? zone.querySelector("input.invalide, input[data-refuse]") || zone.querySelector("input") || zone.querySelector("button")
          : [...formulaire.querySelectorAll("[data-id]")].find((x) => x.dataset.id === id);
      if (!cible) return false;
      const groupe = cible.closest("details");
      if (groupe && !groupe.open) groupe.open = true;
      const entier = cible.matches("details");
      const doux = !matchMedia("(prefers-reduced-motion: reduce)").matches;
      (entier ? cible.querySelector("summary") : cible).focus({ preventScroll: true });
      cible.scrollIntoView({ block: entier ? "start" : "center", behavior: doux ? "smooth" : "auto" });
      const cadre = entier ? cible : cible.closest("label, .tableau-saisie, .action") || cible;
      formulaire.querySelectorAll(".cause-surlignee").forEach((x) => x.classList.remove("cause-surlignee"));
      cadre.classList.add("cause-surlignee");
      clearTimeout(minuterieCause);
      minuterieCause = setTimeout(() => cadre.classList.remove("cause-surlignee"), 2000);
      return true;
    }
    // Lien « Aller à la cause » d'un critère : rien si le calcul ou le critère n'a pas de champ sûr dans CAUSES, ou si ce
    // champ n'existe pas dans ce formulaire. Au clic, la première cible affichée avec la saisie actuelle reçoit le focus.
    function causesDe(cle, c) {
      const entree = (CAUSES[cle] || []).find(([motif]) => motif.test(`${c.groupe || ""}|${c.mode}`));
      const existe = (t) => (t.startsWith("g:") ? f.groupes.some((g) => g.titre === t.slice(2)) : tousChamps.some((x) => x.id === t));
      const cibles = entree ? entree[1].filter(existe) : [];
      return cibles.length ? cibles : null;
    }
    function boutonCause(cle, c, nom) {
      const cibles = causesDe(cle, c);
      if (!cibles) return null;
      return el("button", { type: "button", class: "lien-cause", "aria-label": `Aller à la cause : ${nom}`, texte: "Aller à la cause",
        aide: "Va au champ ou au groupe de champs qui influence le plus ce critère.", onclick: () => {
          if (!cibles.some(aller)) signaler("info", "Le champ à corriger n'est pas affiché avec la saisie actuelle.");
        } });
    }
    const listeInvalides = () => [...invalides].flatMap((id, n) => [n ? ", " : "",
      el("button", { type: "button", class: "lien-champ", "data-aller": id, texte: nomChamp(id), aide: "Va au champ à corriger.", onclick: () => aller(id) })]);
    const blocage = (debut) => [debut + " ", ...listeInvalides(), "."];

    // Entrée dans un champ d'une page automatique ne fait pas défiler vers le résultat (déjà à jour) ; « Calculer » le fait.
    const formulaire = el("form", { class: "saisie", onsubmit: (e) => { e.preventDefault(); relancer(!auto); } });
    function dessinerChamps() {
      // le champ qui avait le focus (et la position du curseur) le retrouve une fois les champs recréés
      const actif = document.activeElement;
      const focus = actif && actif !== document.body && formulaire.contains(actif) && actif.dataset && actif.dataset.id !== undefined
        ? { id: actif.dataset.id, sel: actif.type === "text" ? [actif.selectionStart, actif.selectionEnd, actif.selectionDirection] : null } : null;
      abonnes.length = 0;
      const haut = el("div", { class: "actions-saisie" });
      if (!auto) haut.append(el("button", { type: "submit", class: "primaire", texte: "Calculer", aide: "Lance le calcul (Entrée dans un champ)." }));
      if ((f.exemples || []).length) {
        // tableaux de la saisie (appuis, charges, barres…) : le cas personnalisé les vide, les combinaisons restent
        const tableaux = Object.keys(f.defaut).filter((k) => k !== "combo" && Array.isArray(f.defaut[k]));
        const noms = tableaux.length ? [...f.exemples, VIDE] : f.exemples;
        const choix = el("select", { "aria-label": "Exemple", "data-id": "|exemple" }, noms.map((n) => el("option", { value: n, texte: n === VIDE ? "Cas personnalisé (tableaux vides)" : NOMS_EXEMPLES[n] || n })));
        const garde = App.memoire.lire("exemple." + ident, f.exemples[0]); // l'exemple chargé reste affiché dans la liste
        if (noms.includes(garde)) choix.value = garde;
        haut.append(choix, el("button", { type: "button", class: "secondaire", "data-id": "|exemple-charger", texte: "Charger l'exemple", aide: "Remplace la saisie par l'exemple choisi, ou vide les tableaux pour partir de zéro.", onclick: () => {
          const retablir = memoriser(); // le bouton « Annuler » du message remet la saisie d'avant
          App.memoire.ecrire("exemple." + ident, choix.value);
          viderInvalides();
          if (choix.value === VIDE) {
            saisie = { ...copie(f.defaut), ...Object.fromEntries(tableaux.map((k) => [k, []])) };
            enregistrer();
            dessinerChamps();
            apercu();
            return signaler("info", "Cas personnalisé : les tableaux sont vides. Ajoutez vos lignes, puis cliquez sur Calculer.", retablir);
          }
          const r = App.calculer(ident + ".exemple", { nom: choix.value });
          if (!r.ok) return signaler("erreur", r.erreur);
          saisie = { ...copie(f.defaut), ...r.sortie };
          enregistrer();
          dessinerChamps();
          relancer();
          signaler("succes", `Exemple « ${NOMS_EXEMPLES[choix.value] || choix.value} » chargé : la saisie d'avant est remplacée.`, retablir);
        } }));
      } else {
        haut.append(el("button", { type: "button", class: "secondaire", "data-id": "|exemple-defaut", texte: "Charger l'exemple", aide: "Remet les valeurs de l'exemple du cours ou du classeur.",
          onclick: () => {
            const retablir = memoriser();
            saisie = copie(f.defaut); viderInvalides(); App.memoire.oublier("saisie." + ident); dessinerChamps(); relancer();
            signaler("succes", "Exemple chargé : la saisie d'avant est remplacée.", retablir);
          } }));
      }
      if (f.norme) {
        haut.append(el("button", { type: "button", class: "secondaire", "data-id": "|norme", texte: "Valeurs conseillées par la norme", aide: "Qualités, lissage et jeu de montage conseillés pour ce diamètre.",
          onclick: () => {
            const r = App.calculer(ident + ".norme", saisie);
            if (r.ok && r.sortie) { Object.assign(saisie, r.sortie); Object.keys(r.sortie).forEach(oublierInvalide); enregistrer(); dessinerChamps(); relancer(); }
            else signaler("avertissement", "Diamètre hors table : saisissez les valeurs.");
          } }));
      }
      const ouverts = Object.fromEntries([...formulaire.querySelectorAll("details.groupe")].map((d) => [d.dataset.titre, d.open]));
      // un champ refusé reste refusé s'il est redessiné avec son texte ; sans texte à réafficher (tableau, matrice) ou devenu
      // invisible, il n'est plus compté (sinon le calcul resterait bloqué sans aucun champ rouge)
      const visibles = new Set(f.groupes.flatMap((g) => g.champs.filter(visible).map((c) => c.id)));
      for (const id of [...invalides]) if (!visibles.has(id) || !brutInvalide.has(id)) oublierInvalide(id);
      formulaire.replaceChildren(haut, zoneMessage, ...f.groupes.filter((g) => g.champs.some(visible)).map((g) => {
        const champs = g.champs.filter(visible).map((c) => champ(c, saisie, changer, outils));
        const d = el("details", { class: "groupe", open: g.titre in ouverts ? ouverts[g.titre] : g.ouvert !== false }, el("summary", { texte: g.titre }),
          el("div", { class: g.ligne ? "grille ligne-champs" : "grille" }, champs),
          g.note ? el("p", { class: "legende note", texte: g.note }) : null);
        d.dataset.titre = g.titre;
        return d;
      }));
      if (auto) formulaire.append(el("button", { type: "submit", hidden: true, texte: "Calculer" }));
      afficherPerime();
      if (f.note) { // la source et les écarts avec le cours sont repliés : une phrase utile reste visible
        const coupe = f.note.search(/(^|\s)(Source|Fatigue|Formules classiques|Exemples) ?:? /);
        const tete = coupe > 0 ? f.note.slice(0, coupe).trim() : coupe === 0 ? "" : f.note;
        if (tete) formulaire.append(el("p", { class: "legende note", texte: tete }));
        if (coupe >= 0) formulaire.append(el("details", { class: "source" }, el("summary", { texte: /Exemples ?:/.test(f.note) ? "Détail des exemples" : "Source et écarts avec le cours" }),
          el("p", { class: "legende note", texte: f.note.slice(coupe).trim() })));
      }
      formulaire.append(barreFichiers());
      if (focus) {
        const cible = [...formulaire.querySelectorAll("[data-id]")].find((x) => x.dataset.id === focus.id);
        if (cible) {
          cible.focus({ preventScroll: true });
          if (focus.sel && cible.type === "text") { try { cible.setSelectionRange(...focus.sel); } catch (e) { /* champ sans sélection */ } }
        }
      }
    }

    // ---------- fichiers : enregistrer, ouvrir, lien de partage, Excel ----------
    const structure = !!f.dossier; // pages au format de fichier du bureau
    const fichier = () => App.calculer(structure ? ident + ".enregistrer" : "machine.enregistrer", structure ? saisie : { ident, saisie });
    function appliquer(texte, origine) {
      const r = App.calculer(structure ? ident + ".ouvrir" : "machine.ouvrir", structure ? { texte } : { ident, texte });
      if (!r.ok) return signaler("erreur", `${origine} : ${r.erreur}`);
      saisie = { ...copie(f.defaut), ...r.sortie };
      viderInvalides();
      enregistrer();
      outils.controle = true; // chaque champ repasse par la validation (bornes, 1e30…) et se marque en rouge s'il est refusé
      try { dessinerChamps(); } finally { outils.controle = false; }
      relancer();
      if (invalides.size) {
        signaler("avertissement", [`${origine} : étude chargée, mais des valeurs sont refusées :`, " ", ...listeInvalides(), "."]);
        App.toast(`${origine} : étude chargée, ${invalides.size} champ${invalides.size > 1 ? "s" : ""} à corriger.`, "erreur");
      } else {
        signaler("succes", `${origine} : étude chargée.`);
        App.toast(`${origine} : étude chargée.`);
      }
    }
    function barreFichiers() {
      const entree = el("input", { type: "file", accept: ".json,application/json", hidden: true });
      entree.addEventListener("change", async () => {
        const fic = entree.files[0];
        entree.value = "";
        if (!fic) return;
        if (fic.size > 2_000_000) return signaler("erreur", "Fichier trop gros pour une étude MecaStruct.");
        appliquer(await fic.text(), fic.name);
      });
      const boutons = [
        el("button", { type: "button", class: "secondaire petit", texte: "Enregistrer l'étude", aide: structure
          ? "Télécharge l'étude (.json). Le fichier est celui de l'application de bureau : il s'ouvre dans les deux versions."
          : "Télécharge l'étude (.json), à rouvrir plus tard sur cette page.", onclick: (e) => {
          const r = fichier();
          if (r.ok) { App.telecharger(r.sortie.nom, r.sortie.texte); App.retour(e.currentTarget, true, "Étude enregistrée"); }
          else signaler("erreur", r.erreur);
        } }),
        el("button", { type: "button", class: "secondaire petit", texte: "Ouvrir une étude", onclick: () => entree.click() }),
        el("button", { type: "button", class: "secondaire petit", texte: "Copier le lien de l'étude",
          aide: "Lien qui contient l'étude : la personne qui l'ouvre retrouve vos données. Rien n'est envoyé sur Internet, tout est dans l'adresse.",
          onclick: async (e) => {
            const bouton = e.currentTarget; // perdu après un await
            const r = fichier();
            if (!r.ok) return signaler("erreur", r.erreur);
            const code = await App.compresser(r.sortie.texte);
            const lien = `${location.origin}${location.pathname}#/${App.pageCourante().id}?calcul=${ident}&etude=${code}`;
            if (lien.length > 8000) return signaler("avertissement", "Étude trop grande pour un lien : enregistrez plutôt le fichier.");
            const ok = await App.copier(lien);
            App.confirmer(bouton, ok, "Lien copié", "Copie impossible", "Lien copié dans le presse-papiers : il contient toute l'étude.");
          } }),
      ];
      if (structure) {
        boutons.push(el("button", { type: "button", class: "secondaire petit", texte: "Exporter les résultats (Excel)",
          aide: "Classeur avec un onglet par tableau de résultats.", onclick: async (e) => {
            const bouton = e.currentTarget, libelle = bouton.textContent;
            bouton.disabled = true;
            bouton.textContent = "Préparation…";
            try {
              if (!await App.paquets(["openpyxl"])) return signaler("erreur", "L'export Excel n'a pas pu se charger.");
              const r = App.calculer(ident + ".excel", saisie);
              if (!r.ok) return signaler("erreur", r.erreur);
              const octets = Uint8Array.from(atob(r.sortie.base64), (c) => c.charCodeAt(0));
              App.telecharger(r.sortie.nom, octets, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
              bouton.textContent = libelle;
              App.retour(bouton, true, "Excel téléchargé");
            } finally { bouton.disabled = false; if (!bouton.dataset.libelle) bouton.textContent = libelle; }
          } }));
      }
      if (ident === "beam") { // Poutres : x, efforts, rotation et flèche par abscisse (mêmes valeurs que les graphiques)
        const point = el("input", { type: "checkbox", id: "csv-point" });
        point.checked = App.memoire.lire("csvPoint", false) === true;
        point.addEventListener("change", () => App.memoire.ecrire("csvPoint", point.checked));
        boutons.push(el("button", { type: "button", class: "secondaire petit", texte: "Exporter les diagrammes (CSV)",
          aide: "Fichier CSV (séparateur « ; », unités dans l'en-tête) : abscisse x, N, Ty, Tz, Mt, Mfy, Mfz, rotation et flèche aux mêmes points que les graphiques. S'ouvre dans Excel et LibreOffice.",
          onclick: (e) => {
            const r = App.calculer(ident + ".csv", { ...saisie, _point: point.checked });
            if (!r.ok) return signaler("erreur", r.erreur);
            App.telecharger(r.sortie.nom, r.sortie.texte, "text/csv;charset=utf-8");
            App.retour(e.currentTarget, true, "CSV téléchargé");
          } }),
          el("label", { class: "panneau-memo", for: "csv-point", aide: "Décoché : virgule décimale (Excel en français). Coché : point décimal." }, point, "Point décimal dans le CSV"));
      }
      return el("div", { class: "fichiers" }, el("h2", { class: "titre-mineur", texte: "Fichiers" }), el("div", { class: "ligne" }, boutons),
        avertAncien("Résultat précédent : le lien et le fichier reprennent la saisie actuelle, pas le résultat affiché."), entree);
    }

    function apercu() {
      if (invalides.size) return signalerInvalides(); // le résultat affiché reste, grisé et signalé comme daté
      griser(false);
      if (f.apercu) {
        const a = App.calculer(ident + ".apercu", saisie);
        zoneSchema.replaceChildren(a.ok && a.sortie && a.sortie.data ? App.figure(a.sortie, "figure schema-figure", false)
          : App.message("info", "Schéma indisponible pour cette saisie" + (a.erreur ? " : " + a.erreur : ".")));
      }
      if (calculee !== null && calculee !== JSON.stringify(saisie)) perime();
      else zoneResultat.querySelector(":scope > .perime")?.remove(); // saisie revenue à celle du résultat : plus rien de daté
    }
    const TEXTE_PERIME = "Saisie modifiée depuis le dernier calcul : les résultats ci-dessous datent de l'ancienne saisie. Cliquez sur « Calculer ».";
    const TEXTE_INVALIDE = "Un champ est invalide : le résultat affiché date de la dernière saisie valide.";
    const aResultat = () => !!zoneResultat.querySelector(".bilan, .verdict"); // un résultat de calcul est affiché (pas un message)
    // Bandeau « résultat daté » en tête de la zone de résultat, créé ou mis à jour (texte et liens des champs à corriger).
    function perime(texte = TEXTE_PERIME, ...suite) {
      let m = zoneResultat.querySelector(":scope > .perime");
      if (!m) {
        m = App.message("avertissement", "");
        m.classList.add("perime");
        zoneResultat.prepend(m);
      }
      m.replaceChildren(texte, ...suite);
    }
    // Résultat grisé (classe obsolete) tant qu'un champ est invalide : on garde l'ancien, on ne le remplace pas par une erreur.
    function griser(oui) {
      zoneResultat.classList.toggle("obsolete", oui);
      if (oui) zoneResultat.setAttribute("aria-busy", "true"); else zoneResultat.removeAttribute("aria-busy");
    }
    function signalerInvalides() {
      if (aResultat()) { perime(TEXTE_INVALIDE, " ", ...listeInvalides()); griser(true); }
      else {
        const m = App.message("avertissement", "");
        m.replaceChildren(...blocage("Corrigez les champs signalés en rouge : le calcul reprendra dès qu'ils seront valides. Champs à corriger :"));
        zoneResultat.replaceChildren(m);
      }
    }

    function relancer(parClic = false) {
      if (!App.pret) return;
      if (invalides.size) return signalerInvalides();
      griser(false);
      // même saisie que le résultat affiché : rien à recalculer (un clic sur « Calculer » ramène seulement le résultat à l'écran)
      if (calculee !== null && calculee === JSON.stringify(saisie) && aResultat()) {
        zoneResultat.querySelector(":scope > .perime")?.remove();
        if (parClic) montrer();
        return;
      }
      if (f.apercu && auto) apercu();
      const lancer = () => {
        minuterieCalcul = null;
        const r = App.calculer(ident, saisie);
        calculee = JSON.stringify(saisie);
        if (matPerime) { matPerime = null; afficherPerime(); }
        if (!r.ok) { zoneDecision.replaceChildren(); majResume(null); zoneResultat.replaceChildren(App.message("erreur", r.erreur)); if (parClic) montrer(); return; }
        afficherResultat(r.sortie);
        if (parClic) ctlSchema?.apresCalcul(); // clic sur « Calculer » : le schéma passe en bloc repliable au-dessus des résultats (pas pour le calcul de l'arrivée ni les recalculs automatiques)
        annoncer(phraseAnnonce(r.sortie), parClic);
        if (r.sortie.options) majOptions(r.sortie);
        if (!auto && f.apercu) apercu();
        if (parClic) setTimeout(montrer, 60); // après le nouveau schéma, qui change la hauteur de la page
      };
      if (auto) lancer();
      else { // laisse le navigateur afficher « Calcul en cours » avant un calcul de quelques dixièmes de seconde
        clearTimeout(minuterieCalcul); // clics répétés : un seul calcul, un seul message
        zoneResultat.replaceChildren(App.message("info", "Calcul en cours…"));
        minuterieCalcul = setTimeout(lancer, 30);
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

    let derniere = null; // dernier résultat affiché (redessiné quand on change la forme de la sécurité)
    function afficherResultat(s) {
      derniere = s;
      zoneDecision.replaceChildren(decision(s, ident));
      majResume(resumer(s));
      zoneResultat.replaceChildren(...construireResultat(s, ident, barreExports(), !auto));
    }
    // Après un clic sur « Calculer » : le résultat vient à l'écran et son cadre s'éclaire un instant.
    // `surTete` (barre résumé) : le focus va aussi à la tête de résultat « Décision ».
    function montrer(surTete = false) {
      const doux = !matchMedia("(prefers-reduced-motion: reduce)").matches;
      const col = titreResultat.closest(".colonne-resultat");
      // grand écran : la colonne de droite défile seule ; sinon c'est la page qui défile
      const interne = () => col && getComputedStyle(col).overflowY === "auto" && col.scrollHeight > col.clientHeight + 4;
      // le titre « Résultat » se range sous le menu collant (--barre) ; le bloc « Décision » est juste dessous
      const ecart = () => titreResultat.getBoundingClientRect().top - (interne() ? col.getBoundingClientRect().top + 4 : App.hautBarre() + 12);
      const aller = (behavior) => {
        if (interne()) col.scrollTo({ top: col.scrollTop + ecart(), behavior });
        else window.scrollBy({ top: ecart(), behavior });
      };
      // Mode guidé : le résultat ne fait pas sauter la page sous la carte (« Suivant » doit rester où on l'a vu) ; le guide amène
      // lui-même la page au verdict à l'étape qui le montre. Le bouton « Voir le résultat » (surTete) défile toujours.
      const guide = guideActif() && !surTete;
      if (!guide) {
        aller(doux ? "smooth" : "auto");
        // Un seul recalage final, sans animation : les graphiques ont fini de se dessiner et ont pu déplacer la page. Il n'a lieu que
        // si la personne n'a pas repris la main (molette, doigt, clavier) entre-temps, sinon il l'arracherait à sa lecture.
        let reprise = false;
        const noter = () => { reprise = true; };
        const evenements = ["wheel", "touchstart", "keydown", "pointerdown"];
        for (const e of evenements) window.addEventListener(e, noter, { passive: true, once: true });
        setTimeout(() => {
          for (const e of evenements) window.removeEventListener(e, noter);
          if (!reprise && !guideActif() && Math.abs(ecart()) > 24) aller("auto");
        }, 900);
      }
      zoneResultat.classList.remove("eclair");
      void zoneResultat.offsetWidth; // relance l'animation si le calcul est refait
      zoneResultat.classList.add("eclair");
      if (surTete) zoneDecision.firstElementChild?.focus({ preventScroll: true });
    }

    const phraseEtat = (t) => { const p = App.decimalesFr(String(t || "")); return /^[a-zà-ÿ]{2}/.test(p) ? p.charAt(0).toUpperCase() + p.slice(1) : p; };
    const nf = (x, chiffres = 3) => (Number.isFinite(x) ? App.exposants(String(Number(x.toPrecision(chiffres))).replace(".", ",")) : "∞");
    // réserve = 1 − taux en % ; un taux non nul arrondi à « 100 » s'écrit « > 99,9 » (100 % ferait croire à une charge nulle)
    const reserve = (taux) => { const r = nf(100 * (1 - taux)); return taux > 0 && r === "100" ? "> 99,9" : r; };

    // Phrase lue par le lecteur d'écran après un calcul : « Vérifié : 3 modes de ruine sur 3 admissibles », ou le verdict.
    function phraseAnnonce(s) {
      const crit = s.criteres || [];
      if (crit.length) {
        const ko = crit.filter((c) => !c.ok).length;
        if (ko) return `Non vérifié : ${ko} mode${ko > 1 ? "s" : ""} de ruine sur ${crit.length} non admissible${ko > 1 ? "s" : ""}`;
        const pastille = s.ok === true ? "Vérifié" : "Indicatif";
        return crit.length > 1 ? `${pastille} : ${crit.length} modes de ruine sur ${crit.length} admissibles` : `${pastille} : le mode de ruine est admissible`;
      }
      return (s.ok === true ? "Vérifié. " : s.ok === false ? "Non vérifié. " : "") + App.decimalesFr(String(s.status || ""));
    }

    // Diagramme des modes de ruine : une ligne par critère, barre du taux de travail, coefficient de sécurité ou marge s − 1
    // (résistance), ou réserve 1 − taux (durée, rigidité, vitesse, norme…). Les études d'une même page ont un sous-titre.
    function bilan(s, cle) {
      const crit = s.criteres || [];
      const ko = crit.filter((c) => !c.ok).length;
      const etat = s.ok === true ? "ok" : s.ok === false ? "ko" : "neutre";
      const pastille = { ok: "Vérifié", ko: "Non vérifié", neutre: "Indicatif" }[etat];
      const phrase = ko ? `${ko} mode${ko > 1 ? "s" : ""} de ruine non admissible${ko > 1 ? "s" : ""} sur ${crit.length}`
        : crit.length > 1 ? `Les ${crit.length} modes de ruine sont admissibles` : "Le mode de ruine est admissible";
      const echelle = Math.min(2, Math.max(1.25, ...crit.map((c) => c.taux * 1.08)));
      const pire = crit.reduce((m, c) => (c.taux > m.taux ? c : m), crit[0]);
      const lignes = [];
      let groupe = "";
      for (const c of crit) {
        if (c.groupe && c.groupe !== groupe) lignes.push(el("li", { class: "mode-groupe", texte: c.groupe }));
        groupe = c.groupe || "";
        const u = c.unite ? " " + c.unite : "";
        const barre = el("span", { class: "jauge", role: "img", "aria-label": `Taux de travail ${nf(100 * c.taux)} %`,
          aide: "Part de l'admissible utilisée. Le trait marque 100 % : au-delà, le mode n'est pas admissible." },
          el("span", { class: "remplie", style: `width:${(100 * Math.min(c.taux, echelle) / echelle).toFixed(1)}%` }),
          el("span", { class: "repere", style: `left:${(100 / echelle).toFixed(1)}%` }));
        const marge = c.genre === "resistance"
          ? (securiteEnMarge()
            ? [el("strong", { texte: c.s_obtenu === null ? "marge illimitée" : `marge ${nf(100 * (c.s_obtenu - 1))} %`, aide: "Marge de sécurité obtenue : s − 1, avec s la limite du matériau divisée par la valeur calculée." }),
              el("span", { texte: `demandée ${nf(100 * (c.s_demande - 1))} %` })]
            : [el("strong", { texte: `s = ${c.s_obtenu === null ? "∞" : nf(c.s_obtenu)}`, aide: "Coefficient de sécurité obtenu : la limite du matériau divisée par la valeur calculée." }),
              el("span", { texte: `demandé ${nf(c.s_demande)}` })])
          : [el("strong", { texte: c.taux <= 1 ? `réserve ${reserve(c.taux)} %` : `dépassement ${nf(100 * (c.taux - 1))} %`,
            aide: "Réserve : part de l'admissible encore libre (1 − taux), au plus 100 %. Ce n'est pas la marge de sécurité s − 1." })];
        // s < 1 : la valeur calculée dépasse déjà la limite du matériau (Re) ; le dire en clair (s − 1 ne passe jamais sous −100 %)
        if (c.genre === "resistance" && c.sens === "max" && c.s_obtenu > 0 && c.s_obtenu < 1)
          marge.push(el("span", { class: "depasse-limite", texte: `dépasse la limite du matériau de ${nf(100 * (1 / c.s_obtenu - 1))} %`,
            aide: "Valeur calculée divisée par la limite du matériau (Re, sans sécurité), moins 1." }));
        const lienCause = !c.ok || (etat === "neutre" && c === pire) ? boutonCause(cle, c, libelleMode(c, crit)) : null;
        const aideLigne = [barre, ...marge].map((x) => x.dataset && x.dataset.aide).filter(Boolean).join(" ");
        lignes.push(el("li", { class: "mode " + (c.ok ? "ok" : "ko") + (c === pire && crit.length > 1 ? " pire" : "") },
          // UN seul arrêt de tabulation par ligne : le nom du mode porte l'aide de la jauge et des chiffres (lecteur d'écran compris)
          el("span", { class: "mode-nom", texte: c.mode, tabindex: "0", aide: aideLigne }),
          el("span", { class: "mode-etat", texte: c.ok ? "Admissible" : "Non admissible" }),
          barre,
          el("span", { class: "mode-chiffres" },
            // taux sans unité d'une norme (effort / résistance ≤ 1) : le taux en % suffit
            (!c.unite && c.limite === 1) ? null : el("span", { texte: `${nf(c.valeur, 4)}${u} pour ${nf(c.limite, 4)}${u} ${c.sens === "max" ? "admissibles" : "requis"}` }),
            el("span", { texte: `taux ${nf(100 * c.taux)} %` }), marge),
          // mode non admissible (ou le plus sollicité d'un résultat « à vérifier ») : lien vers le champ qui l'influence le plus
          lienCause ? el("span", { class: "mode-cause" }, lienCause) : null));
      }
      return el("section", { class: "bilan " + etat },
        el("p", { class: "bilan-tete" }, el("span", { class: "verdict-etat", texte: pastille }), el("strong", { texte: phrase })),
        el("ul", { class: "modes" }, lignes),
        el("p", { class: "bilan-phrase", texte: phraseEtat(s.status) }));
    }

    // Ce que la tête de résultat et la barre résumé disent, calculé à partir des critères et du verdict déjà renvoyés :
    // verdict, mode dimensionnant (taux le plus élevé), coefficient de sécurité minimal (modes de résistance) ou réserve.
    function resumer(s) {
      const crit = s.criteres || [];
      const ko = crit.filter((c) => !c.ok);
      const niveau = ko.length || s.ok === false ? "ko" : s.ok === true ? "ok" : crit.length ? "neutre" : "info";
      const plusSollicite = (liste) => liste.reduce((m, c) => (m === null || tauxDe(c) > tauxDe(m) ? c : m), null);
      const pire = plusSollicite(crit), pireKo = plusSollicite(ko);
      const finis = crit.filter((c) => c.genre === "resistance" && Number.isFinite(c.s_obtenu));
      const smin = finis.reduce((m, c) => (m === null || c.s_obtenu < m.s_obtenu ? c : m), null);
      const enMarge = securiteEnMarge();
      let court = "";
      if (smin) court = enMarge ? `marge min ${nf(100 * (smin.s_obtenu - 1))} %` : `s min ${nf(smin.s_obtenu)}`;
      else if (pire) court = tauxDe(pire) <= 1 ? `réserve ${reserve(pire.taux)} %` : `dépassement ${nf(100 * (tauxDe(pire) - 1))} %`;
      return { crit, niveau, pire, pireKo, smin, enMarge, court };
    }

    // Tête de résultat : verdict (texte + icône + couleur), coefficient de sécurité minimal ou réserve, mode dimensionnant,
    // paramètre le plus influent (quand CAUSES le désigne), action conseillée. Texte seul : aucun graphique n'est nécessaire.
    function decision(s, cle) {
      const r = resumer(s);
      const [icone, mot] = VERDICTS[r.niveau];
      const faits = [];
      const fait = (titre, ...valeur) => faits.push(el("div", {}, el("dt", { texte: titre }), el("dd", {}, ...valeur)));
      if (r.smin) {
        const c = r.smin;
        fait(r.enMarge ? "Marge de sécurité minimale" : "Coefficient de sécurité minimal",
          el("strong", { texte: r.enMarge ? `${nf(100 * (c.s_obtenu - 1))} %` : `s = ${nf(c.s_obtenu)}` }),
          el("span", { class: "decision-sous", texte: r.enMarge ? `demandée ${nf(100 * (c.s_demande - 1))} %` : `demandé ${nf(c.s_demande)}` }));
      } else if (r.pire) {
        fait(tauxDe(r.pire) <= 1 ? "Réserve minimale" : "Dépassement", el("strong", { texte: tauxDe(r.pire) <= 1 ? `${reserve(r.pire.taux)} %` : `${nf(100 * (tauxDe(r.pire) - 1))} %` }));
      }
      if (r.pire) {
        fait("Mode dimensionnant", el("strong", { texte: libelleMode(r.pire, r.crit) }), el("span", { class: "decision-sous", texte: `taux ${nf(100 * tauxDe(r.pire))} %` }));
        // paramètre le plus influent : seulement un champ précis de CAUSES (un groupe de champs n'est pas un paramètre)
        const cibles = causesDe(cle, r.pire);
        const champ = cibles && !cibles[0].startsWith("g:") ? cibles[0] : null;
        if (champ) fait("Paramètre le plus influent", el("button", { type: "button", class: "lien-champ", texte: nomChamp(champ),
          aide: "Va à ce champ.", onclick: () => { if (!aller(champ)) signaler("info", "Le champ n'est pas affiché avec la saisie actuelle."); } }));
      }
      let action = "Vérifiez les hypothèses.";
      if (r.niveau === "ko" && r.pireKo) {
        const nom = libelleMode(r.pireKo, r.crit);
        action = r.pireKo.genre === "resistance" ? `Réduire la charge ou augmenter la section pour « ${nom} ».` : `Revoir la charge ou les dimensions pour « ${nom} ».`;
      } else if (r.niveau === "ok") action = "Aucune action requise : tous les critères sont admissibles.";
      else if (r.niveau === "info") action = "Ce calcul donne des valeurs, sans critère de conformité.";
      const avert = (AVERTISSEMENTS[cle] || (() => null))(saisie); // limite du modèle que la saisie franchit
      const cause = r.niveau === "ko" && r.pireKo ? boutonCause(cle, r.pireKo, libelleMode(r.pireKo, r.crit)) : null;
      return el("section", { class: "decision " + r.niveau, role: "group", "aria-label": "Décision", tabindex: "-1" },
        el("h3", { class: "cache", texte: "Décision" }),
        el("p", { class: "decision-verdict" }, el("span", { class: "decision-etat" }, el("span", { "aria-hidden": "true", texte: icone }), " " + mot)),
        faits.length ? el("dl", { class: "decision-faits" }, faits) : null,
        avert ? el("p", { class: "decision-avert", role: "note" }, el("span", { "aria-hidden": "true", texte: "⚠ " }), avert) : null,
        el("p", { class: "decision-action" }, action, cause ? " " : null, cause));
    }

    // Barre résumé du bas d'écran (sous 1100 px) : montrée quand ni le titre « Résultat » ni la tête de résultat ne sont à l'écran.
    // Son texte (role="status") se met à jour 800 ms après le dernier calcul, comme la zone d'annonce du bilan.
    let resumeDispo = false, texteResume = "", minuterieResume = null;
    const vu = { bloc: false, titre: true, decision: false }; // zones de la page actuellement à l'écran
    // pas de role="status" ici : la zone d'annonce du bilan (« annonce ») est la seule région vocale, le verdict n'est pas lu deux fois
    const barreResume = el("div", { class: "barre-resume neutre", hidden: true },
      el("span", { class: "barre-resume-texte" }),
      el("button", { type: "button", class: "barre-resume-bouton", texte: "Voir le résultat",
        aide: "Fait défiler jusqu'à la tête du résultat.", onclick: () => montrer(true) }));
    // Pendant le mode guidé la barre se range : elle cachait le champ désigné, sous la carte du guide (js/guide.js)
    const guideActif = () => document.body.classList.contains("guide-actif");
    function visibiliteResume() {
      const voir = resumeDispo && vu.bloc && !vu.titre && !(vu.decision && zoneDecision.firstElementChild) && !guideActif();
      barreResume.hidden = !voir;
      if (voir) barresVisibles.add(bloc); else barresVisibles.delete(bloc);
      majPageResume();
    }
    // Saisie modifiée depuis le dernier calcul (ou champ invalide) : la barre ne rend plus de verdict, ni couleur, ni « Conforme ».
    let resumeCourant = null, resumeAncien = false;
    function ecrireResume(immediat = false) {
      clearTimeout(minuterieResume);
      const r = resumeCourant;
      if (!r) return;
      const ecrire = () => {
        const calcul = !!minuterieCalcul; // calcul différé en cours : « à recalculer » serait faux
        const ancien = resumeAncien && !calcul;
        const [icone, mot] = ancien ? ["↻", "Résultat ancien — à recalculer"] : calcul ? ["…", "Calcul en cours…"] : VERDICTS[r.niveau];
        const texte = ancien || calcul ? mot : [mot, r.court].filter(Boolean).join(" · ");
        barreResume.classList.remove("ok", "ko", "neutre", "info");
        if (!ancien && !calcul) barreResume.classList.add(r.niveau);
        barreResume.classList.toggle("ancien", resumeAncien);
        if (texte === texteResume) return; // même phrase : rien de neuf à dire
        texteResume = texte;
        barreResume.firstElementChild.replaceChildren(el("span", { "aria-hidden": "true", texte: icone + " " }), texte);
      };
      if (!texteResume || immediat) ecrire(); else minuterieResume = setTimeout(ecrire, 800);
    }
    function majResume(r) { // r : résultat de resumer(), ou null (plus de résultat)
      clearTimeout(minuterieResume);
      resumeDispo = !!r;
      resumeCourant = r;
      if (!r) { texteResume = ""; visibiliteResume(); return; }
      resumeAncien = false; // un résultat tout neuf : il remplace tout de suite « Résultat ancien » ou « Calcul en cours »
      ecrireResume(texteResume === "Résultat ancien — à recalculer" || texteResume === "Calcul en cours…");
      visibiliteResume();
    }
    document.addEventListener("mecastruct:guide", function surGuide() {
      if (!bloc.isConnected) { document.removeEventListener("mecastruct:guide", surGuide); return; }
      visibiliteResume();
    });
    function surveillerResume(essais = 0) {
      if (!window.IntersectionObserver || blocsResume.has(bloc)) return;
      if (!bloc.isConnected) { if (essais < 50) setTimeout(() => surveillerResume(essais + 1), 100); return; } // pas encore dans la page
      const io = new IntersectionObserver((entrees) => {
        for (const e of entrees) {
          if (e.target === titreResultat) vu.titre = e.isIntersecting;
          else if (e.target === zoneDecision) vu.decision = e.isIntersecting;
          else vu.bloc = e.isIntersecting;
        }
        visibiliteResume();
      });
      blocsResume.set(bloc, io);
      io.observe(titreResultat);
      io.observe(zoneDecision);
      io.observe(bloc);
      majPageResume();
    }
    // Résultat précédent : pendant un calcul, un résultat daté ou grisé, la tête de résultat reste affichée mais le dit.
    new MutationObserver(() => {
      const ancien = zoneResultat.classList.contains("obsolete") || !!zoneResultat.querySelector(":scope > .perime")
        || (!!zoneDecision.firstElementChild && !aResultat());
      zoneDecision.classList.toggle("ancien", ancien);
      if (ancien !== resumeAncien) { resumeAncien = ancien; ecrireResume(); }
      for (const a of bloc.querySelectorAll(".avert-ancien")) a.hidden = !ancien; // exports et lien : ils reprennent la saisie actuelle
    }).observe(zoneResultat, { childList: true, attributes: true, attributeFilter: ["class"] });

    // Contrôles oui / non sans valeur limite (conditions de montage d'un train épicycloïdal).
    const controles = (s) => ((s.controles || []).length ? el("section", { class: "bilan neutre" },
      el("p", { class: "bilan-tete" }, el("strong", { texte: s.titre_controles || "Contrôles" })),
      el("ul", { class: "modes" }, s.controles.map((c) => el("li", { class: "mode " + (c.ok ? "ok" : "ko") },
        el("span", { class: "mode-nom", texte: `${c.nom} = ${App.decimalesFr(c.valeur)}` }),
        el("span", { class: "mode-etat", texte: c.ok ? "Respectée" : "Non respectée" }))))) : "");

    function construireResultat(s, cle, exports = "", avecHeure = false, avecDecision = false) {
      const niveau = s.ok === true ? "succes" : s.ok === false ? "erreur" : "info";
      const prefixe = s.ok === true ? "Vérifié. " : s.ok === false ? "Non vérifié. " : "";
      let verdict;
      if ((s.criteres || []).length) verdict = bilan(s, cle);
      else {
        verdict = App.message(niveau, prefixe + App.decimalesFr(s.status));
        verdict.classList.add("verdict");
      }
      const h = new Date();
      const heure = el("p", { class: "legende heure", texte: `Calculé à ${h.getHours()} h ${String(h.getMinutes()).padStart(2, "0")} min ${String(h.getSeconds()).padStart(2, "0")} s` });
      const liste = [];
      for (const g of s.figures || []) liste.push({ id: "fig-" + g.titre, titre: g.titre, rendu: (p) => p.append(App.figure(g.figure)) });
      if (s.figure) liste.push({ id: "graphique", titre: "Graphique", rendu: (p) => p.append(App.figure(s.figure)) });
      const tables = Object.entries(s.tables || {});
      if (tables.length) liste.push({ id: "synthese", titre: tables.length > 1 ? "Tableaux" : "Synthèse", rendu: (p) => tables.forEach(([nom, t]) => p.append(App.tableau(t, tables.length > 1 ? nom : null, nom))) });
      if ((s.explications || []).length || (s.latex || []).length || (s.rapport || []).length) {
        liste.push({ id: "explications", titre: "Explications du calcul", rendu: (p) => explications(p, s) });
      }
      const metriques = (s.metriques || []).length
        ? el("div", { class: "metriques" }, s.metriques.map(([n, v]) => el("div", { class: "metrique" }, el("span", { texte: n }), el("strong", { texte: App.decimalesFr(v) }))))
        : null;
      return [avecDecision ? decision(s, cle) : "", verdict, controles(s), avecHeure ? heure : "", exports, metriques || "", liste.length ? App.onglets(liste, cle) : ""];
    }

    // Un résultat complémentaire dont la saisie a changé depuis le calcul est signalé (jamais effacé en silence).
    function marquerExtras() {
      for (const { empreinte, bloc } of Object.values(extras)) {
        const ancien = bloc.querySelector(".perime");
        if (empreinte === JSON.stringify(saisie)) ancien?.remove();
        else if (!ancien) {
          const m = App.message("avertissement", "Saisie modifiée depuis ce calcul : relancez-le pour l'actualiser.");
          m.classList.add("perime");
          bloc.querySelector("h2").after(m);
        }
      }
    }

    function explications(p0, s) {
      const p = el("div", { class: "corps-explications" });
      p0.append(App.boutonImage(p, "explications.png"), p);
      if ((s.explications || []).length) {
        p.append(el("h3", { class: "titre-mineur", texte: "Équations appliquées à vos données" }),
          el("p", { class: "legende", texte: "Chaque grandeur est refaite à la main, puis comparée au résultat du solveur." }));
        for (const r of s.explications) {
          if (r.titre) { p.append(el("h4", { class: "sous-titre", texte: r.titre })); continue; }
          p.append(el("p", { class: "explication", texte: r.label }), App.formule(r.latex),
            el("p", { class: "legende " + (r.ok ? "concorde" : "ecart"), texte: App.decimalesFr(r.note) }));
        }
      }
      if ((s.latex || []).length) p.append(el("h3", { class: "titre-mineur", texte: "Formules appliquées à vos données" }), ...s.latex.map(App.formule));
      if ((s.blocs || []).length) {
        const d = el("details", { class: "groupe" }, el("summary", { texte: "Équations écrites par le solveur" }));
        for (const b of s.blocs) d.append(el("h4", { texte: b.nom }), ...b.formules.map(App.formule));
        p.append(d);
      }
      if ((s.rapport || []).length) p.append(el("h3", { class: "titre-mineur", texte: "Démarche" }), el("ul", {}, s.rapport.filter((l) => String(l).trim()).map((l) => el("li", { texte: App.decimalesFr(l) }))));
    }

    // Petit avertissement sous les exports et le lien de l'étude : visible tant que le résultat affiché n'est plus celui de la saisie
    // (saisie modifiée, champ invalide). Les boutons restent actifs : c'est un rappel, pas un blocage.
    const avertAncien = (texte) => el("p", { class: "legende avert-ancien", role: "note", hidden: !resumeAncien, texte: "⚠ " + texte });
    // Exports placés juste sous le verdict : dossier de validation, bloc-notes, Excel de validation.
    function barreExports() {
      const boutons = (f.dossier || f.dossierMachine) ? boutonDossier() : [];
      if (f.exports) {
        const note = el("button", { type: "button", class: "secondaire", texte: "Bloc-notes (.txt)",
          aide: "Données, modes de ruine, résultats et démarche dans un fichier texte lisible partout.", onclick: () => {
            const r = App.calculer(ident + ".texte", { ...saisie, _securite: App.memoire.lire("securite", "coef") });
            if (r.ok) App.telecharger(r.sortie.nom, r.sortie.texte, "text/plain;charset=utf-8");
            else signaler("erreur", r.erreur);
          } });
        const classeur = el("button", { type: "button", class: "secondaire", texte: "Excel de validation",
          aide: "Classeur simple : vos données, le calcul refait par des formules Excel à côté de MecaStruct, et les coefficients de sécurité. Pour les poutres, treillis et ossatures, le solveur n'est pas refait : seuls les critères sont en formules." });
        classeur.addEventListener("click", async () => {
          classeur.disabled = true;
          try {
            if (!await App.paquets(["openpyxl"])) return signaler("erreur", "L'export Excel n'a pas pu se charger.");
            const r = App.calculer(ident + ".validation", saisie);
            if (!r.ok) return signaler("erreur", r.erreur);
            const octets = Uint8Array.from(atob(r.sortie.base64), (c) => c.charCodeAt(0));
            App.telecharger(r.sortie.nom, octets, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
          } finally { classeur.disabled = false; }
        });
        boutons.push(note, classeur);
      }
      if (comparaison && boutons.length) boutons.push(comparaison.bouton());
      if (!boutons.length) return "";
      const sans = (f.dossier || f.dossierMachine) ? null : el("span", { class: "legende", texte: "Cette page n'a pas de dossier de validation." });
      return el("div", { class: "exports" }, el("span", { class: "exports-titre", texte: "Justifier ce calcul" }), el("div", { class: "ligne" }, boutons),
        avertAncien("Résultat précédent : l'export reprend la saisie actuelle, pas le résultat affiché. Recalculez d'abord."), sans);
    }

    // Dossier de validation : télécharger le fichier HTML, ou l'ouvrir prêt à imprimer (Imprimer, Enregistrer en PDF).
    function boutonDossier() {
      const aide = "Refait chaque grandeur à la main, la compare au solveur et réunit données, hypothèses et résultats dans un fichier à joindre à votre note de calcul.";
      const fabriquer = (b, titre, suite, fenetre) => {
        b.disabled = true;
        b.textContent = "Préparation du dossier…";
        const fin = () => { b.disabled = false; b.textContent = titre; };
        setTimeout(async () => {
          if (!await App.paquets(["jinja2", "scipy", "shapely"])) { fin(); fenetre?.close(); return signaler("erreur", "Le générateur de dossier n'a pas pu se charger."); }
          const r = App.calculer(ident + ".dossier", saisie);
          fin();
          if (!r.ok) { fenetre?.close(); return signaler("erreur", r.erreur); }
          suite(r.sortie, fenetre);
        }, 30);
      };
      const telecharger = el("button", { type: "button", class: "secondaire", texte: "Dossier de validation (HTML)", aide });
      telecharger.addEventListener("click", () => fabriquer(telecharger, "Dossier de validation (HTML)", (d) => App.telecharger(d.nom, d.html, "text/html")));
      const NOM_IMPRIMER = "Dossier à imprimer (PDF via Imprimer)";
      const imprimer = el("button", { type: "button", class: "secondaire", texte: NOM_IMPRIMER,
        aide: aide + " Ouvre le dossier ; choisissez Imprimer puis Enregistrer au format PDF (aucun fichier PDF n'est créé directement). Les formules mathématiques ne s'affichent complètement qu'avec une connexion Internet (KaTeX)." });
      imprimer.addEventListener("click", () => {
        const fenetre = window.open("", "_blank"); // ouverte tout de suite : après un calcul, le navigateur la bloquerait
        fabriquer(imprimer, NOM_IMPRIMER, (d, w) => {
          if (!w) return App.telecharger(d.nom, d.html, "text/html"); // fenêtre bloquée : téléchargement à la place
          w.location.href = URL.createObjectURL(new Blob([d.html], { type: "text/html" }));
        }, fenetre);
      });
      return [telecharger, imprimer];
    }

    // Bouton flottant en bas à gauche : copie l'étude (consigne + note de calcul) pour la coller dans une IA, qui présente
    // le problème avant qu'on lui pose des questions. Rien n'est envoyé : c'est l'utilisateur qui colle. Il vit dans le
    // bloc de la page : il disparaît avec elle.
    function boutonIA() {
      if (!f.exports) return null;
      const lien = (texte, href) => el("a", { class: "bouton secondaire", href, target: "_blank", rel: "noopener noreferrer", texte });
      const TEXTE_IA = "Étude copiée : collez-la (Ctrl+V) dans l'IA. Elle présente d'abord le problème, puis posez-lui vos questions.";
      // zone « status » : le texte y est écrit après l'ouverture du panneau, sinon un texte déjà là n'est pas annoncé
      const phraseIA = el("p", { role: "status", "aria-live": "polite" });
      const panneau = el("div", { class: "ia-panneau", role: "dialog", "aria-label": "Demander à une IA", hidden: true },
        phraseIA,
        el("div", { class: "ligne" }, lien("Ouvrir Claude", "https://claude.ai/new"), lien("Ouvrir ChatGPT", "https://chatgpt.com/")));
      // languette au bord gauche : réduite à une flèche au repos, déployée (libellé + panneau) après un clic
      const bouton = el("button", { type: "button", class: "ia-bouton", "aria-expanded": "false", "aria-label": "Demander à une IA",
        aide: "Copie l'étude (données, résultats, démarche) avec une consigne : l'IA présente le problème, puis vous lui posez vos questions. Rien n'est envoyé : vous collez le texte dans Claude ou ChatGPT." },
        el("span", { class: "ia-fleche", "aria-hidden": "true", texte: "›" }),
        el("span", { class: "ia-libelle", texte: "Demander à une IA" }));
      const conteneur = el("div", { class: "ia-flottant" }, panneau, bouton);
      // première visite de la session : le libellé complet se montre 5 s, puis la languette se réduit à sa flèche
      let vu = false;
      try { vu = sessionStorage.getItem("mecastruct.ia.vu") === "1"; sessionStorage.setItem("mecastruct.ia.vu", "1"); } catch (e) { /* sans mémoire de session */ }
      if (!vu) { conteneur.classList.add("annonce"); setTimeout(() => conteneur.classList.remove("annonce"), 5000); }
      // rendreFocus : le focus revient au bouton qui a ouvert le panneau (jamais au body), sauf si la personne a cliqué ailleurs
      const fermer = (rendreFocus = false) => {
        const dedans = conteneur.contains(document.activeElement);
        panneau.hidden = true; phraseIA.textContent = ""; conteneur.classList.remove("ouvert"); bouton.setAttribute("aria-expanded", "false");
        if (rendreFocus || dedans) bouton.focus({ preventScroll: true });
      };
      bouton.addEventListener("click", async () => {
        if (!panneau.hidden) return fermer(true); // second clic : on referme et on réduit
        const r = App.calculer(ident + ".ia", { ...saisie, _securite: App.memoire.lire("securite", "coef") });
        if (!r.ok) return signaler("erreur", r.erreur);
        const ok = await App.copier(r.sortie.texte);
        App.confirmer(null, ok, "Étude copiée", "Copie impossible", "Étude copiée : collez-la dans l'IA (Ctrl+V).");
        panneau.hidden = !ok;
        conteneur.classList.toggle("ouvert", ok);
        bouton.setAttribute("aria-expanded", String(ok));
        if (ok) setTimeout(() => { phraseIA.textContent = TEXTE_IA; }, 60); // annoncé : « Étude copiée… »
      });
      // fermeture : Échap ou clic ailleurs (pas le défilement : sur mobile il suit un geste du doigt) ; les écouteurs se
      // retirent d'eux-mêmes quand la page a disparu
      const surDocument = (e) => {
        if (!conteneur.isConnected) {
          document.removeEventListener("keydown", surDocument); document.removeEventListener("click", surDocument);
          return;
        }
        // Échap : un seul composant réagit par appui (le guide ignore un Échap déjà pris ici)
        if (e.type === "keydown") { if (e.key === "Escape" && !panneau.hidden) { e.preventDefault(); fermer(true); } }
        else if (!panneau.hidden && (!conteneur.contains(e.target) || (e.target.closest && e.target.closest(".onglets")))) fermer();
      };
      document.addEventListener("keydown", surDocument);
      document.addEventListener("click", surDocument);
      return conteneur;
    }

    const titreResultat = App.titreImage("Résultat", () => zoneResultat.querySelector(".bilan, .verdict"), "resultat.png", "titre-resultat");
    dessinerChamps();
    // Pages à schéma : AVANT le premier calcul, le schéma est affiché à droite des champs (au-dessus d'eux sous 1100 px).
    // APRÈS un calcul réussi, la colonne de droite ne montre que les résultats : le schéma devient un bloc compact repliable
    // au-dessus d'eux (replié, sauf choix mémorisé pour la page). Rien n'est retiré du DOM : replié, le schéma reste en place
    // (le CSS le réduit à zéro hauteur et le sort du clavier) ; les figures Plotly sont remises à la taille de leur cadre à l'affichage.
    function blocSchema(bloc, colSaisie, colResultat) {
      const cleMemo = "schema." + ident;
      const gardee = App.memoire.lire(cleMemo, null);
      let visible = !!gardee && typeof gardee === "object" && gardee.visible === true; // « schéma visible après calcul »
      let apres = false; // un calcul a réussi : la page est en mode « résultats »
      const idCorps = "schema-corps-" + ident;
      const libelle = el("span");
      const fleche = el("span", { class: "schema-fleche", "aria-hidden": "true" });
      const bascule = el("button", { type: "button", class: "schema-bascule", "aria-controls": idCorps, aide: "Affiche ou masque le schéma de la saisie." }, libelle, fleche);
      const coche = el("input", { type: "checkbox" });
      coche.checked = !!gardee; // un choix mémorisé existe pour cette page
      const memo = el("label", { class: "panneau-memo", aide: "Si cochée, ce navigateur se souvient, pour cette page, de garder le schéma visible après le calcul (ou de ne montrer que les résultats). Sinon le schéma se replie à chaque nouveau calcul." },
        coche, "Mémoriser ce choix pour cette page");
      const corps = el("div", { id: idCorps, class: "schema-corps" },
        App.titreImage("Schéma", () => zoneSchema.querySelector(".js-plotly-plot"), "schema.png"), zoneSchema);
      const cadre = el("section", { class: "bloc-schema", "aria-label": "Représentation" },
        el("div", { class: "schema-tete" }, bascule, memo), corps);
      // Plotly mesure son cadre : on lui « rappelle » la taille une fois le schéma (ré)affiché ou déplacé
      const redimensionner = () => requestAnimationFrame(() => setTimeout(() => {
        window.dispatchEvent(new Event("resize"));
        App.redimensionnerFigures(document);
      }, 50));
      const appliquer = () => {
        const replie = apres && !visible;
        cadre.classList.toggle("apres", apres);
        cadre.classList.toggle("replie", replie);
        bascule.setAttribute("aria-expanded", String(!replie));
        libelle.textContent = replie ? "Afficher le schéma" : "Masquer le schéma";
        fleche.textContent = replie ? "▸" : "▾";
      };
      // avant le calcul : au-dessus des champs sous 1100 px ; sinon en tête de la colonne de résultat (juste après « Calculer »)
      const placer = () => {
        if (petitEcran.matches && !apres) { if (cadre.nextElementSibling !== colSaisie) bloc.insertBefore(cadre, colSaisie); }
        else if (cadre.parentNode !== colResultat) colResultat.insertBefore(cadre, titreResultat);
      };
      const retenir = () => { if (coche.checked) App.memoire.ecrire(cleMemo, { visible }); else App.memoire.oublier(cleMemo); };
      bascule.addEventListener("click", () => { visible = !visible; appliquer(); retenir(); if (visible) redimensionner(); });
      coche.addEventListener("change", retenir);
      const surFenetre = () => {
        if (!bloc.isConnected) { petitEcran.removeEventListener("change", surFenetre); return; }
        placer(); redimensionner();
      };
      petitEcran.addEventListener("change", surFenetre);
      appliquer(); placer();
      return {
        cadre,
        // Appelé après un calcul réussi demandé par un clic sur « Calculer » : à l'arrivée sur la page, le schéma reste à droite
        // des champs. Sans choix mémorisé, il se replie à chaque clic ; avec la case cochée, le choix de l'utilisateur est gardé.
        apresCalcul() {
          if (!coche.checked) visible = false;
          apres = true;
          appliquer(); placer();
          if (visible) redimensionner();
        },
      };
    }
    const colSaisie = el("div", { class: "colonne-saisie" }, formulaire);
    const colResultat = el("div", { class: "colonne-resultat" },
      auto ? null : el("div", { class: "actions-schema" }, el("button", { type: "button", class: "primaire", texte: "Calculer", aide: "Lance le calcul.", onclick: () => relancer(true) })),
      titreResultat, annonce, zoneDecision, zoneResultat, zoneExtras);
    const bloc = el("div", { class: "calcul" + (f.apercu ? " avec-schema" : "") }, boutonIA(), barreResume, colSaisie, colResultat);
    if (f.apercu) ctlSchema = blocSchema(bloc, colSaisie, colResultat);
    const lien = App.lienEtude();
    if (lien && lien.calcul === ident && App.pret) {
      App.oublierLien();
      App.decompresser(lien.etude).then((texte) => { if (bloc.isConnected) appliquer(texte, "Lien de partage"); })
        .catch(() => {
          if (!bloc.isConnected) return; // page quittée pendant la lecture du lien
          signaler("erreur", "Lien de partage illisible ou incomplet : la page montre ses valeurs de départ.");
          if (auto) relancer(); else zoneResultat.replaceChildren(App.message("info", "Renseignez les données, puis cliquez sur « Calculer »."));
        });
    } else if (App.pret) {
      if (auto) setTimeout(relancer, 0);
      else {
        if (f.lent) { // calcul long : on attend le clic
          setTimeout(apercu, 0);
          zoneResultat.replaceChildren(App.message("info", "Renseignez les données, puis cliquez sur « Calculer »."));
        } else setTimeout(() => relancer(), 0); // le résultat de l'exemple (ou de la dernière saisie) est là dès l'arrivée
      }
    }
    surveillerResume();
    App.guide?.monter(ident, f, bloc, { saisie: () => saisie, formulaire, resultat: zoneResultat, auto, apercu: !!f.apercu });
    comparaison = App.comparer?.monter(ident, f, bloc, { saisie: () => saisie, verifierNombre, auto }) || null;
    return bloc;
  }

  App.genre("machine", async (contenu, page, { pret, perime = () => false }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) {
      contenu.append(App.attente("Le calcul se charge : les champs apparaîtront dans quelques secondes.", page));
      return;
    }
    if (page.pont) {
      const attente = App.message("info", "Chargement des bibliothèques de cette page (scipy, shapely)… quelques secondes la première fois.");
      contenu.append(attente);
      const prete = await App.preparer(page);
      if (perime()) return; // page quittée pendant le chargement : rien ne s'ajoute à la page courante
      if (!prete) {
        attente.replaceWith(App.messageEchec("Les bibliothèques de cette page n'ont pas pu se charger. Vérifiez la connexion Internet, puis réessayez."));
        return;
      }
      attente.remove();
      lireFormulaires(true);
    }
    const tous = lireFormulaires(true); // toujours à jour : un matériau ajouté dans la base doit apparaître ici
    const lien = App.lienEtude();
    if (lien && page.calculs.includes(lien.calcul)) App.memoire.ecrire("onglet.page." + page.id, lien.calcul); // ouvre l'onglet du lien
    if (!tous || page.calculs.some((id) => !tous[id])) {
      contenu.append(App.message("erreur", "Les formulaires de cette page n'ont pas pu être lus."));
      return;
    }
    if (page.calculs.length === 1) contenu.append(blocCalcul(page.calculs[0], tous[page.calculs[0]]));
    else contenu.append(App.onglets(page.calculs.map((id) => ({ id, titre: tous[id].titre, rendu: (p) => p.append(blocCalcul(id, tous[id])) })), "page." + page.id));
    contenu.append(el("p", { class: "legende lien-glossaire" }, el("a", { href: "#/glossaire", texte: "Voir le glossaire" })));
  });
})();
