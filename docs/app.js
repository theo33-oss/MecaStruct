"use strict";
// Socle du site MecaStruct : démarrage de Pyodide, menu à cinq familles, adresses par page, outils d'affichage.
// Le calcul est le Python de l'application de bureau (application/mecastruct), exécuté dans le navigateur par
// mecastruct.pont ; ici, seulement l'affichage. Chaque genre de page (js/*.js) s'enregistre avec App.genre(nom, rendu).

const App = (() => {
  const $ = (id) => document.getElementById(id);
  const VERSION = "1.0.0";
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
    { id: "poutres", titre: "Poutres", famille: "structures", genre: "machine", calculs: ["beam"], pont: "structures", texte: "Poutre 2D isostatique ou hyperstatique : réactions, efforts, flèche, contraintes. L'ossature 3D est dans l'application de bureau." },
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
    { id: "base", titre: "Matériaux et profilés", famille: "donnees", genre: "bureau", capture: "base_de_donnees", texte: "Base de matériaux et de profilés normalisés." },
    { id: "references", titre: "Références", famille: "donnees", genre: "bureau", capture: "references", texte: "Formulaires de RdM et abaques." },
    { id: "limites", titre: "Limites et vérifications", famille: "donnees", genre: "texte", source: "LIMITES.md", texte: "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas." },
  ];
  const page = (id) => PAGES.find((p) => p.id === id);

  // ---------- nombres et textes ----------

  // « 0,25 » ou « 0.25 » → nombre ; texte vide → "" ; autre texte → NaN.
  function nombre(v) {
    if (typeof v === "number") return v;
    const t = String(v ?? "").trim().replace(/\s/g, "").replace(",", ".").replace("−", "-");
    if (t === "") return "";
    return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(t) ? Number(t) : NaN;
  }
  const fr = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
  // Décimales d'un texte du calcul à la française : « p = 10.1 MPa » → « p = 10,1 MPa ».
  const decimalesFr = (t) => String(t).replace(/(\d)\.(\d)/g, "$1,$2");
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

  // Tableau {entetes, lignes} du pont, avec un bouton qui le copie pour Excel (tabulations).
  function tableau(t, titre) {
    const tab = el("table", {},
      el("thead", {}, el("tr", {}, t.entetes.map((e) => el("th", { scope: "col", texte: e })))),
      el("tbody", {}, t.lignes.map((ligne) => el("tr", {}, ligne.map((c, j) => {
        const td = el("td", { texte: c });
        if (j > 0 && /^[−\-+]?[\d\s]+(,\d+)?(e[−\-+]?\d+)?$/.test(String(c).trim())) td.className = "num";
        if (/^(OK|oui)$/.test(c)) td.className = "verdict succes";
        if (/^(NON|non)$/.test(c)) td.className = "verdict erreur";
        return td;
      })))));
    const b = el("button", { type: "button", class: "secondaire petit", texte: "Copier le tableau", aide: "Copie le tableau avec des tabulations : à coller directement dans Excel." });
    b.addEventListener("click", async () => {
      b.textContent = (await copier([t.entetes, ...t.lignes].map((l) => l.join("\t")).join("\n"))) ? "Copié" : "Copie impossible";
      setTimeout(() => { b.textContent = "Copier le tableau"; }, 1500);
    });
    return el("div", { class: "tableau" }, titre ? el("h4", { texte: titre }) : null, el("div", { class: "defile" }, tab), b);
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
  const enSombre = (x) => JSON.parse(JSON.stringify(x).replace(/"(rgba\(0,0,0,1\)|black|white|#000000|#FFFFFF|#ffffff|rgba\(255,255,255,1\))"/g, (m, c) => `"${COULEURS_SOMBRES[c]}"`));

  // Figure Plotly du pont : fond et textes suivent le thème, largeur suit la page.
  function tracer(div, f) {
    div._figure = f;
    let data = f.data, layout = { ...(f.layout || {}) };
    if (sombre()) {
      data = enSombre(data);
      layout = enSombre(layout);
    }
    const encre = getComputedStyle(document.documentElement).getPropertyValue("--encre").trim();
    const fond = getComputedStyle(document.documentElement).getPropertyValue("--figure-fond").trim();
    layout.paper_bgcolor = fond;
    layout.plot_bgcolor = fond;
    layout.font = { ...(layout.font || {}), color: encre };
    layout.autosize = true;
    delete layout.width;
    if (layout.title && layout.title.text) layout.title = { ...layout.title, x: 0.01, xanchor: "left" };
    Plotly.react(div, data, layout, { responsive: true, displaylogo: false, locale: "fr" });
  }
  function figure(f, classe = "figure") {
    const d = el("div", { class: classe });
    requestAnimationFrame(() => tracer(d, f));
    return d;
  }

  // Onglets : liste = [{ id, titre, rendu(panneau) }] ; rendu à l'ouverture (Plotly a besoin d'un panneau visible).
  function onglets(liste, cle) {
    const barre = el("div", { class: "onglets", role: "tablist" });
    const panneau = el("div", { class: "panneau", role: "tabpanel" });
    const ouvrir = (id) => {
      for (const b of barre.children) b.setAttribute("aria-selected", String(b.dataset.id === id));
      panneau.replaceChildren();
      liste.find((o) => o.id === id).rendu(panneau);
      if (cle) memoire.ecrire("onglet." + cle, id);
    };
    barre.append(...liste.map((o) => {
      const b = el("button", { type: "button", role: "tab", texte: o.titre, onclick: () => ouvrir(o.id) });
      b.dataset.id = o.id;
      return b;
    }));
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
  async function preparer(p) {
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

  function afficher() {
    const id = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || "accueil";
    const p = page(id) || page("accueil");
    courante = p;
    majMenu(p);
    document.title = (p.id === "accueil" ? "" : p.titre + " · ") + "MecaStruct RdM Pro";
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

  async function demarrer() {
    $("version").textContent = "version " + VERSION;
    menu();
    bulles();
    window.addEventListener("hashchange", afficher);
    afficher(); // la page se lit pendant le chargement ; les calculs s'activent à la fin
    const debut = performance.now();
    try {
      const pyodide = await chronometre("python", () => loadPyodide());
      etat("Préparation 2/4 : bibliothèques de calcul (numpy, pandas)…", 2);
      await chronometre("numpy_pandas", () => pyodide.loadPackage(["numpy", "pandas", "micropip"]));
      etat("Préparation 3/4 : graphiques (plotly)…", 3);
      await chronometre("plotly", () => pyodide.pyimport("micropip").install("plotly==7.1.0")); // même version que l'application de bureau (requirements.lock)
      etat("Préparation 4/4 : calculs MecaStruct, tables ISO 286, matériaux…", 4);
      await chronometre("mecastruct", async () => {
        const empreinte = document.querySelector('meta[name="zip"]').content || Date.now();
        const archive = await (await fetch("mecastruct.zip?v=" + empreinte)).arrayBuffer();
        pyodide.unpackArchive(archive, "zip", { extractDir: "/app" });
        pyodide.runPython("import sys; sys.path.insert(0, '/app')");
        pont = pyodide.pyimport("mecastruct.pont");
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
    console.info("MecaStruct prêt", mesures);
    etat("");
    afficher();
  }

  function genre(nom, rendu) {
    genres[nom] = rendu;
  }

  return { $, el, VERSION, DEPOT, FAMILLES, PAGES, page, nombre, fr, decimalesFr, echapper, markdown, memoire, sombre, message, copier, tableau, formule, tracer, figure, onglets, calculer, genre, demarrer, mesures, paquets, preparer, telecharger, compresser, decompresser, lienEtude, oublierLien, pageCourante: () => courante, get pret() { return !!pont; } };
})();
