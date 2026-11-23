"use strict";
// Recherche globale : un bouton loupe dans la barre du menu (toujours visible), raccourcis « / » et Ctrl+K, une liste de résultats
// au clavier (modèle ARIA « combobox » + « listbox » avec aria-activedescendant). Elle ne calcule rien : elle ouvre `#/<page>`
// (et, pour une page à onglets, l'onglet du calcul cherché) puis place le focus sur le titre de la page.
//
// La table ci-dessous est écrite à la main : une ligne = une page (et un onglet éventuel), une raison courte affichée sous le
// résultat, puis les mots qui y mènent (séparés par « | »). Les mots sont comparés sans accents ni majuscules ; un début de mot,
// un pluriel ou un morceau de mot suffit. Ajouter un synonyme = ajouter un mot à la bonne ligne.

(() => {
  const { el } = App;

  // [page, onglet (identifiant du calcul, "" si la page n'en a qu'un), étiquette, raison, mots]
  const TABLE = [
    // ---- Structures
    ["poutres", "beam", "Poutre 2D", "Flèche, réactions d'appui et efforts d'une poutre",
      "poutre|flèche|flèche maximale|déformée|réaction|réactions d'appui|appui|appuis|charge répartie|charge ponctuelle|console|encastrement|hyperstatique|isostatique|moment fléchissant|effort tranchant|effort normal|diagramme des efforts|contrainte de flexion|contrainte|coefficient de sécurité|limite élastique|rdm|résistance des matériaux"],
    ["poutres", "beam", "Eurocode 3", "Vérification d'une poutre acier selon l'Eurocode 3 (EN 1993-1-1)",
      "eurocode 3|eurocode|ec3|en 1993|en 1993-1-1|nf en 1993|acier de construction|classe de section|profilé|profilé IPE|profilé HEA|ipe|hea|heb|upn"],
    ["poutres", "beam", "Fatigue", "Vérification en fatigue d'une poutre (Kf, catégories de détail)",
      "fatigue|goodman|diagramme de goodman|haigh|endurance|limite d'endurance|contrainte alternée|contrainte moyenne|wöhler|courbe de wöhler|kf|concentration de contrainte|kt|entaille|catégorie de détail|en 1993-1-9"],
    ["poutres", "beam", "Tige filetée", "Vis ou tige filetée : section résistante d'un filetage ISO (ISO 898-1, ISO 68-1)",
      "vis|tige filetée|boulon|filetage|filetage métrique|iso 898-1|iso 898|iso 68-1|iso 68|iso 724|section résistante|pas gros|pas fin|m8|m10|m12|m16"],
    ["poutres", "beam", "Combinaisons", "Combinaisons de charges, enveloppe et charge mobile",
      "combinaison|combinaisons|enveloppe|charge mobile|pont roulant|poids propre"],
    ["poutres", "ossature", "Ossature 3D", "Ossature 3D : barres, nœuds, appuis et efforts internes",
      "ossature|portique|structure 3d|cadre|barres|noeud|nœud|vue 3d|3d"],
    ["treillis", "", "", "Efforts dans les barres et déplacements des nœuds d'un treillis",
      "treillis|barre|barres|noeud|nœud|articulation|ferme|poutre en treillis|effort dans les barres"],
    ["flambage", "", "", "Charge critique d'Euler, courbes de flambement de l'Eurocode 3, élancement et conditions aux limites",
      "flambage|flambement|euler|charge critique|élancement|longueur de flambement|colonne|poteau|buckling|condition aux limites|stabilité|eurocode 3 flambement|flambement eurocode 3|ec3 flambement|courbe de flambement|courbes de flambement|courbe a0|coefficient de réduction|nb,rd|en 1993-1-1 6.3.1|6.3.1"],
    // ---- Sections et contraintes
    ["sections-page", "", "", "Aire, centre de gravité, inerties et modules d'une section",
      "section|sections|aire|centre de gravité|barycentre|inertie|moment quadratique|module de flexion|module de résistance|rayon de giration|section composée|huygens|steiner|profilé|profilé IPE|profilé HEA|ipe|hea|heb|upn|tube|rectangle|cercle"],
    ["sollicitations", "tra", "Traction", "Contrainte et allongement en traction ou compression simple",
      "traction|compression|allongement|contrainte normale|contrainte|contrainte admissible|coefficient de sécurité"],
    ["sollicitations", "cis", "Cisaillement", "Cisaillement : clavette, goupille, rivet, contrainte tangentielle",
      "cisaillement|clavette|goupille|rivet|contrainte tangentielle|jourawski|pression de matage|matage|arbre"],
    ["sollicitations", "tor", "Torsion", "Torsion d'un arbre : contrainte, angle de torsion, couple",
      "torsion|moment de torsion|couple|angle de torsion|arbre|arbre de transmission|contrainte de cisaillement"],
    ["sollicitations", "fle", "Flexion", "Flexion simple : moment fléchissant, contrainte, flèche",
      "flexion|moment fléchissant|moment|contrainte de flexion|flèche|module de flexion|inertie"],
    ["tenseurs", "", "", "Contraintes principales, cercle de Mohr, Von Mises et Tresca",
      "tenseur|tenseurs|contrainte principale|contraintes principales|cercle de mohr|mohr|von mises|tresca|rankine|critère de rankine|contrainte normale maximale|critère|critère de plasticité|contrainte équivalente|état de contrainte|contrainte plane|cisaillement maximal"],
    ["hooke", "hoo", "Hooke", "Loi de Hooke généralisée : contraintes et déformations",
      "hooke|loi de hooke|déformation|module d'young|module de young|coefficient de poisson|poisson|élasticité|contrainte"],
    ["hooke", "jau", "Jauges", "Rosettes de jauges de déformation",
      "jauge|jauges|rosette|rosettes|extensométrie|jauge de déformation|déformation"],
    // ---- Liaisons et guidages
    ["ajustements", "", "", "Ajustement ISO 286 : écarts, cotes limites, jeu ou serrage",
      "ajustement|ajustements|iso 286|iso 286-1|iso 286-2|tolérance|écart|cote limite|cotes limites|jeu|serrage|alésage|arbre|it|qualité|classe de tolérance|ajustement glissant|ajustement serré|zone de tolérance|h7/g6|h7/p6|h7/r6|h7/s6"],
    ["frettage", "", "", "Frettage : serrage nécessaire, contraintes, température de chauffe",
      "frettage|fretté|frette|emmanchement|ajustement serré|serrage|pression de contact|lamé|température de chauffe|chauffage|dilatation|couple transmissible|ajustement|iso 286"],
    ["paliers", "", "", "Palier lisse : pression, vitesse et produit PV",
      "palier lisse|palier|paliers|coussinet|bague|pression|vitesse|produit pv|pv|frottement|glissement"],
    ["roulements", "rlt", "Durée de vie", "Durée de vie L10 d'un roulement (ISO 281)",
      "roulement|roulements|durée de vie|l10|l10h|iso 281|charge dynamique|charge équivalente|charge radiale|charge axiale|fiabilité|capacité de charge|palier"],
    ["roulements", "rlt_ens", "Ensemble", "Ensemble de roulements : réactions et durée de vie de la liaison",
      "ensemble de roulements|liaison pivot|pivot|montage|deux roulements|réactions|arbre"],
    ["roulements", "rlt_regle", "Règles de montage", "Règles de montage d'un roulement selon la bague tournante ou fixe",
      "règles de montage|montage|bague intérieure|bague extérieure|bague tournante|bague fixe"],
    // ---- Transmission
    ["engrenages", "eng", "Engrènement", "Engrenage droit : module, nombre de dents, entraxe, angle de pression, effort en pied de dent",
      "engrenage|engrenages|engrènement|module|nombre de dents|denture|dent|entraxe|angle de pression|rapport de transmission|rapport de réduction|pignon|roue|diamètre primitif|lewis|pied de dent|effort tangentiel|réducteur"],
    ["engrenages", "trn", "Train d'engrenages", "Train d'engrenages simple : rapports et vitesses",
      "train d'engrenages|train simple|rapport de transmission|rapport|réducteur|vitesse de sortie|vitesse"],
    ["engrenages", "epi", "Épicycloïdal", "Train épicycloïdal : planétaire, satellites, porte-satellites",
      "train épicycloïdal|épicycloïdal|planétaire|satellite|satellites|porte-satellite|couronne|solaire|réducteur"],
    ["freins", "frn", "Frein à disque", "Couple de freinage d'un frein à disque",
      "frein|freins|frein à disque|disque|couple de freinage|plaquette|garniture|friction|adhérence"],
    ["freins", "emb", "Embrayage", "Embrayage : synchronisation, énergie dissipée, couple transmissible",
      "embrayage|synchronisation|friction|énergie dissipée|couple transmissible|disque|glissement"],
    ["moteur", "", "", "Choix d'un moteur : couple thermique, couple de pointe, inertie ramenée",
      "moteur|motoréducteur|couple thermique|couple équivalent|couple de pointe|inertie ramenée|inertie|puissance|vitesse|cycle|réducteur|dimensionnement moteur|servomoteur"],
    // ---- Données et aide
    ["convertisseur", "", "", "Conversion entre unités (longueur, force, pression, couple…)",
      "convertisseur|conversion|convertir|unité|unités|pouce|inch|psi|bar|mpa|pascal|newton|kgf|daN|n·m|kw|cv|cheval|température|fahrenheit"],
    ["base", "mat", "Matériaux", "Base de matériaux : module E, limite élastique Re, Rm, masse volumique",
      "matériau|matériaux|acier|inox|aluminium|fonte|titane|bronze|laiton|s235|s355|316l|module d'young|limite élastique|re|rm|masse volumique|densité|coefficient de dilatation"],
    ["base", "pro", "Profilés", "Profilés normalisés : IPE, HEA, HEB, UPN, et ajouts",
      "profilé|profilés|ipe|hea|heb|hem|upn|ipn|cornière|tube|section normalisée|catalogue de profilés"],
    ["base", "mata", "Matage", "Pressions de matage admissibles selon la liaison",
      "pression de matage|matage|pression admissible|clavette|cannelure|liaison"],
    ["base", "kt", "Abaques Kt", "Concentration de contrainte (Peterson) : Kt d'un arbre épaulé ou d'une plaque percée",
      "kt|concentration de contrainte|peterson|arbre épaulé|épaulement|congé|trou|plaque percée|entaille|abaque|abaques"],
    ["base", "fic", "Mes ajouts", "Matériaux et profilés ajoutés, import et export",
      "mes ajouts|ajout|import|export|matériau utilisateur|fichier"],
    ["references", "", "", "Normes, cours et documents cités par l'application",
      "références|norme|normes|bibliographie|cours|eurocode 3|eurocode|iso 286|iso 898-1|iso 68-1|iso 281|en 1993|université de bordeaux|iut|source|document"],
    ["limites", "", "", "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas",
      "limites|limite|vérifications|vérification|validation|tests|précision|matlab|erreur|hypothèses|domaine de validité"],
  ];

  // Classes de tolérance usuelles (h7, g6, k6…) : générées, pour que « H8 » ou « k6 » mènent aux ajustements.
  const CLASSES = { h: [5, 11], g: [5, 7], f: [6, 8], e: [7, 9], d: [8, 11], js: [5, 8], k: [5, 7], m: [5, 7], n: [5, 7], p: [5, 7], r: [5, 7], s: [5, 7], t: [5, 7], u: [5, 8] };
  const classes = [];
  for (const [lettre, [a, b]] of Object.entries(CLASSES)) for (let g = a; g <= b; g++) classes.push(lettre + g);

  // ---------- comparaison tolérante ----------

  const norme = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/œ/g, "oe").replace(/[^a-z0-9]+/g, " ").trim();

  // Une entrée de recherche : ses mots normalisés, plus le titre de la page et de sa famille.
  const entrees = TABLE.map(([page, calc, etiquette, raison, mots], i) => {
    const p = App.page(page);
    const liste = mots.split("|");
    if (page === "ajustements") liste.push(...classes);
    if (p) { liste.push(p.titre, p.id.replace(/-/g, " ")); const f = App.FAMILLES.find((x) => x.id === p.famille); if (f) liste.push(f.titre); }
    const termes = liste.map(norme).filter(Boolean).map((t) => ({ t, mots: t.split(" "), compact: t.replace(/ /g, "") }));
    return { page, calc, etiquette, raison, termes, ordre: i, titre: p ? p.titre : page };
  }).filter((e) => App.page(e.page));

  // Pages absentes de la table : trouvées par leur titre et leur phrase de présentation.
  for (const p of App.PAGES) {
    if (p.id === "accueil" || entrees.some((e) => e.page === p.id)) continue;
    const termes = [p.titre, p.texte].map(norme).map((t) => ({ t, mots: t.split(" "), compact: t.replace(/ /g, "") }));
    entrees.push({ page: p.id, calc: "", etiquette: "", raison: p.texte, termes, ordre: 1000 + entrees.length, titre: p.titre });
  }

  // Calculs que l'application n'a pas : la recherche le dit (au lieu de ne rien répondre) et propose les pages les plus proches.
  // [mots (séparés par « | »), message, [[page, onglet], …]]
  const ABSENTS = [
    ["ressort|ressorts|raideur de ressort|spire|spires", "Pas de calcul de ressort pour l'instant.", [["hooke", "hoo"], ["poutres", "beam"]]],
    ["soudure|soudures|cordon de soudure|soudage|souder", "Pas de calcul de soudure pour l'instant.", [["poutres", "beam"], ["sollicitations", "cis"]]],
  ].map(([mots, message, proches]) => ({ mots: mots.split("|").map(norme), message, proches }));

  function absent(texte) {
    const q = norme(texte);
    if (q.length < 4) return null;
    return ABSENTS.find((a) => a.mots.some((m) => q === m || q.split(" ").some((j) => j.length >= 4 && (j === m || m.startsWith(j) && j.length >= 5)) || q.includes(m))) || null;
  }

  // Note d'un mot cherché contre un mot connu : 6 identique, 4 début de mot, 3 pluriel (« roulements » → « roulement »), 2 morceau (4 lettres au moins : « ipe » ne doit pas trouver « dissipée »).
  function noteMot(q, m) {
    if (m === q) return 6;
    if (m.startsWith(q)) return 4;
    if (m.length >= 4 && q.startsWith(m) && q.length - m.length <= 2) return 3;
    if (q.length >= 4 && m.includes(q)) return 2;
    return 0;
  }

  function chercher(texte) {
    const q = norme(texte);
    if (!q) return [];
    const jetons = q.split(" ");
    const notes = [];
    for (const e of entrees) {
      let total = 0, ok = true;
      for (const j of jetons) {
        let meilleur = 0;
        for (const t of e.termes) {
          for (const m of t.mots) meilleur = Math.max(meilleur, noteMot(j, m));
          if (j.length >= 4 && t.compact.includes(j)) meilleur = Math.max(meilleur, 2); // « vonmises » trouve « von mises »
        }
        if (!meilleur) { ok = false; break; }
        total += meilleur;
      }
      if (!ok) continue;
      let bonus = 0; // la phrase entière, telle qu'écrite, compte plus que des mots épars
      for (const t of e.termes) bonus = Math.max(bonus, t.t === q ? 8 : t.t.startsWith(q) ? 4 : t.t.includes(q) ? 2 : 0);
      notes.push({ e, note: total + bonus });
    }
    notes.sort((a, b) => b.note - a.note || a.e.ordre - b.e.ordre);
    const vus = new Set();
    const res = [];
    for (const { e } of notes) {
      const cle = e.page + "/" + e.calc;
      if (vus.has(cle)) continue;
      vus.add(cle);
      res.push(e);
      if (res.length === 8) break;
    }
    return res;
  }

  // ---------- interface ----------

  const LIBELLE = "Rechercher un calcul, une grandeur, une norme";
  const LOUPE = '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M13 13l5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  let resultats = [], actif = -1, bouton, panneau, champ, liste, aide, etat, fermerBouton;

  function monter() {
    const barre = App.$("barre");
    if (!barre || App.$("recherche-bouton")) return;
    bouton = el("button", { type: "button", id: "recherche-bouton", class: "recherche-bouton secondaire", "aria-expanded": "false", "aria-controls": "recherche-panneau",
      "aria-label": LIBELLE, "aria-keyshortcuts": "/ Control+K" });
    const icone = el("span", { class: "recherche-icone", "aria-hidden": "true" });
    icone.innerHTML = LOUPE;
    bouton.append(icone, el("span", { class: "recherche-texte", "aria-hidden": "true", texte: "Rechercher" }), el("kbd", { "aria-hidden": "true", texte: "/" }));
    bouton.addEventListener("click", () => (panneau.hidden ? ouvrir() : fermer(true)));

    champ = el("input", { type: "text", id: "recherche-champ", role: "combobox", "aria-expanded": "false", "aria-controls": "recherche-liste", "aria-autocomplete": "list",
      "aria-label": LIBELLE, "aria-describedby": "recherche-aide", placeholder: LIBELLE, autocomplete: "off", autocapitalize: "off", spellcheck: "false", enterkeyhint: "go", maxlength: "80" });
    fermerBouton = el("button", { type: "button", class: "secondaire petit", texte: "Fermer", "aria-label": "Fermer la recherche" });
    fermerBouton.addEventListener("click", () => fermer(true));
    aide = el("p", { id: "recherche-aide", class: "legende recherche-aide" });
    liste = el("ul", { id: "recherche-liste", class: "recherche-liste", role: "listbox", "aria-label": "Résultats de la recherche", hidden: true });
    etat = el("p", { class: "cache", role: "status", "aria-atomic": "true" });
    panneau = el("div", { id: "recherche-panneau", class: "recherche-panneau", role: "search", hidden: true },
      el("div", { class: "recherche-ligne" }, champ, fermerBouton), aide, liste, etat);

    champ.addEventListener("input", majResultats);
    champ.addEventListener("keydown", surChamp);
    liste.addEventListener("mousedown", (e) => e.preventDefault()); // le clic sur un résultat ne retire pas le focus du champ
    liste.addEventListener("click", (e) => { const o = e.target.closest("[role=option]"); if (o) choisir(Number(o.dataset.i)); });
    liste.addEventListener("mousemove", (e) => { const o = e.target.closest("[role=option]"); if (o && Number(o.dataset.i) !== actif) activer(Number(o.dataset.i), false); });
    panneau.addEventListener("focusout", (e) => { if (!e.relatedTarget || !(panneau.contains(e.relatedTarget) || e.relatedTarget === bouton)) fermer(false); });
    document.addEventListener("pointerdown", (e) => { if (!panneau.hidden && !panneau.contains(e.target) && !bouton.contains(e.target)) fermer(false); });
    window.addEventListener("hashchange", () => { if (!panneau.hidden) fermer(false); });
    barre.insertBefore(bouton, App.$("sous"));
    barre.append(panneau);
    document.addEventListener("keydown", raccourcis);
    texteAide();
  }

  // Un seul bouton : « / » (hors champ de saisie) et Ctrl+K (partout) ouvrent la recherche ; Échap la ferme (dans le champ).
  function raccourcis(e) {
    if (e.defaultPrevented || e.isComposing || !bouton) return;
    const c = e.target;
    const enSaisie = c && (c.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(c.tagName) || (c.closest && c.closest("[role=textbox],[role=combobox],[role=searchbox]")));
    const ctrlK = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && String(e.key).toLowerCase() === "k";
    if (ctrlK) { e.preventDefault(); ouvrir(); }
    else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !enSaisie) { e.preventDefault(); ouvrir(); }
  }

  function texteAide(texte) {
    aide.textContent = texte || "Exemples : flèche, H7, von mises, roulement, ISO 286, Eurocode 3. Flèches haut et bas pour choisir, Entrée pour ouvrir, Échap pour fermer.";
  }

  function ouvrir() {
    panneau.hidden = false;
    bouton.setAttribute("aria-expanded", "true");
    champ.focus();
    champ.select();
    majResultats();
  }

  function fermer(rendreFocus) {
    if (panneau.hidden) return;
    panneau.hidden = true;
    bouton.setAttribute("aria-expanded", "false");
    champ.setAttribute("aria-expanded", "false");
    champ.removeAttribute("aria-activedescendant");
    if (rendreFocus) bouton.focus();
  }

  function majResultats() {
    const texte = champ.value;
    resultats = chercher(texte);
    const manque = absent(texte);
    if (manque) { // les pages proches d'abord, puis ce que la table a trouvé d'autre
      const proches = manque.proches.map(([page, calc]) => entrees.find((e) => e.page === page && e.calc === calc)).filter(Boolean);
      resultats = [...proches, ...resultats.filter((e) => !proches.includes(e))].slice(0, 8);
    }
    liste.replaceChildren(...resultats.map((r, i) => el("li", { id: "recherche-opt-" + i, role: "option", "aria-selected": "false", "data-i": String(i), class: "recherche-option" },
      el("span", { class: "r-titre", texte: r.titre + (r.etiquette ? " › " + r.etiquette : "") }),
      el("span", { class: "r-raison", texte: r.raison }))));
    const a = resultats.length > 0;
    liste.hidden = !a;
    champ.setAttribute("aria-expanded", String(a));
    if (manque) aide.textContent = manque.message + (a ? " Pages les plus proches ci-dessous." : "");
    else if (a) texteAide();
    if (a) activer(0, false);
    else champ.removeAttribute("aria-activedescendant");
    if (!norme(texte)) { texteAide(); etat.textContent = ""; }
    else if (manque) etat.textContent = manque.message + (a ? " " + resultats.length + (resultats.length > 1 ? " pages proches." : " page proche.") : "");
    else if (!a) { aide.textContent = "Aucun résultat pour « " + texte.trim() + " ». Essayez un seul mot : flèche, H7, roulement, module, Eurocode 3…"; etat.textContent = "Aucun résultat"; }
    else etat.textContent = resultats.length + (resultats.length > 1 ? " résultats" : " résultat");
  }

  function activer(i, defiler = true) {
    if (!resultats.length) return;
    actif = (i + resultats.length) % resultats.length;
    for (const o of liste.children) o.setAttribute("aria-selected", String(Number(o.dataset.i) === actif));
    champ.setAttribute("aria-activedescendant", "recherche-opt-" + actif);
    if (defiler) liste.children[actif].scrollIntoView({ block: "nearest" });
  }

  function surChamp(e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!resultats.length) return;
      e.preventDefault();
      activer(actif + (e.key === "ArrowDown" ? 1 : -1));
    } else if (e.key === "Enter") {
      if (!resultats.length) return;
      e.preventDefault();
      choisir(actif < 0 ? 0 : actif);
    } else if (e.key === "Escape") {
      e.preventDefault(); // un Échap n'a qu'un seul rôle : le guide et les replis ne le reprennent pas
      fermer(true);
    }
  }

  function choisir(i) {
    const r = resultats[i];
    if (!r) return;
    fermer(false);
    if (r.calc) App.memoire.ecrire("onglet.page." + r.page, r.calc); // ouvre l'onglet du calcul cherché (réglage d'affichage seulement)
    const cible = "#/" + r.page;
    if (location.hash === cible) window.dispatchEvent(new HashChangeEvent("hashchange")); // même page : on la redessine sur le bon onglet
    else location.hash = cible;
    // le routeur place déjà le focus sur le titre quand la page change ; ce contrôle couvre « même page » et les rendus tardifs
    setTimeout(() => {
      const titre = App.$("contenu").querySelector("h1");
      if (titre && document.activeElement !== titre) { if (!titre.hasAttribute("tabindex")) titre.setAttribute("tabindex", "-1"); titre.focus({ preventScroll: true }); }
    }, 80);
  }

  App.recherche = { ouvrir: () => ouvrir(), chercher, monter };
  monter();
})();
