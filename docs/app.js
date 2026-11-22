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
    { id: "flambage", titre: "Flambage", famille: "structures", genre: "machine", calculs: ["fla"], pont: "structures", texte: "Charge critique d'Euler, élancement, conditions aux limites." },
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
    { id: "limites", titre: "Limites et vérifications", famille: "donnees", genre: "texte", source: "LIMITES.md", texte: "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas." },
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
    lire(cle, defaut) {
      try { const v = localStorage.getItem("mecastruct." + cle); return v === null ? defaut : JSON.parse(v); } catch (e) { return defaut; }
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
    let t = document.getElementById("toast");
    if (!t) { t = el("div", { id: "toast", role: "status", "aria-live": "polite" }); document.body.append(t); }
    t.className = "toast " + niveau;
    t.textContent = texte;
    t.hidden = false;
    void t.offsetWidth; // relance l'animation si un message précède
    t.classList.add("visible");
    clearTimeout(minuterieToast);
    minuterieToast = setTimeout(() => { t.classList.remove("visible"); minuterieToast = setTimeout(() => { t.hidden = true; }, 300); }, niveau === "erreur" ? 3500 : 2200);
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
      const { data, layout } = miseEnForme(cible._figure, sombre(), encre, racine.getPropertyValue("--figure-fond").trim() || fond);
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
  // Petite barre « Copier l'image » à placer juste au-dessus du bloc ; `cible` peut être un élément ou une fonction qui le donne.
  function boutonImage(cible, nom = "mecastruct.png") {
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
    return el("div", { class: "barre-image" }, b);
  }
  // Gros titre de bloc (h2) avec « Copier l'image » sur la même ligne, à droite.
  function titreImage(texte, cible, nom, classe = "") {
    return el("h2", { class: ("titre-bloc titre-image " + classe).trim() }, el("span", { texte }), boutonImage(cible, nom));
  }

  // Tableau {entetes, lignes} du pont, avec un bouton qui le copie pour Excel (tabulations).
  function tableau(t, titre) {
    // un nombre resté avec un point (texte du calcul) passe à la virgule ; les références de clause (« 6.3.2 ») ne bougent pas
    t = { ...t, lignes: t.lignes.map((l) => l.map((c) => (/^[−\-+]?\d+\.\d+(e[−\-+]?\d+)?$/.test(String(c).trim()) ? decimalesFr(c) : c))) };
    const tab = el("table", {},
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
    return el("div", { class: "tableau" }, titre ? el("h4", { texte: titre }) : null, boutonImage(tab, "tableau.png"), el("div", { class: "defile" }, tab), b);
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

  // Données et mise en page prêtes à tracer : thème sombre ou clair, virgule décimale.
  // Toujours une copie : Plotly réécrit sur place les objets reçus (« rgba(0,0,0,1) » → « rgba(0, 0, 0, 1) » dans les
  // formes), et la figure d'origine, gardée pour les changements de thème, ne doit pas bouger.
  function miseEnForme(f, foncee, encre, fond) {
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
    return { data, layout };
  }
  // Figure Plotly du pont : fond et textes suivent le thème, largeur suit la page.
  function tracer(div, f) {
    div._figure = f;
    const encre = getComputedStyle(document.documentElement).getPropertyValue("--encre").trim();
    const fond = getComputedStyle(document.documentElement).getPropertyValue("--figure-fond").trim();
    const { data, layout } = miseEnForme(f, sombre(), encre, fond);
    if (div.style.height) layout.height = div.clientHeight; // hauteur choisie à la souris (coin bas droit)
    else if (!layout.height) layout.height = 420; // hauteur de départ d'une figure qui n'en fixe pas
    Plotly.react(div, data, layout, { responsive: true, displaylogo: false, locale: "fr" });
    if (!div._suivi && window.ResizeObserver) { // la figure suit la hauteur donnée à son cadre
      let vue = 0;
      div._suivi = new ResizeObserver(() => {
        const h = div.clientHeight;
        if (!div.style.height || Math.abs(h - vue) < 4) return;
        vue = h;
        Plotly.relayout(div, { height: h });
      });
      div._suivi.observe(div);
    }
  }
  // avecBouton = false : le bouton « Copier l'image » est déjà dans le titre du bloc (schéma).
  function figure(f, classe = "figure", avecBouton = true) {
    const d = el("div", { class: classe });
    requestAnimationFrame(() => tracer(d, f));
    return avecBouton ? el("div", { class: "figure-bloc" }, boutonImage(d, "graphique.png"), d) : d;
  }

  // Onglets : liste = [{ id, titre, rendu(panneau) }] ; rendu à l'ouverture (Plotly a besoin d'un panneau visible).
  function onglets(liste, cle) {
    const barre = el("div", { class: "onglets", role: "tablist" });
    const panneau = el("div", { class: "panneau", role: "tabpanel" });
    const ouvrir = (id) => {
      for (const b of barre.children) {
        const choisi = b.dataset.id === id;
        b.setAttribute("aria-selected", String(choisi));
        b.tabIndex = choisi ? 0 : -1; // un seul onglet dans l'ordre de tabulation, les flèches font le tour
      }
      panneau.replaceChildren();
      liste.find((o) => o.id === id).rendu(panneau);
      if (cle) memoire.ecrire("onglet." + cle, id);
    };
    barre.append(...liste.map((o) => {
      const b = el("button", { type: "button", role: "tab", texte: o.titre, onclick: () => ouvrir(o.id) });
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
    return el("div", { class: "bloc-onglets" }, barre, panneau);
  }

  // ---------- bulles d'aide au survol ou au clavier ----------

  function bulles() {
    const b = el("div", { id: "bulle", role: "tooltip", hidden: true });
    document.body.append(b);
    const cacher = () => { b.hidden = true; };
    const montrer = (e) => {
      const cible = e.target.closest ? e.target.closest("[data-aide]") : null;
      if (!cible) return cacher();
      b.textContent = cible.dataset.aide;
      b.hidden = false;
      const r = cible.getBoundingClientRect();
      b.style.left = Math.max(8, Math.min(r.left, innerWidth - b.offsetWidth - 8)) + "px";
      b.style.top = (r.bottom + 6 + b.offsetHeight > innerHeight ? Math.max(8, r.top - b.offsetHeight - 6) : r.bottom + 6) + "px";
    };
    document.addEventListener("mouseover", montrer);
    document.addEventListener("focusin", montrer);
    for (const ev of ["focusout", "keydown", "scroll"]) document.addEventListener(ev, cacher, true);
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
    const gardee = memoire.lire("saisie." + ident, {});
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
  let lienLu = null;
  function lienEtude() {
    if (lienLu === null) {
      const m = location.hash.match(/\?(.*)$/);
      const p = new URLSearchParams(m ? m[1] : "");
      lienLu = p.get("calcul") && p.get("etude") ? { calcul: p.get("calcul"), etude: p.get("etude") } : false;
    }
    return lienLu || null;
  }
  function oublierLien() { // l'étude est chargée : l'adresse redevient celle de la page (pas de rechargement en boucle)
    lienLu = false;
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

  function menu() {
    const nav = $("menu");
    const boutons = [el("a", { href: "#/accueil", class: "famille", "data-famille": "accueil", texte: "Accueil" })];
    for (const f of FAMILLES) {
      const premiere = PAGES.find((p) => p.famille === f.id);
      boutons.push(el("a", { href: "#/" + premiere.id, class: "famille", "data-famille": f.id, texte: f.titre, aide: f.texte }));
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

  function majMenu(p) {
    const famille = p.famille || "accueil";
    for (const a of document.querySelectorAll("#menu .famille")) {
      if (a.dataset.famille === famille) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    }
    const sous = $("sous");
    const soeurs = PAGES.filter((x) => x.famille && x.famille === p.famille);
    sous.hidden = soeurs.length === 0;
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
    courante = p;
    majMenu(p);
    indiceDefilement($("menu"));
    indiceDefilement($("sous"));
    document.title = (p.id === "accueil" ? "" : p.titre + " · ") + "MecaStruct RdM";
    const contenu = $("contenu");
    contenu.replaceChildren();
    const rendu = genres[p.genre];
    if (rendu) rendu(contenu, p, { pret: !!pont });
    window.scrollTo(0, 0);
  }

  // ---------- démarrage ----------

  function etat(texte, pas) {
    $("etat").className = "message info";
    $("etat-texte").textContent = texte;
    $("etat").hidden = !texte;
    $("avance").hidden = !pas;
    if (pas) $("avance").value = pas;
  }

  async function chronometre(nom, travail) {
    const t = performance.now();
    const r = await travail();
    mesures[nom] = Math.round(performance.now() - t);
    return r;
  }

  // Actualisation complète : efface le service worker et les copies du site, puis recharge la page.
  async function actualiserSite() {
    try { for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister(); } catch (e) { /* pas de service worker */ }
    try { for (const n of await caches.keys()) if (n !== "mecastruct-cdn") await caches.delete(n); } catch (e) { /* pas de cache */ }
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
    verifierMiseAJour(build);
    // « Actualiser le site » recharge avec ?maj=… (contourne le cache) : une fois chargée, l'adresse redevient propre
    // (sinon elle se retrouve dans les liens copiés)
    if (/[?&]maj=/.test(location.search)) history.replaceState(null, "", location.pathname + location.hash);
    // lien « Aller au contenu » : le focus va au contenu sans changer l'adresse (le routeur lit le hash)
    document.querySelector(".evitement")?.addEventListener("click", (e) => { e.preventDefault(); $("page").focus(); });
    menu();
    bulles();
    window.addEventListener("hashchange", afficher);
    afficher(); // la page se lit pendant le chargement ; les calculs s'activent à la fin
    const debut = performance.now();
    prechargerPlotly();
    const empreinteZip = document.querySelector('meta[name="zip"]')?.content || Date.now();
    const archiveZip = fetch("mecastruct.zip?v=" + empreinteZip).then((r) => r.arrayBuffer()); // lue plus tard : déjà là
    archiveZip.catch(() => {}); // l'erreur est traitée à l'attente, plus bas
    try {
      const pyodide = await chronometre("python", () => loadPyodide());
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
        if (u) pont.appeler("base.restaurer", JSON.stringify({ utilisateur: u }));
        pont.appeler("formulaires"); // premier appel : charge les modules de calcul
      });
      App.pyodide = pyodide;
    } catch (e) {
      pont = null;
      $("etat").className = "message erreur";
      $("etat-texte").textContent = "Le calcul n'a pas pu se charger (connexion Internet nécessaire la première fois ; rechargez avec Ctrl+F5) : " + e;
      $("avance").hidden = true;
      return;
    }
    mesures.total = Math.round(performance.now() - debut);
    if ("serviceWorker" in navigator && location.protocol === "https:") {
      navigator.serviceWorker.register("sw.js").catch((e) => console.warn("Hors ligne indisponible :", e));
    }
    console.info("MecaStruct prêt", mesures);
    etat("");
    afficher();
    prechargerPages();
  }

  function genre(nom, rendu) {
    genres[nom] = rendu;
  }

  return { $, el, VERSION, DEPOT, FAMILLES, PAGES, page, nombre, fr, decimalesFr, exposants, echapper, markdown, memoire, sombre, message, copier, toast, retour, confirmer, copierImage, boutonImage, titreImage, tableau, formule, tracer, figure, onglets, calculer, genre, demarrer, mesures, paquets, preparer, telecharger, lireSaisie, ecrireSaisie, compresser, decompresser, lienEtude, oublierLien, pageCourante: () => courante, get pret() { return !!pont; } };
})();
