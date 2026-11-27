"use strict";
// Socle du site MecaStruct : démarrage de Pyodide, menu à cinq familles, adresses par page, outils d'affichage.
// Le calcul est le Python de l'application de bureau (application/mecastruct), exécuté dans le navigateur par
// mecastruct.pont ; ici, seulement l'affichage. Chaque genre de page (js/*.js) s'enregistre avec App.genre(nom, rendu).

const App = (() => {
  const $ = (id) => document.getElementById(id);
  const VERSION = "1.7.0";
  const DEPOT = "https://github.com/theo33-oss/MecaStruct";
  let pont = null;
  const genres = {};
  const mesures = {}; // durées du démarrage (ms), lisibles dans la console : App.mesures

  // ---------- pages : une seule liste, qui donne le menu, les adresses et l'accueil ----------
  // genre « machine » : page de calculs (calculs = identifiants du pont) ; « bureau » : pas encore dans le navigateur.
  const FAMILLES = [
    { id: "structures", titre: "Structures", texte: "Une structure chargée : efforts, flèches, stabilité." },
    { id: "sections", titre: "Sections et contraintes", texte: "Une section ou un état de contrainte en un point." },
    { id: "liaisons", titre: "Liaisons et guidages", texte: "Choisir l'ajustement, vérifier le frettage, puis le guidage." },
    { id: "transmission", titre: "Transmission", texte: "La chaîne du moteur au récepteur." },
    { id: "donnees", titre: "Données et aide", texte: "Unités, matériaux, références et limites de l'outil." },
  ];
  const PAGES = [
    { id: "accueil", titre: "Accueil", genre: "accueil" },
    { id: "poutres", titre: "Poutres", famille: "structures", genre: "machine", calculs: ["beam", "ossature"], pont: "structures", texte: "Poutre 2D isostatique ou hyperstatique, ou ossature 3D : réactions, efforts, flèche, contraintes, Eurocode 3 (2D)." },
    { id: "treillis", titre: "Treillis", famille: "structures", genre: "machine", calculs: ["truss"], pont: "structures", texte: "Efforts dans les barres et déplacements des nœuds." },
    { id: "flambage", titre: "Flambage", famille: "structures", genre: "machine", calculs: ["fla"], pont: "structures", texte: "Charge critique d'Euler, courbes de l'Eurocode 3, élancement, conditions aux limites." },
    { id: "sections-page", titre: "Sections", famille: "sections", genre: "machine", calculs: ["sec"], pont: "structures", paquets: ["sympy"], texte: "Aire, centre de gravité, inerties et modules de sections simples, composées ou profilées." },
    { id: "sollicitations", titre: "Sollicitations", famille: "sections", genre: "machine", calculs: ["tra", "cis", "tor", "fle"], pont: "structures", texte: "Traction, cisaillement (clavette, goupille), torsion, flexion." },
    { id: "tenseurs", titre: "Tenseurs et critères", famille: "sections", genre: "machine", calculs: ["ten"], pont: "structures", paquets: ["sympy"], texte: "Contraintes principales, cercle de Mohr, Von Mises et Tresca." },
    { id: "hooke", titre: "Hooke et jauges", famille: "sections", genre: "machine", calculs: ["hoo", "jau"], pont: "structures", texte: "Loi de Hooke généralisée et rosettes de jauges." },
    { id: "ajustements", titre: "Ajustements ISO 286", famille: "liaisons", genre: "machine", calculs: ["aju"], texte: "Écarts, cotes limites, jeu ou serrage d'un ajustement." },
    { id: "frettage", titre: "Frettage", famille: "liaisons", genre: "machine", calculs: ["fre"], texte: "Serrage nécessaire, ajustement normalisé, contraintes, température de chauffe." },
    { id: "paliers", titre: "Paliers lisses", famille: "liaisons", genre: "machine", calculs: ["pal"], texte: "Pression, vitesse et produit PV face aux limites du matériau." },
    { id: "roulements", titre: "Roulements", famille: "liaisons", genre: "machine", calculs: ["rlt", "rlt_ens", "rlt_regle"], texte: "Durée de vie, ensemble de roulements, règles de montage." },
    { id: "engrenages", titre: "Engrenages", famille: "transmission", genre: "machine", calculs: ["eng", "trn", "epi"], texte: "Engrènement, train simple et train épicycloïdal." },
    { id: "freins", titre: "Freins et embrayages", famille: "transmission", genre: "machine", calculs: ["frn", "emb"], texte: "Couple de freinage d'un disque, synchronisation d'un embrayage." },
    { id: "moteur", titre: "Dimensionnement moteur", famille: "transmission", genre: "machine", calculs: ["mot"], texte: "Couple thermique équivalent, couple de pointe, inertie ramenée." },
    { id: "convertisseur", titre: "Convertisseur", famille: "donnees", genre: "convertisseur", texte: "Conversion entre unités de toutes les grandeurs." },
    { id: "base", titre: "Matériaux et profilés", famille: "donnees", genre: "base", texte: "Base de matériaux et de profilés normalisés." },
    { id: "references", titre: "Références", famille: "donnees", genre: "references", texte: "Normes, cours et documents cités par l'application." },
    { id: "glossaire", titre: "Glossaire", famille: "donnees", genre: "glossaire", pont: "structures", texte: "Symboles des formules : nom, unité et pages où ils apparaissent." },
    { id: "limites", titre: "Limites et vérifications", famille: "donnees", genre: "texte", source: "LIMITES.md", pont: "structures", verifications: true, texte: "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas." },
  ];
  const page = (id) => PAGES.find((p) => p.id === id);

  // ---------- nombres et textes ----------

  // « 0,25 » ou « 0.25 » → nombre ; texte vide → "" ; autre texte → NaN.
  function nombre(v) {
    if (typeof v === "number") return v;
    const t = String(v ?? "").trim().replace(/\s/g, "").replace(",", ".").replace("−", "-");
    if (t === "") return "";
    if (!/^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(t)) return NaN;
    const n = Number(t);
    return Number.isFinite(n) ? n : NaN; // « 1e400 » dépasse ce qu'un nombre peut porter : refusé comme un texte
  }
  const fr = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
  // Décimales d'un texte du calcul à la française : « p = 10.1 MPa » → « p = 10,1 MPa ».
  // « 2,487e+07 » → « 2,487·10⁷ » (exposant en chiffres hauts, plus lisible que la notation informatique)
  const HAUT = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "−": "⁻" };
  const exposants = (t) => String(t).replace(/(\d)e([-+−]?)(\d{1,3})(?![\w])/g, (_m, d, signe, exp) =>
    `${d}·10${signe === "+" ? "" : HAUT[signe] || ""}${String(Number(exp)).replace(/\d/g, (x) => HAUT[x])}`);
  const decimalesFr = (t) => exposants(String(t).replace(/(\d)\.(\d)/g, "$1,$2"));
  // Clavier des champs numériques sur téléphone : « decimal » n'a pas de signe moins (iPhone), donc réservé aux champs
  // dont le minimum est connu et positif ou nul ; sinon le champ peut être négatif et reçoit le clavier texte.
  const clavierNombre = (min) => (typeof min === "number" && min >= 0 ? "decimal" : "text");
  const echapper = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function el(balise, attributs = {}, ...enfants) {
    const e = document.createElement(balise);
    for (const [k, v] of Object.entries(attributs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "texte") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "aide") e.dataset.aide = v;
      else e.setAttribute(k, v === true ? "" : v);
    }
    // Aide portée en texte, sans arrêt de tabulation de plus : l'en-tête, le titre de tableau et la valeur clé la déclarent en
    // aria-description (la bulle reste pour le survol) ; la ligne d'un mode de ruine reçoit UN arrêt (son nom) qui porte l'aide
    // de sa jauge et de ses chiffres (voir `bilan` de machine.js).
    if (e.dataset.aide && (balise === "th" || /\b(titre-tableau|metrique|mode-nom)\b/.test(e.className))) {
      e.setAttribute("aria-description", e.dataset.aide);
    }
    e.append(...enfants.flat().filter((x) => x !== null && x !== undefined && x !== false));
    return e;
  }

  // Markdown de LIMITES.md et des démarches : titres, tableaux, listes, gras, liens. Le texte est échappé avant tout.
  function markdown(texte) {
    const enLigne = (t) => echapper(t)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>');
    const lignes = String(texte).split("\n");
    let html = "", i = 0;
    while (i < lignes.length) {
      const l = lignes[i];
      if (/^#{1,3} /.test(l)) {
        const n = l.match(/^#+/)[0].length + 1;
        html += `<h${n}>${enLigne(l.replace(/^#+ /, ""))}</h${n}>`;
        i++;
      } else if (l.startsWith("|")) {
        const bloc = [];
        while (i < lignes.length && lignes[i].startsWith("|")) bloc.push(lignes[i++]);
        const cellules = (x) => x.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const [tete, , ...corps] = bloc;
        html += '<div class="defile"><table><thead><tr>' + cellules(tete).map((c) => `<th>${enLigne(c)}</th>`).join("") + "</tr></thead><tbody>"
          + corps.map((r) => "<tr>" + cellules(r).map((c) => `<td>${enLigne(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>";
      } else if (/^- /.test(l)) {
        html += "<ul>";
        while (i < lignes.length && /^- /.test(lignes[i])) {
          let item = lignes[i++].slice(2);
          while (i < lignes.length && /^ {2}\S/.test(lignes[i])) item += " " + lignes[i++].trim();
          html += `<li>${enLigne(item)}</li>`;
        }
        html += "</ul>";
      } else {
        let para = l;
        i++;
        while (i < lignes.length && lignes[i].trim() && !/^(#|\||- )/.test(lignes[i])) para += " " + lignes[i++];
        if (para.trim()) html += `<p>${enLigne(para)}</p>`;
      }
    }
    return html;
  }

  // ---------- mémoire du navigateur (jamais indispensable : tout marche sans) ----------

  const memoire = {
    // Valeur gardée, ou « defaut » si rien n'est gardé, si le JSON est illisible ou si son type n'est pas celui du défaut
    // (stockage abîmé ou modifié à la main : « null » à la place d'un objet…). Sans défaut précis (undefined, null), pas de contrôle de type.
    lire(cle, defaut) {
      try {
        const v = localStorage.getItem("mecastruct." + cle);
        if (v === null) return defaut;
        const x = JSON.parse(v);
        const genre = (y) => (y === null ? "null" : Array.isArray(y) ? "tableau" : typeof y);
        return defaut !== undefined && defaut !== null && genre(x) !== genre(defaut) ? defaut : x;
      } catch (e) { return defaut; }
    },
    ecrire(cle, valeur) {
      try { localStorage.setItem("mecastruct." + cle, JSON.stringify(valeur)); } catch (e) { /* stockage bloqué : sans mémoire */ }
    },
    oublier(cle) {
      try { localStorage.removeItem("mecastruct." + cle); } catch (e) { /* rien */ }
    },
  };

  // ---------- thème clair / sombre ----------

  const sombre = () => document.documentElement.dataset.theme === "dark";
  function poserTheme(theme) {
    document.documentElement.dataset.theme = theme;
    memoire.ecrire("theme", theme);
    try { localStorage.setItem("mecastruct.theme", theme); } catch (e) { /* rien */ }
    for (const d of document.querySelectorAll(".js-plotly-plot")) if (d._figure) tracer(d, d._figure);
    document.dispatchEvent(new Event("themechange"));
  }

  // Bibliothèques des CDN (Pyodide, Plotly, KaTeX) : balises async dans index.html, donc le menu et l'accueil s'affichent sans
  // les attendre. Promesse qui se résout quand la bibliothèque est là (test()), et échoue si son script n'a pas pu se charger.
  const biblios = new Map();
  function bibliotheque(id, test) {
    if (!biblios.has(id)) {
      biblios.set(id, new Promise((ok, ko) => {
        const s = document.getElementById("script-" + id);
        const echec = () => ko(new Error("chargement de « " + id + " » impossible"));
        if (test()) return ok();
        if (!s || s.dataset.echec) return echec();
        s.addEventListener("load", () => (test() ? ok() : echec()));
        s.addEventListener("error", echec);
      }));
    }
    return biblios.get(id);
  }

  // ---------- éléments d'affichage ----------

  function message(niveau, texte) {
    return el("p", { class: "message " + niveau, role: niveau === "erreur" ? "alert" : "status", texte });
  }

  async function copier(texte) {
    try { await navigator.clipboard.writeText(texte); return true; } catch (e) { /* page non sécurisée : copie de secours */ }
    const z = Object.assign(document.createElement("textarea"), { value: texte });
    document.body.append(z);
    z.select();
    const ok = document.execCommand("copy");
    z.remove();
    return ok;
  }

  // ---------- retour visible des boutons : le bouton change d'aspect un instant, un message flotte en bas d'écran ----------

  // Message flottant (hors de portée du bouton cliqué : il faut le voir même si la page défile).
  let minuterieToast = null;
  function toast(texte, niveau = "succes") {
    // la zone « status » est dans index.html dès le départ (une zone créée avec son texte n'est pas annoncée) ; elle reste dans
    // l'arbre d'accessibilité (opacité 0, pas display:none) et se vide après chaque message pour que le suivant soit une vraie nouveauté
    let t = document.getElementById("toast");
    if (!t) { t = el("div", { id: "toast", class: "toast", role: "status", "aria-live": "polite" }); document.body.append(t); }
    t.className = "toast " + niveau;
    t.textContent = texte;
    void t.offsetWidth; // relance l'animation si un message précède
    t.classList.add("visible");
    clearTimeout(minuterieToast);
    minuterieToast = setTimeout(() => { t.classList.remove("visible"); minuterieToast = setTimeout(() => { t.textContent = ""; t.className = "toast"; }, 300); }, niveau === "erreur" ? 3500 : 2200);
  }
  // Le bouton passe au vert (ou au rouge) avec une coche, un petit rebond, puis reprend son texte.
  function retour(bouton, ok, texteOk, texteKo = "Impossible") {
    if (bouton.dataset.libelle === undefined) { bouton.dataset.libelle = bouton.textContent; bouton.style.minWidth = bouton.offsetWidth + "px"; }
    bouton.textContent = (ok ? "✓ " : "✗ ") + (ok ? texteOk : texteKo);
    bouton.classList.remove("retour-ok", "retour-ko");
    void bouton.offsetWidth;
    bouton.classList.add(ok ? "retour-ok" : "retour-ko");
    clearTimeout(bouton._retour);
    bouton._retour = setTimeout(() => {
      bouton.textContent = bouton.dataset.libelle;
      bouton.classList.remove("retour-ok", "retour-ko");
      delete bouton.dataset.libelle;
      bouton.style.minWidth = "";
    }, 2000);
  }
  // Retour complet d'une action : bouton + message flottant.
  function confirmer(bouton, ok, texteOk, texteKo = "Copie impossible", message = texteOk) {
    if (bouton) retour(bouton, ok, texteOk, texteKo);
    toast(ok ? message : texteKo, ok ? "succes" : "erreur");
  }

  // ---------- copie d'un bloc en image (presse-papiers) ----------

  let chargementImage = null;
  function chargerHtmlToImage() {
    if (window.htmlToImage) return Promise.resolve(window.htmlToImage);
    chargementImage = chargementImage || new Promise((ok, ko) => {
      const s = el("script", { src: "https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js",
        integrity: "sha384-UbfRVKN3/elS1r7JcK2FhmPP+KlJ4CvYwbyYD7tH+uTkbT9bNJr9eJeQ0FoFbAgz", crossorigin: "anonymous" });
      s.onload = () => ok(window.htmlToImage);
      s.onerror = () => { chargementImage = null; ko(new Error("html-to-image")); };
      document.head.append(s);
    });
    return chargementImage;
  }
  // PNG du bloc, dans le thème affiché : figure Plotly retracée à sa taille, autre bloc recopié hors écran dans un cadre
  // à marge égale (sans la marge externe du bloc, qui décalait l'image et rognait son bord droit), dessiné par html-to-image.
  async function imageDuBloc(cible) {
    const racine = getComputedStyle(document.documentElement);
    const encre = racine.getPropertyValue("--encre").trim(), fond = racine.getPropertyValue("--carte").trim() || "#FFFFFF";
    if (cible.classList.contains("js-plotly-plot") && cible._figure) {
      const { data, layout } = miseEnForme(cible._figure, sombre(), encre, racine.getPropertyValue("--figure-fond").trim() || fond, cible._modeLegende);
      const url = await Plotly.toImage({ data, layout: { ...layout, width: cible.clientWidth, height: cible.clientHeight } },
        { format: "png", scale: 2 });
      return (await fetch(url)).blob();
    }
    const h2i = await chargerHtmlToImage();
    const largeur = Math.max(cible.scrollWidth, cible.getBoundingClientRect().width);
    const copie = cible.cloneNode(true);
    copie.querySelectorAll(".barre-image").forEach((b) => b.remove());
    // bloc avec son propre fond (verdict) : image serrée au ras du cadre, coins arrondis transparents ;
    // bloc sans fond (tableau, explications) : petite marge sur le fond de la page, pour que le texte reste lisible
    const fondPropre = !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(getComputedStyle(cible).backgroundColor);
    const marge = fondPropre ? 0 : 8;
    const cadre = el("div", { class: "cadre-image" }, copie);
    cadre.style.padding = marge + "px";
    if (fondPropre) cadre.style.background = "transparent";
    cadre.style.width = Math.ceil(largeur + 2 * marge) + "px";
    const hors = el("div", { class: "capture-hors-ecran", "aria-hidden": "true" }, cadre); // le cadre lui-même reste à sa place
    document.body.append(hors);
    try {
      await document.fonts.ready;
      return await h2i.toBlob(cadre, { pixelRatio: 2, backgroundColor: fondPropre ? undefined : fond, width: cadre.offsetWidth, height: cadre.offsetHeight });
    } finally { hors.remove(); }
  }
  // Rend "copie", "telechargee" ou "echec". L'écriture est lancée dans le clic (promesse du blob) : exigence des navigateurs.
  async function copierImage(cible, nom = "mecastruct.png") {
    const blob = imageDuBloc(cible);
    try {
      if (!window.ClipboardItem || !navigator.clipboard || !navigator.clipboard.write) throw new Error("presse-papiers");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      return "copie";
    } catch (e) { /* copie refusée : l'image est téléchargée à la place */ }
    try {
      const b = await blob;
      if (!b) return "echec";
      telecharger(nom, b, "image/png");
      return "telechargee";
    } catch (e) { return "echec"; }
  }
  // SVG (vectoriel) d'une figure Plotly : version claire (fond blanc, texte noir) quel que soit le thème affiché, à une largeur
  // d'au moins 760 px pour que les textes gardent leur taille de 12 px et plus ; fait par Plotly.toImage, sans autre bibliothèque.
  // Rend le texte SVG, ou null si `cible` n'est pas une figure tracée.
  async function svgDeLaFigure(cible) {
    if (!window.Plotly || !cible || !cible._figure) return null;
    const { data, layout } = miseEnForme(cible._figure, false, "#000000", "#FFFFFF", null);
    const hauteur = cible.dataset.hauteurAuto === "1" ? layout.height || cible._hauteurAuto || HAUTEUR_FIGURE : cible.clientHeight;
    const url = await Plotly.toImage({ data, layout: { ...layout, width: Math.max(cible.clientWidth, 760), height: hauteur } }, { format: "svg" });
    const corps = url.slice(url.indexOf(",") + 1);
    if (/^data:image\/svg\+xml;base64,/.test(url)) return new TextDecoder().decode(Uint8Array.from(atob(corps), (c) => c.charCodeAt(0)));
    return decodeURIComponent(corps);
  }
  // Bouton « Télécharger l'image (SVG) » d'un graphique ; `cible` : élément ou fonction qui le donne.
  function boutonSvg(cible, nom = "graphique.svg") {
    const b = el("button", { type: "button", class: "secondaire petit telecharger-svg", texte: "Télécharger l'image (SVG)",
      aide: "Télécharge ce graphique en image vectorielle (SVG, fond blanc), à insérer dans Word, LibreOffice ou Inkscape sans perte de qualité." });
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        const svg = await svgDeLaFigure(typeof cible === "function" ? cible() : cible);
        if (!svg) return confirmer(b, false, "", "Image impossible", "Image impossible : le graphique n'est pas encore tracé.");
        telecharger(nom, svg, "image/svg+xml");
        retour(b, true, "SVG téléchargé");
      } catch (e) { confirmer(b, false, "", "Image impossible", "Image SVG impossible : " + (e && e.message ? e.message : "erreur du graphique") + "."); }
      finally { b.disabled = false; }
    });
    return b;
  }
  // Petite barre « Copier l'image » à placer juste au-dessus du bloc ; `cible` peut être un élément ou une fonction qui le donne.
  // svg : ajoute « Télécharger l'image (SVG) » (graphiques Plotly seulement).
  function boutonImage(cible, nom = "mecastruct.png", svg = false) {
    const b = el("button", { type: "button", class: "secondaire petit copie-image", texte: "Copier l'image",
      aide: "Met une image de ce bloc dans le presse-papiers : à coller dans Word, un mail, un compte rendu." });
    b.addEventListener("click", async () => {
      b.disabled = true;
      const r = await copierImage(typeof cible === "function" ? cible() : cible, nom);
      b.disabled = false;
      if (r === "copie") confirmer(b, true, "Image copiée", "", "Image copiée dans le presse-papiers : à coller dans Word, un mail…");
      else if (r === "telechargee") confirmer(b, true, "Image téléchargée", "", "Copie refusée par le navigateur : l'image a été téléchargée à la place.");
      else confirmer(b, false, "", "Copie impossible");
    });
    return el("div", { class: "barre-image" }, svg ? boutonSvg(cible, nom.replace(/\.png$/, ".svg")) : null, b);
  }
  // Gros titre de bloc (h2) avec « Copier l'image » sur la même ligne, à droite.
  function titreImage(texte, cible, nom, classe = "", svg = false) {
    return el("h2", { class: ("titre-bloc titre-image " + classe).trim() }, el("span", { texte }), boutonImage(cible, nom, svg));
  }

  // Tableau {entetes, lignes} du pont, avec un bouton qui le copie pour Excel (tabulations).
  function tableau(t, titre, nom) {
    // un nombre resté avec un point (texte du calcul) passe à la virgule ; les références de clause (« 6.3.2 ») ne bougent pas
    t = { ...t, lignes: t.lignes.map((l) => l.map((c) => (/^[−\-+]?\d+\.\d+(e[−\-+]?\d+)?$/.test(String(c).trim()) ? decimalesFr(c) : c))) };
    const tab = el("table", { "aria-label": decimalesFr(titre || nom || t.titre || "Tableau de résultats") },
      el("thead", {}, el("tr", {}, t.entetes.map((e) => el("th", { scope: "col", texte: e })))),
      el("tbody", {}, t.lignes.map((ligne) => el("tr", {}, ligne.map((c, j) => {
        const td = el("td", { texte: typeof c === "string" && /^[−\-+]?\d+(,\d+)?e[−\-+]?\d+$/.test(c.trim()) ? exposants(c) : c });
        if (j > 0 && /^[−\-+]?[\d\s]+(,\d+)?(e[−\-+]?\d+)?$/.test(String(c).trim())) td.className = "num";
        if (/^(OK|oui)$/.test(c)) td.className = "verdict succes";
        if (/^(NON|non)$/.test(c)) td.className = "verdict erreur";
        return td;
      })))));
    const b = el("button", { type: "button", class: "secondaire petit", texte: "Copier le tableau", aide: "Copie le tableau avec des tabulations : à coller directement dans Excel." });
    b.addEventListener("click", async () => {
      // les espaces des milliers sont retirés : collé dans Excel, « 1 000 000 » doit rester un nombre
      const brut = (c) => (/^[−\-+]?\d{1,3}([ \u202f\u00a0]\d{3})+(,\d+)?$/.test(String(c).trim()) ? String(c).replace(/[ \u202f\u00a0]/g, "") : c);
      const ok = await copier([t.entetes, ...t.lignes.map((l) => l.map(brut))].map((l) => l.join("\t")).join("\n"));
      confirmer(b, ok, "Tableau copié", "Copie impossible", "Tableau copié : à coller dans Excel.");
    });
    const fichier = el("button", { type: "button", class: "secondaire petit", texte: "Exporter le tableau (CSV)",
      aide: "Télécharge le même tableau en fichier CSV (séparateur « ; », virgule décimale, UTF-8) : s'ouvre dans Excel et LibreOffice." });
    fichier.addEventListener("click", () => {
      const nomCsv = "MecaStruct_" + (String(titre || nom || t.titre || "tableau").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "") || "tableau") + ".csv";
      telecharger(nomCsv, csv(t.entetes, t.lignes), "text/csv;charset=utf-8");
      retour(fichier, true, "CSV téléchargé");
    });
    return el("div", { class: "tableau" }, titre ? el("h3", { class: "titre-mineur", texte: titre }) : null, boutonImage(tab, "tableau.png"), el("div", { class: "defile" }, tab), b, fichier);
  }

  // CSV d'un tableau : séparateur « ; », guillemets si besoin, retours de ligne CRLF, repère UTF-8 (BOM) pour Excel. Les nombres
  // perdent leurs espaces de milliers et gardent leur virgule (`point` : point décimal) ; le « − » typographique devient « - ».
  // Un texte qui commence par = @ + - (hors nombre) est précédé d'une apostrophe : il ne peut pas devenir une formule.
  function csv(entetes, lignes, point = false) {
    const cellule = (c) => {
      let t = c === null || c === undefined ? "" : String(c);
      if (/^[−\-+]?\d{1,3}([   ]\d{3})+(,\d+)?$/.test(t.trim())) t = t.replace(/[   ]/g, "");
      if (/^[−\-+]?\d+([,.]\d+)?(e[−\-+]?\d+)?$/i.test(t.trim())) {
        t = t.trim().replace(/−/g, "-");
        if (point) t = t.replace(",", ".");
      } else if (/^[=@\t\r]/.test(t) || /^[+\-].+/.test(t)) t = "'" + t;
      return /[";\r\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
    };
    return "﻿" + [entetes, ...lignes].map((l) => l.map(cellule).join(";")).join("\r\n") + "\r\n";
  }

  // Formule LaTeX du calcul dessinée par KaTeX (texte brut si KaTeX n'est pas chargé).
  function formule(tex) {
    const d = el("div", { class: "formule" });
    const t = String(tex).replace(/^\$+|\$+$/g, "").replace(/(\d)\.(\d)/g, "$1{,}$2"); // virgule décimale, sans espace
    if (window.katex) {
      try { katex.render(t, d, { displayMode: true, throwOnError: false, strict: "ignore" }); return d; } catch (e) { /* texte brut */ }
    }
    d.textContent = t;
    return d;
  }

  // Couleurs des figures du calcul (plots/_common.py) → thème sombre.
  const COULEURS_SOMBRES = { "rgba(0,0,0,1)": "#EDE6F7", "black": "#EDE6F7", "#000000": "#EDE6F7", "white": "#1A1626", "#FFFFFF": "#1A1626", "#ffffff": "#1A1626", "rgba(255,255,255,1)": "#1A1626" };
  // espaces tolérés dans rgba( ) : c'est ainsi que Plotly réécrit les couleurs
  const enSombre = (x) => JSON.parse(JSON.stringify(x).replace(/"(rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*1\s*\)|black|white|#000000|#FFFFFF|#ffffff|rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*1\s*\))"/g,
    (m, c) => `"${COULEURS_SOMBRES[c.replace(/\s/g, "")]}"`));

  // Adaptation d'une figure à son conteneur. Légende à droite (marge de 170 px) : sur un écran étroit elle mangeait le tracé, et sur
  // un grand écran elle frôle les repères dessinés dans la marge ; une légende sous le tracé peut toucher le titre de l'axe. Elle
  // passe alors tout en bas de la figure, en une ligne qui se replie. mode : "etroit" (conteneur de moins de 520 px : marges
  // réduites, textes plus petits, repères hors tracé retirés) ou "replie" (légende seule déplacée, repères gardés).
  const LARGEUR_ETROITE = 520;
  function placeLegende(layout, data) { // "droite", "dessous" ou null (pas de légende, ou déjà dans le tracé)
    if (layout.showlegend === false) return null;
    const lg = layout.legend || {};
    const noms = data.filter((d) => d.showlegend !== false && d.name).length;
    if (!(layout.showlegend ? noms >= 1 : noms >= 2)) return null;
    if (lg.orientation === "h") return lg.y !== undefined && lg.y < 0 && lg.yref !== "container" ? "dessous" : null;
    return lg.x !== undefined && lg.x < 1 ? null : "droite";
  }
  function adapterFigure(layout, data, mode) {
    if (!mode) return;
    const place = placeLegende(layout, data);
    const marge = { ...(layout.margin || {}) };
    const droite = place === "droite";
    if (mode === "etroit") {
      // marges par défaut de Plotly (80, 80, 100) : sur 290 px elles ne laissaient que 130 px au tracé ; Plotly agrandit tout seul
      // une marge où il faut des graduations ou un titre d'axe
      marge.l = Math.min(marge.l === undefined ? 80 : marge.l, 24);
      marge.r = Math.min(marge.r === undefined ? 80 : marge.r, 24);
      marge.t = Math.min(marge.t === undefined ? 100 : marge.t, 70);
      // textes du tracé plus petits : sur 290 px de large, ils se recouvraient
      if (layout.annotations) layout.annotations = layout.annotations.map((a) => (a.text && !(a.xref === "paper" && a.x > 1) ? { ...a, font: { ...(a.font || {}), size: Math.min((a.font && a.font.size) || 12, 10) } } : a));
      // titre trop long pour la largeur : coupé avant la parenthèse (« Courbe de flambage (E = 210 GPa… ») et en plus petit
      if (layout.title && typeof layout.title.text === "string") {
        const t = layout.title.text;
        layout.title = { ...layout.title, text: t.replace(/<[^>]*>/g, "").length > 36 && !/<br/i.test(t) ? t.replace(/ \(/, "<br>(") : t, font: { ...(layout.title.font || {}), size: 14 } };
      }
      // repères posés dans la marge de droite (hors du tracé) : sans cette marge, ils sortiraient de la figure
      if (droite && layout.annotations) layout.annotations = layout.annotations.filter((a) => !(a.xref === "paper" && a.x > 1));
    } else if (droite && layout.annotations) { // légende repliée : les repères de la marge s'écartent un peu du tracé (l'étiquette Y_B les frôlait)
      layout.annotations = layout.annotations.map((a) => (a.xref === "paper" && a.x > 1 ? { ...a, xshift: (a.xshift || 0) + 20 } : a));
    }
    if (place) {
      layout.legend = { orientation: "h", yref: "container", y: 0, yanchor: "bottom", xref: "paper", x: 0.5, xanchor: "center" };
      marge.b = Math.max(marge.b || 0, 80) + 40; // la légende occupe le bas de la marge, sous le titre de l'axe
      if (layout.height) layout.height += 40;
    }
    layout.margin = marge;
  }
  // La légende (à droite) recouvre-t-elle un texte du tracé : annotation, titre, graduation ?
  function legendeChevauche(div) {
    const lg = div.querySelector("g.legend");
    if (!lg) return false;
    const L = lg.getBoundingClientRect();
    if (!L.width) return false;
    for (const e of div.querySelectorAll("g.annotation, .gtitle, .xtitle, .xtick text, .ytick text")) {
      if (!e.textContent.trim() && !e.querySelector("path")) continue;
      const b = e.getBoundingClientRect();
      if (b.width && b.height && b.left < L.right && b.right > L.left && b.top < L.bottom && b.bottom > L.top) return true;
    }
    return false;
  }
  // Données et mise en page prêtes à tracer : thème sombre ou clair, virgule décimale.
  // Toujours une copie : Plotly réécrit sur place les objets reçus (« rgba(0,0,0,1) » → « rgba(0, 0, 0, 1) » dans les
  // formes), et la figure d'origine, gardée pour les changements de thème, ne doit pas bouger.
  function miseEnForme(f, foncee, encre, fond, mode) {
    let data = JSON.parse(JSON.stringify(f.data || [])), layout = JSON.parse(JSON.stringify(f.layout || {}));
    if (foncee) {
      data = enSombre(data);
      layout = enSombre(layout);
    }
    layout.paper_bgcolor = fond;
    layout.plot_bgcolor = fond;
    layout.font = { ...(layout.font || {}), color: encre };
    layout.autosize = true;
    layout.separators = ", "; // virgule décimale, espace des milliers, comme le reste du site
    // textes écrits par le calcul (« N1 = 18.75 ») : virgule aussi
    if (layout.annotations) layout.annotations = layout.annotations.map((a) => (typeof a.text === "string" ? { ...a, text: decimalesFr(a.text) } : a));
    if (layout.title && typeof layout.title.text === "string") layout.title = { ...layout.title, text: decimalesFr(layout.title.text) };
    data = data.map((d) => ({ ...d, ...(typeof d.name === "string" ? { name: decimalesFr(d.name) } : {}),
      ...(typeof d.text === "string" ? { text: decimalesFr(d.text) } : Array.isArray(d.text) ? { text: d.text.map((x) => (typeof x === "string" ? decimalesFr(x) : x)) } : {}) }));
    delete layout.width;
    if (layout.title && layout.title.text) layout.title = { ...layout.title, x: 0.01, xanchor: "left" };
    adapterFigure(layout, data, mode);
    return { data, layout };
  }
  // Barre d'outils des graphiques : on garde zoom, déplacement, zoom avant / arrière, réinitialisation et téléchargement.
  const BOUTONS_INUTILES = ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines", "hoverClosestCartesian", "hoverCompareCartesian", "hoverClosest3d", "resetCameraLastSave3d"];
  // Titres français des boutons restants (dictionnaire écrit ici : aucun fichier de langue à charger).
  let langueFaite = false;
  function langueGraphiques() {
    if (langueFaite || !window.Plotly || !Plotly.register) return;
    langueFaite = true;
    Plotly.register({ moduleType: "locale", name: "fr", dictionary: {
      "Zoom": "Zoom (rectangle)", "Pan": "Déplacer", "Zoom in": "Zoom avant", "Zoom out": "Zoom arrière", "Reset axes": "Réinitialiser les axes",
      "Download plot as a png": "Télécharger le graphique (PNG)", "Autoscale": "Échelle automatique", "Reset camera to default": "Vue de départ",
      "Turntable rotation": "Rotation sur plateau", "Orbital rotation": "Rotation libre" } });
  }
  // Texte d'un titre Plotly sans ses balises (<b>, <br>…), pour l'étiquette d'un graphique lu au lecteur d'écran.
  const texteSimple = (t) => String(t || "").replace(/<br\s*\/?>/gi, " ").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
  const HAUTEUR_FIGURE = 420; // hauteur de départ d'une figure dont la mise en page n'en fixe pas
  // Figure Plotly du pont : fond et textes suivent le thème, largeur suit la page.
  function tracer(div, f) {
    div._figure = f;
    if (!window.Plotly) { // plotly.min.js (async) n'est pas encore là : le graphique se trace dès son arrivée
      div.replaceChildren(el("p", { class: "legende", texte: "Graphique en préparation…" }));
      bibliotheque("plotly", () => !!window.Plotly).then(
        () => { if (div._figure === f) { div.replaceChildren(); tracer(div, f); } },
        () => div.replaceChildren(el("p", { class: "legende", texte: "Graphique indisponible : la bibliothèque de tracé n'a pas pu se charger. Vérifiez la connexion Internet, puis rechargez la page." })));
      return;
    }
    const encre = getComputedStyle(document.documentElement).getPropertyValue("--encre").trim();
    const fond = getComputedStyle(document.documentElement).getPropertyValue("--figure-fond").trim();
    const largeur = div.clientWidth || (div.parentElement && div.parentElement.clientWidth) || 0;
    const etroit = largeur > 0 && largeur < LARGEUR_ETROITE;
    div._etroit = etroit;
    div._modeLegende = etroit ? "etroit" : div._modeLegende === "replie" ? "replie" : null;
    const { data, layout } = miseEnForme(f, sombre(), encre, fond, div._modeLegende);
    // Hauteur du cadre : jamais laissée au contenu. Avec « autosize », Plotly mesure son cadre à chaque redimensionnement
    // (fenêtre, dépliage du panneau « Représentation ») : un cadre sans hauteur propre se réduisait alors à son min-height et
    // coupait la figure. Le cadre prend donc la hauteur de la mise en page (420 px sinon), sauf si elle a été choisie à la souris
    // (coin bas droit : la hauteur est alors inscrite dans le style et c'est elle qui compte).
    if (div.style.height && div.dataset.hauteurAuto !== "1") layout.height = div.clientHeight;
    else {
      if (!layout.height) layout.height = HAUTEUR_FIGURE;
      div.style.height = layout.height + "px"; // cadre en « content-box » (style.css) : la hauteur du cadre est celle du tracé
      div.dataset.hauteurAuto = "1";
      div._hauteurAuto = layout.height;
    }
    const tactile = !!window.matchMedia && matchMedia("(pointer: coarse)").matches;
    if (tactile) layout.dragmode = false; // au doigt, le graphique ne capte pas le glissement : la page continue de défiler
    langueGraphiques();
    const fait = Plotly.react(div, data, layout, { responsive: true, displaylogo: false, locale: "fr",
      modeBarButtonsToRemove: tactile ? BOUTONS_INUTILES.concat(["zoom2d", "pan2d"]) : BOUTONS_INUTILES });
    // légende à droite qui touche un texte du tracé ou un repère de la marge : elle passe sous le graphique
    if (!div._modeLegende && fait && fait.then) fait.then(() => {
      if (div._figure !== f || div._modeLegende || !legendeChevauche(div)) return;
      div._modeLegende = "replie";
      tracer(div, f);
    }, () => {});
    if (!div._suivi && window.ResizeObserver) { // la figure suit la hauteur donnée à son cadre
      let vue = div.clientHeight;
      div._suivi = new ResizeObserver(() => {
        const l = div.clientWidth;
        if (l > 0 && div._figure && (l < LARGEUR_ETROITE) !== div._etroit) { div._modeLegende = null; tracer(div, div._figure); return; } // passage de la barre des 520 px
        const h = div.clientHeight;
        if (!div.style.height || Math.abs(h - vue) < 4) return;
        vue = h;
        if (div.dataset.hauteurAuto === "1") { if (Math.abs(h - div._hauteurAuto) < 4) return; delete div.dataset.hauteurAuto; } // hauteur prise à la souris
        Plotly.relayout(div, { height: h });
      });
      div._suivi.observe(div);
    }
  }
  // Remet à la taille de leur cadre les figures affichées d'un bloc (panneau déplié, onglet ouvert) : Plotly refait sa mesure,
  // puis la hauteur propre de la figure est rétablie (une mesure ne doit jamais la réduire au min-height du cadre).
  function redimensionnerFigures(racine = document) {
    if (!window.Plotly) return;
    for (const d of racine.querySelectorAll(".js-plotly-plot")) {
      if (!d.offsetParent || !d._fullLayout) continue;
      try {
        const retablir = () => { if (d.dataset.hauteurAuto === "1" && d._hauteurAuto && d._fullLayout && Math.abs(d._fullLayout.height - d._hauteurAuto) > 1) Plotly.relayout(d, { height: d._hauteurAuto }); };
        const r = Plotly.Plots.resize(d);
        if (r && r.then) r.then(retablir, () => {}); else retablir();
      } catch (e) { /* figure en cours de tracé */ }
    }
  }
  // avecBouton = false : le bouton « Copier l'image » est déjà dans le titre du bloc (schéma).
  // opts : { nom (étiquette lue), decritPar (id d'un texte qui décrit les données) }.
  function figure(f, classe = "figure", avecBouton = true, opts = {}) {
    const titre = texteSimple(f.layout && (typeof f.layout.title === "string" ? f.layout.title : f.layout.title && f.layout.title.text));
    const d = el("div", { class: classe, role: "img", "aria-label": decimalesFr(opts.nom || titre || "Graphique du calcul") + " : graphique interactif, survolez pour les valeurs" });
    // hauteur donnée tout de suite : la page ne bouge plus quand Plotly finit de tracer (pas de saut de défilement ensuite)
    const hauteur = Number(f.layout && f.layout.height) || HAUTEUR_FIGURE;
    d.style.height = hauteur + "px"; d.dataset.hauteurAuto = "1"; d._hauteurAuto = hauteur;
    if (opts.decritPar) d.setAttribute("aria-describedby", opts.decritPar);
    requestAnimationFrame(() => tracer(d, f));
    return avecBouton ? el("div", { class: "figure-bloc" }, boutonImage(d, "graphique.png", true), d) : d;
  }

  // Onglets : liste = [{ id, titre, rendu(panneau) }] ; rendu à l'ouverture (Plotly a besoin d'un panneau visible).
  // Onglets de PAGE (clé « page.… » : Poutre 2D / Ossature 3D…) et onglets de RÉSULTAT (Graphique, Synthèse…) : même clavier,
  // mais le bandeau des onglets de page est plus marqué (classe niveau-page).
  let compteurOnglets = 0;
  function onglets(liste, cle, nom) {
    const base = "onglets-" + (++compteurOnglets);
    const niveauPage = !!cle && cle.startsWith("page.");
    const barre = el("div", { class: "onglets", role: "tablist", "aria-label": nom || (niveauPage ? "Calculs de la page" : "Résultats") });
    const panneau = el("div", { class: "panneau", role: "tabpanel", id: base + "-p", tabindex: "0" });
    const ouvrir = (id) => {
      for (const b of barre.children) {
        const choisi = b.dataset.id === id;
        b.setAttribute("aria-selected", String(choisi));
        b.tabIndex = choisi ? 0 : -1; // un seul onglet dans l'ordre de tabulation, les flèches font le tour
        if (choisi) panneau.setAttribute("aria-labelledby", b.id);
      }
      panneau.replaceChildren();
      liste.find((o) => o.id === id).rendu(panneau);
      requestAnimationFrame(() => setTimeout(() => redimensionnerFigures(panneau), 150)); // figure tracée dans un panneau tout juste affiché
      if (cle) memoire.ecrire("onglet." + cle, id);
    };
    barre.append(...liste.map((o, i) => {
      const b = el("button", { type: "button", role: "tab", id: `${base}-t${i}`, "aria-controls": base + "-p", texte: o.titre, onclick: () => ouvrir(o.id) });
      b.dataset.id = o.id;
      return b;
    }));
    // clavier des onglets : flèches gauche et droite, début et fin (modèle ARIA des onglets)
    barre.addEventListener("keydown", (e) => {
      const tous = [...barre.children];
      const i = tous.indexOf(document.activeElement);
      const vers = { ArrowRight: (i + 1) % tous.length, ArrowLeft: (i - 1 + tous.length) % tous.length, Home: 0, End: tous.length - 1 }[e.key];
      if (i < 0 || vers === undefined) return;
      e.preventDefault();
      ouvrir(tous[vers].dataset.id);
      tous[vers].focus();
    });
    const garde = cle ? memoire.lire("onglet." + cle) : null;
    ouvrir(liste.some((o) => o.id === garde) ? garde : liste[0].id);
    return el("div", { class: "bloc-onglets" + (niveauPage ? " niveau-page" : "") }, barre, panneau);
  }

  // ---------- bulles d'aide au survol ou au clavier ----------

  function bulles() {
    const b = el("div", { id: "bulle", role: "tooltip", hidden: true });
    document.body.append(b);
    // WCAG 1.4.13 : la bulle reste tant que le pointeur est sur l'élément ou sur la bulle (délai de 250 ms pour franchir l'écart),
    // se ferme avec Échap, et un élément qui a le focus au clavier la garde. Elle décrit l'élément (aria-describedby).
    let courante = null, minuterie = null;
    // « bulle » s'ajoute à la liste aria-describedby de l'élément (un champ en erreur y garde son message) et s'en retire
    const jetons = (x) => (x.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    const decrire = (x, oui) => {
      const l = jetons(x).filter((j) => j !== "bulle");
      if (oui) l.push("bulle");
      if (l.length) x.setAttribute("aria-describedby", l.join(" ")); else x.removeAttribute("aria-describedby");
    };
    const cacher = () => {
      clearTimeout(minuterie);
      b.hidden = true;
      if (courante) { decrire(courante, false); courante = null; }
    };
    const planifier = () => { clearTimeout(minuterie); minuterie = setTimeout(() => { if (!(courante && courante.matches(":focus-visible"))) cacher(); }, 250); };
    const montrer = (e) => {
      const dansBulle = e.target.closest && e.target.closest("#bulle");
      if (dansBulle) return clearTimeout(minuterie); // le pointeur est passé sur la bulle : elle reste
      const cible = e.target.closest ? e.target.closest("[data-aide]") : null;
      if (!cible) return courante ? planifier() : undefined;
      clearTimeout(minuterie);
      if (cible === courante && !b.hidden) return;
      if (courante) decrire(courante, false);
      courante = cible;
      if (!cible.hasAttribute("aria-description")) decrire(cible, true); // sinon la description est déjà portée par l'élément
      b.textContent = cible.dataset.aide;
      b.hidden = false;
      const r = cible.getBoundingClientRect();
      b.style.left = Math.max(8, Math.min(r.left, innerWidth - b.offsetWidth - 8)) + "px";
      b.style.top = (r.bottom + 6 + b.offsetHeight > innerHeight ? Math.max(8, r.top - b.offsetHeight - 6) : r.bottom + 6) + "px";
    };
    document.addEventListener("mouseover", montrer);
    document.addEventListener("focusin", montrer);
    for (const ev of ["focusout", "scroll"]) document.addEventListener(ev, (e) => { if (!e.target || !e.target.closest || !e.target.closest("#bulle")) cacher(); }, true);
    document.addEventListener("keydown", (e) => {
      if (b.hidden) return;
      if (e.key === "Escape") { e.preventDefault(); cacher(); } // la bulle se ferme seule : le guide ou le panneau ouvert ne reçoivent pas ce Échap
      else if (e.key === "Tab") cacher();
    }, true); // pas à chaque frappe : on tape dans un champ qui porte une bulle
  }

  // ---------- appel du calcul ----------

  // Appelle un calcul du pont : rend {ok, sortie} ou {ok: false, erreur}.
  function calculer(ident, saisie = {}) {
    if (!pont) return { ok: false, erreur: "Le calcul n'est pas encore chargé." };
    try {
      return JSON.parse(pont.appeler(ident, JSON.stringify(saisie)));
    } catch (e) {
      return { ok: false, erreur: "Erreur inattendue du calcul : " + e.message };
    }
  }

  // ---------- saisies des pages, partagées pour les échanges entre pages (section → Poutres…) ----------

  // Saisie courante d'un calcul : celle gardée dans le navigateur, sinon les valeurs de l'exemple.
  function lireSaisie(ident) {
    const r = calculer("formulaires");
    const defaut = r.ok && r.sortie[ident] ? r.sortie[ident].defaut : {};
    const lue = memoire.lire("saisie." + ident, {});
    const gardee = lue && typeof lue === "object" && !Array.isArray(lue) ? lue : {}; // jamais « null » ni un tableau
    const s = JSON.parse(JSON.stringify(defaut));
    for (const k of Object.keys(s)) if (k in gardee) s[k] = gardee[k];
    return s;
  }
  function ecrireSaisie(ident, saisie) {
    memoire.ecrire("saisie." + ident, saisie);
  }

  // ---------- bibliothèques chargées à la demande ----------

  const PAQUETS_PONT = { structures: ["scipy", "shapely", "jinja2"] }; // famille du pont → bibliothèques Pyodide
  const charges = new Set();

  // Charge des paquets Pyodide (une fois) ; vrai si c'est fait.
  async function paquets(noms) {
    const manquants = noms.filter((n) => !charges.has(n));
    if (!manquants.length) return true;
    for (const nom of manquants) {
      try {
        await App.pyodide.loadPackage([nom]);
        if (nom === "openpyxl") App.pyodide.pyimport("openpyxl"); // absent de la distribution : erreur ici
      } catch (e) {
        try { // paquet en pur Python absent de Pyodide : pris sur PyPI
          await App.pyodide.pyimport("micropip").install(nom);
        } catch (e2) {
          console.error(e2);
          return false;
        }
      }
      charges.add(nom);
    }
    return true;
  }

  // Avant une page lourde : ses bibliothèques, puis sa famille du pont.
  // Les appels simultanés (page ouverte pendant le préchargement) attendent le même chargement au lieu de le refaire.
  const enCours = new Map();
  function preparer(p) {
    const cle = (p.pont || "") + "|" + (p.paquets || []).join(",");
    if (!enCours.has(cle)) enCours.set(cle, preparerPage(p).then((ok) => { if (!ok) enCours.delete(cle); return ok; }));
    return enCours.get(cle);
  }

  // Dès que le calcul est prêt, charge en arrière-plan les bibliothèques des autres pages (scipy, shapely, jinja2, sympy) :
  // l'accueil se lit pendant ce temps et les pages lourdes s'ouvrent ensuite sans attente. Évité en mode économie de données.
  async function prechargerPages() {
    if (navigator.connection && navigator.connection.saveData) return;
    const vues = new Set();
    for (const p of PAGES) {
      if (!p.pont) continue;
      const cle = p.pont + "|" + (p.paquets || []).join(",");
      if (vues.has(cle)) continue;
      vues.add(cle);
      await new Promise((r) => (window.requestIdleCallback ? requestIdleCallback(r, { timeout: 3000 }) : setTimeout(r, 300)));
      try { await preparer(p); } catch (e) { console.warn("Préchargement impossible :", p.id, e); }
    }
  }

  async function preparerPage(p) {
    if (!p.pont) return true;
    if (charges.has("pont:" + p.pont)) return paquets(p.paquets || []);
    const t = performance.now();
    if (!await paquets([...(PAQUETS_PONT[p.pont] || []), ...(p.paquets || [])])) return false;
    try {
      pont.charger(p.pont);
    } catch (e) {
      console.error(e);
      return false;
    }
    charges.add("pont:" + p.pont);
    mesures["pont_" + p.pont] = Math.round(performance.now() - t);
    return true;
  }

  // ---------- lien de partage : l'étude compressée dans l'adresse, rien ne passe par un serveur ----------

  const base64url = (octets) => btoa(String.fromCharCode(...octets)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  async function compresser(texte) {
    const flux = new Blob([texte]).stream().pipeThrough(new CompressionStream("deflate-raw"));
    return base64url(new Uint8Array(await new Response(flux).arrayBuffer()));
  }
  async function decompresser(code) {
    if (code.length > 10000) throw new Error("lien trop long");
    const binaire = atob(code.replace(/-/g, "+").replace(/_/g, "/"));
    const octets = Uint8Array.from(binaire, (c) => c.charCodeAt(0));
    const flux = new Blob([octets]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    const texte = await new Response(flux).text();
    if (texte.length > 200000) throw new Error("étude trop grande");
    return texte;
  }
  // Lu dans l'adresse à chaque appel : un lien collé dans la même fenêtre (hashchange) est pris en compte ; il disparaît
  // de l'adresse dès que l'étude est chargée (oublierLien).
  function lienEtude() {
    const m = location.hash.match(/\?(.*)$/);
    const p = new URLSearchParams(m ? m[1] : "");
    return p.get("calcul") && p.get("etude") ? { calcul: p.get("calcul"), etude: p.get("etude") } : null;
  }
  function oublierLien() { // l'étude est chargée : l'adresse redevient celle de la page (pas de rechargement en boucle)
    history.replaceState(null, "", location.pathname + location.hash.replace(/\?.*$/, ""));
  }

  function telecharger(nomFichier, contenu, type = "application/json") {
    const url = URL.createObjectURL(new Blob([contenu], { type }));
    const a = el("a", { href: url, download: nomFichier });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast("Fichier téléchargé : " + nomFichier + " (dossier Téléchargements)");
  }

  // ---------- menu, adresses ----------

  let courante = null;
  let numeroRendu = 0; // change à chaque affichage de page : un rendu lent (await) vérifie qu'il est toujours le dernier
  let echec = null; // texte de l'erreur si le calcul n'a pas pu se charger

  // Message de chargement du calcul dans une page ; si le chargement a déjà échoué, le message d'erreur à la place.
  function messageEchec(texte) {
    const m = message("erreur", (texte || "Le calcul n'a pas pu se charger. Vérifiez la connexion Internet, puis réessayez.") + " ");
    m.append(el("button", { type: "button", class: "secondaire petit", texte: "Réessayer", onclick: () => location.reload() }));
    return m;
  }
  // Exemples déjà calculés (images de l'application de bureau, dossier captures/) : rien n'est calculé ici, ce sont des images.
  const EXEMPLES = {
    poutres: ["poutres", "Exemple : poutre isostatique de 6 m en IPE 300 (acier S235), verdict « Vérifié », flèche maximale 14 mm, Kt·σ max 120,7 MPa (image de l'application de bureau, non interactive).", "Page Poutres : formulaire et résultat d'une poutre de 6 m en IPE 300 déjà calculée, verdict « Vérifié »."],
    treillis: ["treillis", "Exemple : page Treillis avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Treillis avec un calcul déjà fait."],
    flambage: ["flambage", "Exemple : page Flambage avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Flambage avec un calcul déjà fait."],
    "sections-page": ["sections", "Exemple : page Sections avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Sections avec un calcul déjà fait."],
    sollicitations: ["sollicitations_0", "Exemple : page Sollicitations avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Sollicitations avec un calcul déjà fait."],
    tenseurs: ["tenseurs", "Exemple : page Tenseurs et critères avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Tenseurs et critères avec un calcul déjà fait."],
    hooke: ["hooke_jauges_0", "Exemple : page Hooke et jauges avec un calcul déjà fait (image de l'application de bureau, non interactive).", "Page Hooke et jauges avec un calcul déjà fait."],
    base: ["base_de_donnees", "Exemple : page Matériaux et profilés (image de l'application de bureau, non interactive).", "Page Matériaux et profilés."],
    references: ["references", "Exemple : page Références (image de l'application de bureau, non interactive).", "Page Références."],
  };
  let numeroExemple = 0;
  // Bouton « Voir un exemple sans attendre » : montre une image déjà calculée pendant le chargement de Pyodide. Pour l'accueil,
  // l'exemple est celui des poutres. Rend null s'il n'y a rien à montrer (calcul prêt, échec, page sans capture).
  // opts.lien = false : pas de lien « Ouvrir la vraie page » (page de calcul déjà ouverte : elle remplace l'exemple à la fin).
  function exemple(p, opts = {}) {
    if (pont || echec !== null) return null;
    const cible = p.id === "accueil" ? page("poutres") : p;
    const ex = EXEMPLES[cible.id];
    if (!ex) return null;
    const id = "exemple-" + ++numeroExemple;
    const bouton = el("button", { type: "button", class: "secondaire", "aria-expanded": "false", "aria-controls": id, texte: "Voir un exemple sans attendre" });
    const img = el("img", { src: "captures/" + ex[0] + ".jpg", alt: ex[2], width: "1400", height: "854", loading: "lazy" });
    const bas = el("span", { class: "legende" });
    const zone = el("figure", { id, class: "capture", hidden: true }, img, el("figcaption", { class: "legende", texte: ex[1] }));
    let lien = null;
    if (opts.lien !== false) {
      lien = el("a", { class: "bouton primaire", href: "#/" + cible.id, "aria-disabled": "true", texte: "Ouvrir la vraie page" });
      lien.addEventListener("click", (e) => { if (lien.getAttribute("aria-disabled") === "true") e.preventDefault(); });
      zone.append(el("p", { class: "ligne" }, lien, bas));
    } else zone.append(el("p", {}, bas));
    const dire = (pret) => {
      if (lien) lien.setAttribute("aria-disabled", pret ? "false" : "true");
      bas.textContent = pret ? "Le calcul est prêt : vous pouvez ouvrir la vraie page." : opts.lien === false ? "La vraie page remplacera cet exemple dès que le calcul est prêt." : "Le lien s'active dès que le calcul est prêt.";
    };
    dire(false);
    document.addEventListener("mecastruct:pret", () => dire(true), { once: true });
    bouton.addEventListener("click", () => {
      zone.hidden = !zone.hidden;
      bouton.setAttribute("aria-expanded", String(!zone.hidden));
      bouton.textContent = zone.hidden ? "Voir un exemple sans attendre" : "Masquer l'exemple";
    });
    return el("div", { class: "exemple" }, bouton, zone);
  }

  // Message de chargement ; avec une page (p), il est suivi de son exemple déjà calculé s'il y en a un.
  function attente(texte, p) {
    if (echec !== null) return messageEchec();
    const m = message("info", texte);
    const ex = p ? exemple(p, { lien: false }) : null;
    if (!ex) {
      m.dataset.attenteCalcul = "";
      return m;
    }
    const boite = el("div", {}, m, ex);
    boite.dataset.attenteCalcul = "";
    return boite;
  }

  // Page ouverte par un clic sur une famille du menu : la dernière visitée dans cette famille (« derniere.<famille> »), sinon la première.
  function pageDeFamille(famille) {
    const id = memoire.lire("derniere." + famille, "");
    return PAGES.find((p) => p.id === id && p.famille === famille && p.genre !== "bureau") || PAGES.find((p) => p.famille === famille);
  }

  function menu() {
    const nav = $("menu");
    const boutons = [el("a", { href: "#/accueil", class: "famille", "data-famille": "accueil", texte: "Accueil" })];
    for (const f of FAMILLES) {
      boutons.push(el("a", { href: "#/" + pageDeFamille(f.id).id, class: "famille", "data-famille": f.id, texte: f.titre, aide: f.texte }));
    }
    const theme = el("button", { type: "button", class: "theme secondaire" });
    const majTheme = () => {
      theme.textContent = sombre() ? "Thème clair" : "Thème sombre";
      theme.setAttribute("aria-label", sombre() ? "Passer au thème clair" : "Passer au thème sombre");
    };
    theme.addEventListener("click", () => poserTheme(sombre() ? "light" : "dark"));
    document.addEventListener("themechange", majTheme);
    majTheme();
    nav.replaceChildren(...boutons);
    document.querySelector(".entete").append(theme);
  }

  // Hauteur du menu collant, en variable CSS --barre (décalages de défilement, colonnes collantes) : suit le menu quand il
  // passe sur une ou deux lignes ; 0 quand il n'est plus collant (paysage bas).
  let hauteurBarre = 0;
  let majBarre = () => {};
  function mesurerBarre() {
    const barre = $("barre");
    if (!barre) return;
    const maj = () => {
      // marge basse négative : menu repliable ouvert par-dessus la page (js/bandeau.js), seule la ligne repliée compte
      const style = getComputedStyle(barre);
      hauteurBarre = style.position === "sticky" ? Math.ceil(barre.getBoundingClientRect().height + parseFloat(style.marginBottom)) : 0;
      document.documentElement.style.setProperty("--barre", hauteurBarre + "px");
    };
    majBarre = maj;
    maj();
    if (window.ResizeObserver) new ResizeObserver(maj).observe(barre);
    window.addEventListener("resize", maj);
    if (window.matchMedia) matchMedia("(max-height: 520px)").addEventListener("change", maj);
  }

  function majMenu(p) {
    const famille = p.famille || "accueil";
    for (const a of document.querySelectorAll("#menu .famille")) {
      if (a.dataset.famille === famille) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
      if (a.dataset.famille !== "accueil") a.setAttribute("href", "#/" + pageDeFamille(a.dataset.famille).id);
    }
    const sous = $("sous");
    const soeurs = PAGES.filter((x) => x.famille && x.famille === p.famille);
    sous.hidden = soeurs.length === 0;
    if (sous.dataset.famille === (p.famille || "")) { // même famille : seul le lien courant change, le lien focalisé reste en place
      for (const a of sous.querySelectorAll("a")) {
        if (a.getAttribute("href") === "#/" + p.id) a.setAttribute("aria-current", "page");
        else a.removeAttribute("aria-current");
      }
      return;
    }
    sous.dataset.famille = p.famille || "";
    sous.replaceChildren(...soeurs.map((x) => {
      const a = el("a", { href: "#/" + x.id, texte: x.titre });
      if (x.genre === "bureau") a.append(el("span", { class: "pastille", texte: "bureau", aide: "Disponible dans l'application de bureau ; arrive bientôt dans le navigateur." }));
      if (x.id === p.id) a.setAttribute("aria-current", "page");
      return a;
    }));
  }

  // Menu qui défile (téléphone) : un fondu sur le bord signale ce qui dépasse, et l'entrée courante se centre.
  function indiceDefilement(barre) {
    const maj = () => {
      barre.classList.toggle("fondu-gauche", barre.scrollLeft > 4);
      barre.classList.toggle("fondu-droite", barre.scrollLeft + barre.clientWidth < barre.scrollWidth - 4);
    };
    if (!barre._indice) { barre._indice = true; barre.addEventListener("scroll", maj, { passive: true }); window.addEventListener("resize", maj); }
    const a = barre.querySelector('[aria-current]');
    if (a && barre.scrollWidth > barre.clientWidth) barre.scrollLeft = Math.max(0, a.offsetLeft - (barre.clientWidth - a.offsetWidth) / 2);
    maj();
  }

  function afficher() {
    // une ancre qui n'est pas une adresse de page (« #page ») ne change pas de page : on ne retombe pas sur l'accueil
    if (courante && location.hash && !location.hash.startsWith("#/")) return;
    const id = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || "accueil";
    const p = page(id) || page("accueil");
    const changement = !!courante && courante.id !== p.id; // vrai changement de page (pas le premier affichage, ni le rappel de fin de chargement)
    courante = p;
    const numero = ++numeroRendu;
    if (p.famille && p.genre !== "bureau") memoire.ecrire("derniere." + p.famille, p.id); // le menu rouvre la dernière page de la famille
    majMenu(p);
    indiceDefilement($("menu"));
    indiceDefilement($("sous"));
    document.title = (p.id === "accueil" ? "" : p.titre + " · ") + "MecaStruct RdM";
    const contenu = $("contenu");
    contenu.replaceChildren();
    const rendu = genres[p.genre];
    if (rendu) rendu(contenu, p, { pret: !!pont, perime: () => numero !== numeroRendu });
    // page posée (le titre est là, même pour un rendu qui attend le calcul) : pages récentes, favori, section « Mes études » (js/etudes.js)
    document.dispatchEvent(new CustomEvent("mecastruct:page", { detail: { page: p, contenu, changement } }));
    window.scrollTo(0, 0);
    if (changement) { // le focus suit la page (lecteur d'écran, clavier) : il va sur son titre
      const titre = contenu.querySelector("h1") || $("page");
      if (!titre.hasAttribute("tabindex")) titre.setAttribute("tabindex", "-1");
      titre.focus({ preventScroll: true });
    }
  }

  // ---------- démarrage ----------

  // Barre de chargement : étape en cours, secondes écoulées (hors lecteur d'écran : il annoncerait chaque seconde) et ce qui se lit déjà.
  let minuteur = 0;
  function majDuree(debut) {
    $("etat-duree").textContent = " · " + Math.round((performance.now() - debut) / 1000) + " s écoulées";
  }
  function arreterMinuteur() {
    clearInterval(minuteur);
    minuteur = 0;
  }
  function detailChargement() {
    const lisibles = PAGES.filter((p) => ["accueil", "texte", "bureau"].includes(p.genre)).map((p) => p.titre);
    const nbCalcul = PAGES.filter((p) => p.genre === "machine").length;
    return "Déjà lisibles : " + lisibles.join(", ") + ". En préparation : les " + nbCalcul + " pages de calcul, le convertisseur, les matériaux et les références : elles s'activent toutes à la fin de l'étape 4/4.";
  }
  function etat(texte, pas) {
    $("etat").className = "message info";
    $("etat-texte").textContent = texte;
    $("etat").hidden = !texte;
    $("avance").hidden = !pas;
    if (pas) $("avance").value = pas;
    if (!texte) arreterMinuteur();
  }

  async function chronometre(nom, travail) {
    const t = performance.now();
    const r = await travail();
    mesures[nom] = Math.round(performance.now() - t);
    return r;
  }

  // Actualisation complète : efface le service worker et les copies du site, puis recharge la page.
  // Partager le site et le projet : feuille de partage du téléphone (Messages, WhatsApp, Mail, AirDrop…) ; sur ordinateur les liens sont copiés.
  async function partagerSite() {
    const texte = "MecaStruct RdM : calculs de résistance des matériaux et d'éléments de machines, dans le navigateur.\nSite : https://theo33-oss.github.io/MecaStruct/\nProjet : " + DEPOT;
    if (navigator.share) {
      try { await navigator.share({ title: "MecaStruct RdM", text: texte }); } catch (e) { if (e && e.name !== "AbortError") toast("Partage impossible : " + e.message); }
      return;
    }
    const ok = await copier(texte);
    toast(ok ? "Liens du site et du projet copiés : collez-les dans votre message." : "Copie impossible : le navigateur refuse l'accès au presse-papiers.");
  }

  async function actualiserSite() {
    try { for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister(); } catch (e) { /* pas de service worker */ }
    try { for (const n of await caches.keys()) if (n.startsWith("mecastruct-") && n !== "mecastruct-cdn") await caches.delete(n); } catch (e) { /* pas de cache */ }
    location.replace(location.pathname + "?maj=" + Date.now() + location.hash);
  }

  // Compare le build de cette page à celui du site en ligne : une page ancienne le dit et propose de se mettre à jour.
  async function verifierMiseAJour(build) {
    if (!build || location.protocol !== "https:") return;
    try {
      const t = await (await fetch(location.pathname + "?verif=" + Date.now(), { cache: "no-store" })).text();
      const m = t.match(/name="build" content="([0-9a-f]+)"/);
      if (!m || m[1] === build) return;
      const bouton = el("button", { type: "button", class: "primaire", texte: "Actualiser le site", onclick: actualiserSite });
      const bandeau = message("avertissement", "Une version plus récente du site est disponible (cette page : " + build + ", en ligne : " + m[1] + "). ");
      bandeau.append(bouton);
      $("contenu").before(bandeau);
    } catch (e) { /* hors ligne : rien à comparer */ }
  }

  // Télécharge d'avance, en parallèle de Pyodide, la roue de plotly (9,7 Mo, l'étape la plus longue à froid) : micropip la
  // retrouve ensuite dans le cache du navigateur. Sans effet (et sans erreur) si le réseau refuse.
  async function prechargerPlotly() {
    try {
      const d = await (await fetch("https://pypi.org/pypi/plotly/7.1.0/json")).json();
      const roue = d.urls.find((u) => u.packagetype === "bdist_wheel");
      if (roue) await (await fetch(roue.url)).arrayBuffer();
    } catch (e) { /* micropip la téléchargera lui-même */ }
  }

  async function demarrer() {
    const build = document.querySelector('meta[name="build"]')?.content || "";
    $("version").textContent = "version " + VERSION + (build ? " · build " + build : "");
    $("actualiser").addEventListener("click", actualiserSite);
    $("partager").addEventListener("click", partagerSite);
    verifierMiseAJour(build);
    // « Actualiser le site » recharge avec ?maj=… (contourne le cache) : une fois chargée, l'adresse redevient propre
    // (sinon elle se retrouve dans les liens copiés)
    if (/[?&]maj=/.test(location.search)) history.replaceState(null, "", location.pathname + location.hash);
    // lien « Aller au contenu » : le focus va au contenu sans changer l'adresse (le routeur lit le hash)
    document.querySelector(".evitement")?.addEventListener("click", (e) => { e.preventDefault(); $("page").focus(); });
    menu();
    bulles();
    window.addEventListener("hashchange", afficher);
    mesurerBarre();
    afficher(); // la page se lit pendant le chargement ; les calculs s'activent à la fin
    mesures.menu = Math.round(performance.now()); // depuis l'ouverture de la page : menu et accueil visibles
    const debut = performance.now();
    $("etat-detail").textContent = detailChargement();
    $("etat-duree").hidden = false;
    majDuree(debut);
    minuteur = setInterval(() => majDuree(debut), 1000);
    prechargerPlotly();
    const empreinteZip = document.querySelector('meta[name="zip"]')?.content || Date.now();
    const archiveZip = fetch("mecastruct.zip?v=" + empreinteZip).then((r) => r.arrayBuffer()); // lue plus tard : déjà là
    archiveZip.catch(() => {}); // l'erreur est traitée à l'attente, plus bas
    try {
      const pyodide = await chronometre("python", async () => { await bibliotheque("pyodide", () => typeof window.loadPyodide === "function"); return window.loadPyodide(); });
      etat("Préparation 2/4 : bibliothèques de calcul (numpy, pandas)…", 2);
      await chronometre("numpy_pandas", () => pyodide.loadPackage(["numpy", "pandas", "micropip"]));
      etat("Préparation 3/4 : graphiques (plotly)…", 3);
      await chronometre("plotly", () => pyodide.pyimport("micropip").install("plotly==7.1.0")); // même version que l'application de bureau (requirements.lock)
      etat("Préparation 4/4 : calculs MecaStruct, tables ISO 286, matériaux…", 4);
      await chronometre("mecastruct", async () => {
        const archive = await archiveZip;
        pyodide.unpackArchive(archive, "zip", { extractDir: "/app" });
        pyodide.runPython("import sys; sys.path.insert(0, '/app')");
        pont = pyodide.pyimport("mecastruct.pont");
        // ajouts de l'utilisateur (matériaux, profilés) gardés dans ce navigateur : rejoués avant tout calcul
        const u = memoire.lire("utilisateur", null);
        if (u && typeof u === "object" && !Array.isArray(u)) pont.appeler("base.restaurer", JSON.stringify({ utilisateur: u }));
        pont.appeler("formulaires"); // premier appel : charge les modules de calcul
      });
      App.pyodide = pyodide;
    } catch (e) {
      pont = null;
      echec = String(e);
      console.error(e);
      arreterMinuteur();
      $("etat-duree").hidden = true;
      $("etat-detail").hidden = true;
      for (const x of document.querySelectorAll(".exemple")) x.remove(); // le lien « Ouvrir la vraie page » ne s'activerait jamais
      $("etat").className = "message erreur";
      $("etat").setAttribute("role", "alert");
      $("etat-texte").textContent = "Le calcul n'a pas pu se charger (la connexion Internet est nécessaire la première fois). Vérifiez la connexion Internet, puis réessayez. Détail : " + echec;
      $("avance").hidden = true;
      if (!$("etat-reessayer")) $("etat").append(el("button", { id: "etat-reessayer", type: "button", class: "secondaire petit", texte: "Réessayer", onclick: () => location.reload() }));
      for (const m of document.querySelectorAll("[data-attente-calcul]")) m.replaceWith(messageEchec()); // pages déjà ouvertes : plus d'attente éternelle
      return;
    }
    mesures.total = Math.round(performance.now() - debut);
    mesures.pret = Math.round(performance.now()); // depuis l'ouverture de la page
    await bibliotheque("katex", () => !!window.katex).catch(() => {}); // formules : sans KaTeX elles s'affichent en texte brut
    if ("serviceWorker" in navigator && location.protocol === "https:") {
      navigator.serviceWorker.register("sw.js").catch((e) => console.warn("Hors ligne indisponible :", e));
    }
    console.info("MecaStruct prêt", mesures);
    etat("");
    document.dispatchEvent(new Event("mecastruct:pret"));
    // fin du chargement : seules les pages qui dépendent du calcul se redessinent (l'accueil et les textes gardent leur défilement et leurs replis)
    if (courante && ["machine", "convertisseur", "base", "references", "glossaire"].includes(courante.genre)) afficher();
    prechargerPages();
  }

  function genre(nom, rendu) {
    genres[nom] = rendu;
  }

  return { $, el, VERSION, clavierNombre, hautBarre: () => hauteurBarre, majBarre: () => majBarre(), redimensionnerFigures, DEPOT, FAMILLES, PAGES, page, nombre, fr, decimalesFr, exposants, echapper, markdown, memoire, sombre, message, copier, toast, retour, confirmer, copierImage, boutonImage, boutonSvg, svgDeLaFigure, titreImage, tableau, csv, formule, tracer, figure, onglets, calculer, genre, demarrer, attente, exemple, bibliotheque, messageEchec, mesures, paquets, preparer, telecharger, lireSaisie, ecrireSaisie, compresser, decompresser, lienEtude, oublierLien, pageCourante: () => courante, get pret() { return !!pont; } };
})();
