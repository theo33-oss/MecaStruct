"use strict";
// Comparer des études : sur chaque page de calcul, étudier des variantes d'un même cas sans perdre l'étude de référence.
// La comparaison est indépendante de la saisie de la page (elle ne la modifie jamais) : chaque étude est calculée par
// App.calculer(ident, saisie reconstruite), puis résumée (verdict, mode dimensionnant, coefficient de sécurité minimal,
// grandeurs clés du résultat) dans un tableau, et tracée dans un graphique.
//
// FORMAT (App.memoire « comparaison.<ident> » et fichier « Exporter en JSON ») :
//   {
//     format: "mecastruct-comparaison", version: 1,
//     calcul: "<ident>",                      // identifiant du calcul du pont (aju, fre, rlt, beam…)
//     outil: "MecaStruct RdM 1.7.0",          // version du site qui a écrit le fichier
//     unites: { "<champ>": "<unité>" },       // unité de chaque champ de la saisie : des unités différentes = fichier refusé
//     cree: "2026-11-22T10:00:00.000Z",
//     reference: "<id de l'étude de référence>",
//     base: { ...saisie complète de la référence },   // copie de la saisie de la page au moment de la création
//     etudes: [ { id, nom, ecarts: { "<champ>": valeur } } ]  // les variantes ne portent QUE leurs écarts avec la référence
//   }
// Invariants : « reference » désigne une des études ; l'étude de référence a des écarts vides (c'est la base elle-même) ;
// saisie d'une étude = { ...base, ...ecarts }. Modifier la référence modifie donc aussi les variantes qui n'ont pas
// d'écart sur ce champ. « Définir comme référence » change de base et recalcule les écarts : les valeurs de chaque étude
// ne bougent pas. Les résultats ne sont pas gardés : ils sont recalculés à chaque ouverture.
//
// Un fichier d'une autre page, d'une autre version de format, avec d'autres unités ou des champs inconnus est refusé avec
// un message ; la comparaison en cours n'est jamais mélangée avec lui.

(() => {
  const { el } = App;
  const FORMAT = "mecastruct-comparaison";
  const MAX_ETUDES = 10;
  const MAX_CACHE = 60;
  const TYPES_SCALAIRES = [undefined, "nombre", "liste", "liste-fixe", "case", "texte"]; // champs modifiables dans une variante
  const copie = (x) => JSON.parse(JSON.stringify(x));
  const egal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const identifiant = () => "e" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const nf = (x, n = 3) => (Number.isFinite(x) ? App.exposants(App.fr(String(Number(x.toPrecision(n))))) : "∞");
  const sansMouvement = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const propre = (t) => String(t ?? "").replace(/[\t\r\n]+/g, " ").trim(); // une cellule de tableur : ni tabulation ni retour

  // « 1582.9 » ou « 1 582,9 » → nombre ; texte qui n'est pas un nombre seul (« 16 / 73 », « H7/r6 ») → null.
  function nombreDe(t) {
    const s = String(t ?? "").replace(/[\s  ]/g, "").replace(",", ".").replace("−", "-");
    return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s) && Number.isFinite(Number(s)) ? Number(s) : null;
  }
  const proches = (a, b) => a === b || Math.abs(a - b) <= 1e-9 * Math.max(Math.abs(a), Math.abs(b), 1e-30);
  function ecartRelatif(x, ref) {
    if (!Number.isFinite(x) || !Number.isFinite(ref) || ref === 0 || proches(x, ref)) return null;
    const p = 100 * (x - ref) / Math.abs(ref);
    return Math.abs(p) < 0.005 ? null : `${p > 0 ? "+" : "−"}${nf(Math.abs(p), 2)} %`;
  }

  function monter(ident, f, bloc, opts = {}) {
    if (!f || !f.defaut || !f.groupes) return null;
    const lirePage = typeof opts.saisie === "function" ? opts.saisie : () => ({});
    const verifierNombre = opts.verifierNombre || ((c, t) => { const v = App.nombre(t); return v === "" || Number.isNaN(v) ? [NaN, "Nombre attendu."] : [v, ""]; });
    const titreCalcul = f.titre || ident;
    const cleMemo = "comparaison." + ident;

    // ---------- champs de la page ----------
    const tousChamps = f.groupes.flatMap((g) => g.champs);
    const scalaires = tousChamps.filter((c) => TYPES_SCALAIRES.includes(c.type) && c.id in f.defaut);
    const parId = new Map(tousChamps.map((c) => [c.id, c]));
    const unites = Object.fromEntries(scalaires.map((c) => [c.id, c.unite || ""]));
    const conditions = (c) => [].concat(c.si || []);
    const visible = (c, s) => conditions(c).every((k) => k.valeurs.includes(s[k.id]));
    const controleurs = new Set(tousChamps.flatMap((c) => [...conditions(c).map((k) => k.id), c.options_de && c.type === "liste" && c.options_de.depuis].filter(Boolean)));
    const ordreCles = [...scalaires.map((c) => c.id), ...Object.keys(f.defaut).filter((k) => !scalaires.some((c) => c.id === k))];
    const libelleCle = (k) => { const c = parId.get(k); return c ? c.libelle + (c.unite ? ` (${c.unite})` : "") : k; };
    const affiche = (v) => (typeof v === "number" && Number.isFinite(v) ? App.exposants(App.fr(String(Number(v.toPrecision(10))))) : App.fr(v ?? ""));

    function valeurTexte(c, v) {
      if (!c) return typeof v === "object" ? "modifié" : String(v ?? "");
      if (c.type === "case") return v ? "oui" : "non";
      if (c.type === "liste" || c.type === "liste-fixe") {
        const i = (c.options || []).indexOf(v);
        return i >= 0 && c.etiquettes ? c.etiquettes[i] : String(v);
      }
      if (typeof v === "number") return affiche(v) + (c.unite ? " " + c.unite : "");
      return String(v ?? "");
    }

    // ---------- données ----------
    let etat = null; // la comparaison (format ci-dessus) ou null
    let refus = ""; // pourquoi la comparaison gardée dans ce navigateur n'est pas utilisée
    const cache = new Map(); // empreinte de saisie → résumé du calcul
    let jeton = 0;
    const ouvertes = new Set(); // études dont les champs sont affichés
    const prefs = { x: null, y: null };
    let messageEl = null;

    const saisieDe = (e) => Object.assign(copie(etat.base), copie(e.ecarts));
    const etudeRef = () => etat.etudes.find((e) => e.id === etat.reference);
    const sauver = () => App.memoire.ecrire(cleMemo, etat);
    const ecartsDe = (base, plein) => {
      const r = {};
      for (const k of new Set([...Object.keys(base), ...Object.keys(plein)])) if (!egal(plein[k], base[k])) r[k] = copie(plein[k]);
      return r;
    };
    // nouvelle référence : les valeurs de chaque étude ne bougent pas, seuls les écarts changent de point de départ
    function rebaser(e) {
      const pleines = new Map(etat.etudes.map((x) => [x.id, saisieDe(x)]));
      etat.base = pleines.get(e.id);
      etat.reference = e.id;
      for (const x of etat.etudes) x.ecarts = ecartsDe(etat.base, pleines.get(x.id));
      etat.etudes = [e, ...etat.etudes.filter((x) => x !== e)]; // la référence est toujours la première
    }
    const nettoyerEcarts = () => { for (const x of etat.etudes) for (const k of Object.keys(x.ecarts)) if (egal(x.ecarts[k], etat.base[k])) delete x.ecarts[k]; };

    function nomLibre(depart) {
      const pris = new Set(etat.etudes.map((e) => e.nom));
      if (!pris.has(depart)) return depart;
      for (let n = 2; ; n++) if (!pris.has(`${depart} (${n})`)) return `${depart} (${n})`;
    }
    const prochaineVariante = () => { let n = 1; while (etat.etudes.some((e) => e.nom === `Variante ${n}`)) n++; return `Variante ${n}`; };

    function creer() {
      const e = { id: identifiant(), nom: "Référence", ecarts: {} };
      etat = { format: FORMAT, version: 1, calcul: ident, outil: "MecaStruct RdM " + App.VERSION, unites: copie(unites), cree: new Date().toISOString(),
        reference: e.id, base: copie({ ...f.defaut, ...lirePage() }), etudes: [e] };
      refus = "";
      sauver();
    }

    // ---------- validation d'une comparaison lue (mémoire ou fichier) ----------
    function valider(d) {
      const non = (erreur, proposerNouvelle = true) => ({ ok: false, erreur, proposerNouvelle });
      if (!d || typeof d !== "object" || Array.isArray(d) || d.format !== FORMAT) return non("Ce fichier n'est pas une comparaison MecaStruct.");
      if (d.version !== 1) return non(`Version de format non prise en charge (${d.version}) : ce site lit la version 1.`);
      if (d.calcul !== ident) {
        const p = App.PAGES.find((x) => (x.calculs || []).includes(d.calcul));
        return non(`Cette comparaison concerne ${p ? `la page « ${p.titre} » (calcul « ${d.calcul} »)` : `un autre calcul (« ${d.calcul} »)`} et non « ${titreCalcul} » : elle n'a pas été importée. On ne compare que des études du même calcul.`);
      }
      if (!d.base || typeof d.base !== "object" || Array.isArray(d.base)) return non("Étude de référence absente du fichier (saisie de base manquante).");
      for (const [k, u] of Object.entries(d.unites || {})) {
        if (!(k in f.defaut)) return non(`Champ inconnu « ${k} » : la comparaison vient d'une autre version de la page.`);
        if (k in unites && unites[k] !== u) return non(`Unités différentes pour « ${libelleCle(k)} » : « ${u} » dans le fichier, « ${unites[k]} » ici. Les études ne sont jamais mélangées.`);
      }
      const typeOk = (k, v) => (Array.isArray(f.defaut[k]) ? Array.isArray(v) : typeof v === typeof f.defaut[k] && (v === null) === (f.defaut[k] === null));
      for (const [k, v] of Object.entries(d.base)) {
        if (!(k in f.defaut)) return non(`Champ inconnu « ${k} » : la comparaison vient d'une autre version de la page.`);
        if (!typeOk(k, v)) return non(`Valeur incompatible pour « ${libelleCle(k)} » dans la saisie de base.`);
      }
      if (!Array.isArray(d.etudes) || !d.etudes.length) return non("Aucune étude dans le fichier.");
      if (d.etudes.length > MAX_ETUDES) return non(`Trop d'études (${d.etudes.length}) : ${MAX_ETUDES} au plus.`);
      const ids = new Set();
      for (const e of d.etudes) {
        if (!e || typeof e.id !== "string" || !e.id || ids.has(e.id)) return non("Études sans identifiant unique.");
        ids.add(e.id);
        if (typeof e.nom !== "string" || !e.ecarts || typeof e.ecarts !== "object" || Array.isArray(e.ecarts)) return non(`Étude « ${e.id} » mal formée.`);
        for (const [k, v] of Object.entries(e.ecarts)) {
          if (!(k in f.defaut)) return non(`Étude « ${e.nom} » : champ inconnu « ${k} » (autre version de la page).`);
          if (!typeOk(k, v)) return non(`Étude « ${e.nom} » : valeur incompatible pour « ${libelleCle(k)} ».`);
        }
      }
      if (!ids.has(d.reference)) return non(`L'étude de référence « ${d.reference} » est absente du fichier.`);
      const r = copie(d);
      r.base = { ...copie(f.defaut), ...r.base };
      r.unites = copie(unites);
      const ref = r.etudes.find((e) => e.id === r.reference);
      if (Object.keys(ref.ecarts).length || r.etudes[0] !== ref) { const avant = etat; etat = r; rebaser(ref); etat = avant; } // référence avec écarts, ou pas la première : ramenée à la base
      return { ok: true, donnees: r };
    }
    {
      const gardee = App.memoire.lire(cleMemo, null);
      if (gardee) {
        const v = valider(gardee);
        if (v.ok) etat = v.donnees;
        else refus = v.erreur;
      }
    }

    // ---------- résumé d'un calcul ----------
    function grandeursDe(s) {
      const g = new Map();
      // cle : identifie la grandeur d'une étude à l'autre ; nom : libellé ; piece : ligne d'un tableau à plusieurs colonnes
      // (« Alésage H7 »), qui change d'une étude à l'autre quand la grandeur est la même.
      const ajouter = (cle, nom, texte, piece) => {
        if (g.size >= 40) return;
        let c = cle, k = 2;
        while (g.has(c)) c = `${cle} (${k++})`;
        g.set(c, { nom, texte: App.decimalesFr(String(texte ?? "")), num: nombreDe(texte), piece });
      };
      const tables = Object.entries(s.tables || {});
      for (const [nomTable, t] of tables) {
        const pre = tables.length > 1 ? nomTable + " · " : "";
        if (t.entetes.length === 2) for (const l of t.lignes) ajouter(pre + l[0], pre + l[0], l[1]);
        else if (t.lignes.length <= 10 && t.entetes.length <= 8) t.lignes.forEach((l, i) => { for (let j = 1; j < t.entetes.length; j++) ajouter(`${pre}#${i}|${t.entetes[j]}`, `${pre}${l[0]} · ${t.entetes[j]}`, l[j], String(l[0])); });
      }
      for (const [n, v] of s.metriques || []) ajouter(n, n, v);
      return g;
    }
    function resumer(r) {
      if (!r.ok) return { erreur: String(r.erreur || "erreur inconnue") };
      const s = r.sortie;
      const crit = s.criteres || [];
      const pire = crit.reduce((m, c) => (!m || c.taux > m.taux ? c : m), null);
      let sMin = null, critS = null;
      for (const c of crit) if (c.s_obtenu !== null && c.s_obtenu !== undefined && (sMin === null || c.s_obtenu < sMin)) { sMin = c.s_obtenu; critS = c; }
      return {
        verdict: s.ok === true ? "ok" : s.ok === false ? "ko" : "indic",
        status: String(s.status || ""),
        nCrit: crit.length,
        mode: pire ? pire.mode : null,
        tauxMax: pire ? pire.taux : null,
        sMin: crit.length ? (sMin === null ? Infinity : sMin) : null,
        sDemande: critS ? critS.s_demande : (pire ? pire.s_demande : null),
        grandeurs: grandeursDe(s),
      };
    }
    const empreinte = (s) => JSON.stringify(s);
    function planifier() {
      const mon = ++jeton;
      const vus = new Set();
      const aFaire = [];
      for (const e of etat.etudes) {
        const s = saisieDe(e), k = empreinte(s);
        if (!cache.has(k) && !vus.has(k)) { vus.add(k); aFaire.push([k, s]); }
      }
      const suite = () => {
        if (mon !== jeton || !section.isConnected || !details.open) return;
        const x = aFaire.shift();
        if (!x) return;
        cache.set(x[0], resumer(App.calculer(ident, x[1])));
        while (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
        rendreSynthese();
        setTimeout(suite, 0);
      };
      if (aFaire.length) setTimeout(suite, 0);
    }

    // ---------- interface : squelette ----------
    const zoneMessage = el("div", { class: "cmp-message", "aria-live": "polite" });
    const zoneContenu = el("div", { class: "cmp-contenu" });
    const corps = el("div", { class: "cmp-corps" },
      el("p", { class: "legende cmp-info", texte: "La comparaison est conservée seulement dans ce navigateur (rien n'est envoyé sur Internet). Pour la garder ou la partager, utilisez « Exporter en JSON »." }),
      zoneMessage, zoneContenu);
    const resume = el("summary", {}, el("h2", { texte: "Comparer des études" }));
    const details = el("details", { class: "repli cmp-details" }, resume, corps);
    const section = el("section", { class: "comparer", id: "cmp-" + ident, "aria-label": "Comparer des études" }, details);
    const colonne = bloc.querySelector(".colonne-resultat");
    (colonne || bloc).append(section);

    function dire(niveau, texte, ...actions) {
      messageEl = el("div", { class: "message " + niveau, role: niveau === "erreur" ? "alert" : "status" }, el("span", { texte }), ...actions.flatMap((a) => [" ", a]));
      zoneMessage.replaceChildren(messageEl);
    }
    const bouton = (texte, fn, classe = "secondaire petit", aide) => el("button", { type: "button", class: classe, texte, aide, onclick: fn });
    function demander(texte, libelle, fn) { // confirmation en ligne, sans boîte de dialogue
      dire("avertissement", texte, bouton(libelle, () => { zoneMessage.replaceChildren(); fn(); }, "primaire petit"), bouton("Annuler", () => zoneMessage.replaceChildren()));
    }

    // références des zones de l'espace actif
    let zoneListe = null, zoneEtatPage = null, zoneTableau = null, cocheMasque = null, selX = null, selY = null, zoneGraphe = null, zoneDescription = null;
    let dernierTSV = "", dernierEnAttente = false;

    function rendreTout() {
      if (!etat) return rendreVide();
      zoneListe = el("ul", { class: "cmp-liste" });
      zoneEtatPage = el("p", { class: "legende cmp-etat-page cmp-ecran" });
      zoneTableau = el("div", { class: "cmp-zone-tableau" });
      cocheMasque = el("input", { type: "checkbox" });
      cocheMasque.addEventListener("change", () => zoneTableau.classList.toggle("cmp-masque", cocheMasque.checked));
      selX = el("select", { "aria-label": "Abscisse du graphique" });
      selY = el("select", { "aria-label": "Grandeur en ordonnée" });
      selX.addEventListener("change", () => { prefs.x = selX.value; rendreSynthese(); });
      selY.addEventListener("change", () => { prefs.y = selY.value; rendreSynthese(); });
      zoneGraphe = el("div", { class: "cmp-graphe" });
      zoneDescription = el("p", { class: "legende cmp-description" });
      const entree = fichierEntree();
      const barre = el("div", { class: "ligne cmp-barre cmp-ecran", role: "group", "aria-label": "Actions sur la comparaison" },
        bouton("Ajouter une variante", ajouterVariante, "primaire petit", "Copie l'étude de référence ; vous modifiez ensuite un ou plusieurs de ses champs."),
        bouton("Ajouter la saisie de la page", ajouterDepuisPage, "secondaire petit", "Ajoute comme étude ce qui est saisi dans le formulaire de la page en ce moment."),
        bouton("Figer la saisie de la page comme référence", figerReference, "secondaire petit", "Remplace les valeurs de l'étude de référence par la saisie de la page. Les variantes gardent leurs écarts."),
        bouton("Exporter en JSON", exporter, "secondaire petit", "Télécharge la comparaison (.json) : seul moyen de la garder hors de ce navigateur."),
        bouton("Importer", () => entree.click(), "secondaire petit", "Ouvre une comparaison exportée. Un fichier d'un autre calcul ou d'autres unités est refusé."),
        bouton("Copier la synthèse", copierSynthese, "secondaire petit", "Copie le tableau avec des tabulations : à coller directement dans Excel."),
        bouton("Imprimer", imprimer, "secondaire petit", "Imprime la synthèse seule (tableau et graphique)."),
        bouton("Nouvelle comparaison", nouvelle, "secondaire petit", "Efface cette comparaison et repart de la saisie de la page."),
        entree);
      zoneContenu.replaceChildren(zoneEtatPage, barre,
        el("h4", { class: "cmp-titre", texte: "Études" }), zoneListe,
        el("h4", { class: "cmp-titre", texte: "Synthèse" }),
        el("label", { class: "case cmp-ecran cmp-masquer" }, cocheMasque, " Masquer les valeurs identiques"),
        zoneTableau,
        el("h4", { class: "cmp-titre cmp-ecran", texte: "Graphique" }),
        el("div", { class: "ligne cmp-choix cmp-ecran" }, el("label", {}, "Abscisse (paramètre)", selX), el("label", {}, "Grandeur en ordonnée", selY)),
        zoneGraphe, zoneDescription);
      rendreListe();
      rendreSynthese();
      planifier();
    }

    function rendreVide() {
      const entree = fichierEntree();
      zoneContenu.replaceChildren(
        el("p", { texte: "Aucune comparaison pour ce calcul. Créez-en une à partir de ce qui est saisi dans la page : cette étude devient la référence, puis vous ajoutez des variantes qui ne changent que quelques champs." }),
        el("div", { class: "ligne" }, bouton("Créer une comparaison à partir de la saisie de la page", () => { creer(); zoneMessage.replaceChildren(); rendreTout(); }, "primaire"),
          bouton("Importer une comparaison", () => entree.click(), "secondaire"), entree));
      if (refus && !messageEl?.isConnected) dire("avertissement", `La comparaison gardée dans ce navigateur n'est plus compatible avec cette page et n'est pas utilisée : ${refus} Créer une nouvelle comparaison la remplacera.`);
    }

    function majEtatPage() {
      if (!zoneEtatPage || !zoneEtatPage.isConnected || !etat) return;
      const ref = saisieDe(etudeRef()), page = { ...copie(f.defaut), ...copie(lirePage()) };
      const diff = Object.keys(ref).filter((k) => !egal(ref[k], page[k]));
      zoneEtatPage.textContent = diff.length
        ? `La saisie de la page diffère de la référence (${diff.length} champ${diff.length > 1 ? "s" : ""} : ${diff.slice(0, 4).map(libelleCle).join(", ")}${diff.length > 4 ? "…" : ""}). « Ajouter la saisie de la page » en fait une étude.`
        : "La saisie de la page est identique à l'étude de référence.";
    }

    // ---------- liste des études ----------
    function rendreListe() {
      zoneListe.replaceChildren(...etat.etudes.map((e, n) => carte(e, n)));
      majEtatPage();
    }

    function carte(e, n) {
      const estRef = e.id === etat.reference;
      const nom = el("input", { type: "text", value: e.nom, "aria-label": `Nom de l'étude ${n + 1}`, maxlength: "60", class: "cmp-nom" });
      nom.addEventListener("input", () => { e.nom = nom.value; sauver(); majSynthese(); });
      nom.addEventListener("change", () => { if (!nom.value.trim()) { nom.value = e.nom = nomLibre(`Étude ${n + 1}`); sauver(); majSynthese(); } });
      const zoneEdition = el("div", { class: "cmp-edition", id: "cmp-edition-" + e.id, hidden: !ouvertes.has(e.id) });
      const modifier = el("button", { type: "button", class: "secondaire petit", "aria-expanded": String(ouvertes.has(e.id)), "aria-controls": "cmp-edition-" + e.id,
        texte: ouvertes.has(e.id) ? "Masquer les valeurs" : "Modifier les valeurs",
        aide: "Affiche les champs de cette étude : changez-en un ou plusieurs, seuls les écarts avec la référence sont gardés." });
      const basculer = () => {
        const ouvre = zoneEdition.hidden;
        zoneEdition.hidden = !ouvre;
        if (ouvre) { ouvertes.add(e.id); dessinerEdition(e, zoneEdition); } else ouvertes.delete(e.id);
        modifier.setAttribute("aria-expanded", String(ouvre));
        modifier.textContent = ouvre ? "Masquer les valeurs" : "Modifier les valeurs";
      };
      modifier.addEventListener("click", basculer);
      if (ouvertes.has(e.id)) dessinerEdition(e, zoneEdition);
      const nbEcarts = Object.keys(e.ecarts).length;
      return el("li", { class: "cmp-etude" + (estRef ? " cmp-reference" : ""), "data-id": e.id },
        el("div", { class: "cmp-tete" },
          el("label", { class: "cmp-label-nom" }, el("span", { class: "cache", texte: `Nom de l'étude ${n + 1}` }), nom),
          estRef ? el("span", { class: "cmp-badge", texte: "Référence" }) : el("span", { class: "legende cmp-nb", texte: nbEcarts ? `${nbEcarts} écart${nbEcarts > 1 ? "s" : ""} avec la référence` : "identique à la référence" })),
        el("div", { class: "ligne cmp-actions cmp-ecran" }, modifier,
          bouton("Dupliquer", () => dupliquer(e), "secondaire petit", "Ajoute une copie de cette étude."),
          estRef ? null : bouton("Définir comme référence", () => definirReference(e), "secondaire petit", "Les autres études sont alors comparées à celle-ci ; leurs valeurs ne changent pas."),
          bouton("Remplacer par la saisie de la page", () => remplacerParPage(e), "secondaire petit", "Recopie dans cette étude ce qui est saisi dans la page."),
          bouton("Retirer", () => retirer(e), "secondaire petit", "Retire cette étude de la comparaison.")),
        zoneEdition);
    }

    // ---------- modification d'une étude ----------
    function appliquerChamp(e, id, v) {
      const estRef = e.id === etat.reference;
      const s = estRef ? copie(etat.base) : saisieDe(e);
      s[id] = v;
      const suite = (f.suites || {})[id]; // le matériau change E, Re… comme dans la page
      if (suite) {
        const r = App.calculer(suite.calcul, { nom: v, champs: suite.champs, saisie: s });
        if (r.ok) for (const [k, x] of Object.entries(r.sortie)) if (x !== null) s[k] = x;
      }
      for (const c of tousChamps) { // listes dépendantes (profilés de la famille choisie) : première option si la valeur n'existe plus
        if (c.type !== "liste" || !c.options_de) continue;
        const r = App.calculer(c.options_de.calcul, { [c.options_de.cle]: s[c.options_de.depuis] });
        const options = r.ok ? r.sortie : [];
        if (options.length && !options.includes(s[c.id])) s[c.id] = options[0];
      }
      if (estRef) { etat.base = s; nettoyerEcarts(); } else e.ecarts = ecartsDe(etat.base, s);
      sauver();
    }

    function dessinerEdition(e, zone) {
      const s = saisieDe(e);
      const estRef = e.id === etat.reference;
      const groupes = [];
      for (const g of f.groupes) {
        const champs = g.champs.filter((c) => scalaires.includes(c) && visible(c, s));
        if (champs.length) groupes.push(el("fieldset", { class: "cmp-groupe" }, el("legend", { texte: g.titre }), el("div", { class: "grille" }, champs.map((c) => controle(c, e)))));
      }
      const autres = tousChamps.filter((c) => !TYPES_SCALAIRES.includes(c.type) && c.id in f.defaut);
      zone.replaceChildren(...[
        estRef ? el("p", { class: "legende", texte: "Étude de référence : modifier un champ ici le modifie aussi dans les variantes qui n'ont pas d'écart sur ce champ." }) : null,
        ...groupes,
        autres.length ? el("p", { class: "legende", texte: `${autres.map((c) => c.libelle).join(", ")} : à modifier dans la page, puis « Remplacer par la saisie de la page ».` }) : null].filter(Boolean));
    }

    function controle(c, e) {
      const s = saisieDe(e);
      const v = s[c.id];
      const refV = etat.base[c.id];
      const titre = c.libelle + (c.unite ? ` (${c.unite})` : "");
      const estRef = e.id === etat.reference;
      const aide = c.aide || undefined;
      const indice = el("span", { class: "cmp-indice" });
      const etiquette = el("label", { aide });
      const marquer = () => {
        const diff = !estRef && c.id in e.ecarts;
        etiquette.classList.toggle("cmp-ecart", diff);
        indice.textContent = diff ? `≠ référence : ${valeurTexte(c, refV)}` : "";
        indice.hidden = !diff;
      };
      const rafraichir = (id) => { // un champ qui en commande d'autres, ou un matériau : les champs de l'étude sont redessinés
        const zone = etiquette.closest(".cmp-edition");
        if (!zone) return;
        dessinerEdition(e, zone);
        zone.querySelector(`[data-id="${CSS.escape(id)}"]`)?.focus();
      };
      const apres = (id, redessiner) => {
        marquer();
        majSynthese();
        majNb(e);
        if (redessiner) rafraichir(id);
      };
      if (c.type === "case") {
        const i = el("input", { type: "checkbox" });
        i.checked = !!v;
        i.dataset.id = c.id;
        i.addEventListener("change", () => { appliquer(e, c.id, i.checked); apres(c.id, controleurs.has(c.id)); });
        etiquette.className = "case";
        etiquette.append(i, " " + c.libelle, indice);
        marquer();
        return etiquette;
      }
      let entree;
      if (c.type === "liste" || c.type === "liste-fixe") {
        let options = c.options || [];
        if (c.options_de) { const r = App.calculer(c.options_de.calcul, { [c.options_de.cle]: s[c.options_de.depuis] }); options = r.ok ? r.sortie : []; }
        const option = (o, i) => el("option", { value: String(o), texte: c.etiquettes ? c.etiquettes[i] : String(o) });
        let contenu = options.map(option);
        if (c.familles && !c.options_de) contenu = [...new Set(c.familles)].map((n) => el("optgroup", { label: n }, options.map((o, i) => (c.familles[i] === n ? option(o, i) : null))));
        entree = el("select", {}, contenu);
        entree.value = String(v);
        entree.addEventListener("change", () => {
          appliquer(e, c.id, typeof options[0] === "number" ? Number(entree.value) : entree.value);
          apres(c.id, true);
        });
      } else if (c.type === "texte") {
        entree = el("input", { type: "text", value: v ?? "" });
        entree.addEventListener("input", () => { appliquer(e, c.id, entree.value); apres(c.id, false); });
      } else {
        entree = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false" });
        entree.value = affiche(v);
        const erreur = el("span", { class: "erreur-champ", hidden: true });
        etiquette.append(titre, entree, erreur, indice);
        entree.dataset.id = c.id;
        entree.addEventListener("input", () => {
          const [x, texte] = verifierNombre(c, entree.value);
          entree.classList.toggle("invalide", !!texte);
          entree.setAttribute("aria-invalid", String(!!texte));
          erreur.textContent = texte ? texte + " (valeur précédente conservée)" : "";
          erreur.hidden = !texte;
          if (texte) return;
          appliquer(e, c.id, x);
          apres(c.id, false);
        });
        entree.addEventListener("change", () => { if (!entree.classList.contains("invalide") && (controleurs.has(c.id) || (f.suites || {})[c.id])) rafraichir(c.id); });
        marquer();
        return etiquette;
      }
      entree.dataset.id = c.id;
      etiquette.append(titre, entree, indice);
      marquer();
      return etiquette;
    }
    const appliquer = (e, id, v) => { appliquerChamp(e, id, v); };
    function majNb(e) { // « n écarts » de la carte, sans la redessiner
      const li = zoneListe && zoneListe.querySelector(`[data-id="${CSS.escape(e.id)}"] .cmp-nb`);
      if (li) { const n = Object.keys(e.ecarts).length; li.textContent = n ? `${n} écart${n > 1 ? "s" : ""} avec la référence` : "identique à la référence"; }
    }

    // ---------- actions ----------
    function ajouterEtude(e, message) {
      if (etat.etudes.length >= MAX_ETUDES) return dire("avertissement", `${MAX_ETUDES} études au plus : retirez-en une pour en ajouter.`);
      etat.etudes.push(e);
      sauver();
      rendreListe();
      majSynthese(true);
      dire("succes", message);
      zoneListe.querySelector(`[data-id="${CSS.escape(e.id)}"] .cmp-nom`)?.focus();
    }
    function ajouterVariante() {
      const e = { id: identifiant(), nom: prochaineVariante(), ecarts: {} };
      ouvertes.clear(); // seule la nouvelle variante est dépliée
      ouvertes.add(e.id);
      ajouterEtude(e, `${e.nom} ajoutée : c'est une copie de la référence. Modifiez un ou plusieurs de ses champs ci-dessous.`);
    }
    function ajouterDepuisPage() {
      const e = { id: identifiant(), nom: nomLibre("Saisie de la page"), ecarts: ecartsDe(etat.base, { ...copie(f.defaut), ...copie(lirePage()) }) };
      ajouterEtude(e, `« ${e.nom} » ajoutée avec ${Object.keys(e.ecarts).length} écart(s) avec la référence.`);
    }
    function dupliquer(e) {
      const copieE = { id: identifiant(), nom: nomLibre(e.nom + " (copie)"), ecarts: copie(e.ecarts) };
      ajouterEtude(copieE, `« ${e.nom} » dupliquée.`);
    }
    function definirReference(e) {
      rebaser(e);
      sauver();
      rendreListe();
      majSynthese(true);
      dire("succes", `« ${e.nom} » est maintenant la référence : les autres études sont comparées à elle, leurs valeurs n'ont pas changé.`);
    }
    function remplacerParPage(e) {
      const plein = { ...copie(f.defaut), ...copie(lirePage()) };
      if (e.id === etat.reference) { etat.base = plein; nettoyerEcarts(); } else e.ecarts = ecartsDe(etat.base, plein);
      sauver();
      rendreListe();
      majSynthese(true);
      dire("succes", `« ${e.nom} » : saisie de la page recopiée.`);
    }
    function figerReference() {
      const e = etudeRef();
      remplacerParPage(e);
      dire("succes", `Référence figée : « ${e.nom} » reprend la saisie de la page. Les variantes gardent leurs écarts.`);
    }
    function retirer(e) {
      const reste = etat.etudes.filter((x) => x.id !== e.id);
      if (!reste.length) return dire("avertissement", "Une comparaison garde au moins son étude de référence. « Nouvelle comparaison » l'efface.");
      const estRef = e.id === etat.reference;
      if (estRef) rebaser(reste[0]);
      etat.etudes = reste;
      ouvertes.delete(e.id);
      sauver();
      rendreListe();
      majSynthese(true);
      dire("succes", estRef ? `« ${e.nom} » retirée ; « ${reste[0].nom} » devient la référence.` : `« ${e.nom} » retirée.`);
    }
    function nouvelle() {
      const faire = () => { creer(); ouvertes.clear(); cache.clear(); rendreTout(); dire("succes", "Nouvelle comparaison : la saisie de la page est la référence."); };
      if (etat.etudes.length > 1) demander(`Effacer la comparaison actuelle (${etat.etudes.length} études) et repartir de la saisie de la page ? Exportez-la d'abord si vous voulez la garder.`, "Effacer et recommencer", faire);
      else faire();
    }

    // ---------- fichiers ----------
    function exporter(e) {
      App.telecharger(`comparaison-${ident}.json`, JSON.stringify(etat, null, 2));
      if (e && e.currentTarget) App.retour(e.currentTarget, true, "Exportée");
    }
    function fichierEntree() {
      const entree = el("input", { type: "file", accept: ".json,application/json", hidden: true });
      entree.addEventListener("change", async () => {
        const fic = entree.files[0];
        entree.value = "";
        if (!fic) return;
        if (fic.size > 2_000_000) return dire("erreur", "Fichier trop gros pour une comparaison MecaStruct.");
        let d;
        try { d = JSON.parse(await fic.text()); } catch (err) { return refuserImport("Ce fichier n'est pas du JSON lisible."); }
        const v = valider(d);
        if (!v.ok) return refuserImport(v.erreur);
        const poser = () => {
          etat = v.donnees; refus = ""; ouvertes.clear(); cache.clear();
          sauver(); rendreTout();
          const autre = v.donnees.outil && v.donnees.outil !== "MecaStruct RdM " + App.VERSION ? ` Écrite avec « ${v.donnees.outil} », recalculée ici avec la version ${App.VERSION}.` : "";
          dire(autre ? "avertissement" : "succes", `${fic.name} : comparaison importée (${etat.etudes.length} étude${etat.etudes.length > 1 ? "s" : ""}).${autre}`);
        };
        if (etat && etat.etudes.length > 1) demander(`Remplacer la comparaison actuelle (${etat.etudes.length} études) par celle de « ${fic.name} » (${v.donnees.etudes.length} études) ? Exportez l'actuelle d'abord si besoin.`, "Remplacer", poser);
        else poser();
      });
      return entree;
    }
    function refuserImport(texte) {
      dire("erreur", texte + (etat ? " La comparaison actuelle n'a pas été modifiée." : ""),
        bouton("Créer une nouvelle comparaison", () => { if (etat && etat.etudes.length > 1) nouvelle(); else { creer(); cache.clear(); rendreTout(); dire("succes", "Nouvelle comparaison créée à partir de la saisie de la page."); } }, "secondaire petit"));
    }

    // ---------- tableau de synthèse ----------
    let minuterieSynthese = null;
    function majSynthese(vite) {
      clearTimeout(minuterieSynthese);
      const lancer = () => { rendreSynthese(); planifier(); };
      if (vite) lancer(); else minuterieSynthese = setTimeout(lancer, 220);
    }

    function colonnes() {
      return etat.etudes.map((e) => { const s = saisieDe(e); return { e, s, r: cache.get(empreinte(s)) || null, ref: e.id === etat.reference }; });
    }

    const verdictCellule = (r) => ({
      ok: { texte: "✓ Conforme", classe: "cmp-v-ok" },
      ko: { texte: "✗ Non conforme", classe: "cmp-v-ko" },
      indic: { texte: "⚠ À vérifier", classe: "cmp-v-indic", aide: "Résultat indicatif : la page n'a pas de critère de conformité pour ce calcul." },
    }[r.verdict]);

    // Une ligne : cellules = [{ texte, num?, classe?, aide?, neutre? }] ; la différence avec la référence est calculée ici.
    function ligneRes(nom, cellules, iRef) {
      const ref = cellules[iRef];
      const lignes = cellules.map((c, i) => {
        const comparable = !c.neutre && !ref.neutre;
        const diff = i !== iRef && comparable && (c.num !== undefined && ref.num !== undefined && c.num !== null && ref.num !== null ? !proches(c.num, ref.num) : c.texte !== ref.texte);
        const delta = diff && typeof c.num === "number" && typeof ref.num === "number" ? ecartRelatif(c.num, ref.num) : null;
        return { ...c, diff, delta };
      });
      return { nom, cellules: lignes, identique: !lignes.some((c) => c.diff) };
    }

    // grandeurs de tous les résultats : la référence d'abord (ses libellés servent de titre de ligne)
    function grandeursCommunes(cols) {
      const cles = [], libelles = new Map(), pieces = new Map();
      const ordre = [...cols.filter((c) => c.ref), ...cols.filter((c) => !c.ref)];
      for (const col of ordre) if (col.r && !col.r.erreur) for (const [k, g] of col.r.grandeurs) if (!libelles.has(k)) { cles.push(k); libelles.set(k, g.nom); pieces.set(k, g.piece); }
      return { cles, libelles, pieces };
    }
    function construire(cols) {
      const iRef = cols.findIndex((c) => c.ref);
      const groupes = [];
      // paramètres qui changent
      const cles = ordreCles.filter((k) => cols.some((c) => k in c.e.ecarts));
      const parametres = cles.length
        ? cles.map((k) => {
          const c = parId.get(k);
          const scal = scalaires.includes(c);
          return { nom: libelleCle(k), identique: false, cellules: cols.map((col) => ({
            texte: scal ? valeurTexte(c, col.s[k]) : (col.ref ? "valeurs de la référence" : k in col.e.ecarts ? "modifié (voir l'étude)" : "identique à la référence"),
            diff: !col.ref && k in col.e.ecarts, delta: scal && typeof col.s[k] === "number" && !col.ref && k in col.e.ecarts ? ecartRelatif(col.s[k], cols[iRef].s[k]) : null })) };
        })
        : [{ nom: "Paramètres modifiés", identique: false, cellules: cols.map((col) => ({ texte: col.ref ? "référence" : "aucun écart avec la référence", diff: false })) }];
      groupes.push({ titre: "Paramètres modifiés", lignes: parametres });

      const sur = (fn) => cols.map((col) => {
        if (!col.r) return { texte: "calcul en cours…", neutre: true };
        if (col.r.erreur) return { texte: "non calculable", neutre: true, classe: "cmp-erreur" };
        return fn(col.r);
      });
      const verdict = cols.map((col) => {
        if (!col.r) return { texte: "calcul en cours…", neutre: true };
        if (col.r.erreur) return { texte: "non calculable : " + col.r.erreur, neutre: true, classe: "cmp-erreur" };
        return verdictCellule(col.r);
      });
      const lignesV = [ligneRes("Verdict", verdict, iRef)];
      lignesV.push(ligneRes("Conclusion du calcul", sur((r) => (r.status ? { texte: App.decimalesFr(r.status) } : { texte: "sans objet : pas de phrase de conclusion", neutre: true })), iRef));
      lignesV.push(ligneRes("Mode dimensionnant", sur((r) => (r.mode ? { texte: r.mode, aide: `Taux de travail : ${nf(100 * r.tauxMax)} %` } : { texte: "sans objet : pas de critère de ruine" })), iRef));
      lignesV.push(ligneRes("Taux de travail maximal (%)", sur((r) => (r.tauxMax !== null ? { texte: nf(100 * r.tauxMax), num: 100 * r.tauxMax } : { texte: "sans objet : pas de critère", neutre: true })), iRef));
      lignesV.push(ligneRes("Coefficient de sécurité minimal s", sur((r) => (r.sMin === null ? { texte: "sans objet : pas de critère", neutre: true }
        : r.sMin === Infinity ? { texte: "∞ (aucune sollicitation)", num: Infinity } : { texte: nf(r.sMin), num: r.sMin, aide: r.sDemande ? `Demandé : ${nf(r.sDemande)}` : undefined })), iRef));
      groupes.push({ titre: "Verdict et sécurité", lignes: lignesV });

      // grandeurs clés du résultat
      const { cles: noms, libelles, pieces } = grandeursCommunes(cols);
      const grandeurs = noms.map((n) => ligneRes(libelles.get(n), cols.map((col) => {
        if (!col.r) return { texte: "calcul en cours…", neutre: true };
        if (col.r.erreur) return { texte: "non calculable", neutre: true, classe: "cmp-erreur" };
        const g = col.r.grandeurs.get(n);
        if (!g) return { texte: "non disponible", neutre: true };
        // même grandeur mais ligne différente d'une étude à l'autre (autre ajustement…) : la ligne est rappelée dans la cellule
        return { texte: g.piece && g.piece !== pieces.get(n) ? `${g.texte} (${g.piece})` : g.texte, num: g.num };
      }), iRef));
      if (grandeurs.length) groupes.push({ titre: "Grandeurs calculées", lignes: grandeurs });
      return groupes;
    }

    function construireTableau(cols) {
      const groupes = construire(cols);
      const n = cols.length + 1;
      const tete = el("tr", {}, el("th", { scope: "col", texte: "Grandeur" }), cols.map((c) => el("th", { scope: "col", class: c.ref ? "cmp-col-ref" : "" },
        el("span", { class: "cmp-nom-col", texte: c.e.nom || "(sans nom)" }), c.ref ? el("span", { class: "cmp-badge", texte: "Référence" }) : null)));
      const corpsT = groupes.map((g) => el("tbody", {},
        el("tr", { class: "cmp-groupe-ligne" }, el("th", { scope: "rowgroup", colspan: String(n), texte: g.titre })),
        g.lignes.map((l) => el("tr", { class: l.identique ? "cmp-identique" : "" }, el("th", { scope: "row", texte: l.nom }),
          l.cellules.map((c) => el("td", { class: [c.classe, c.diff ? "cmp-diff" : "", typeof c.num === "number" ? "num" : ""].filter(Boolean).join(" "), aide: c.aide },
            c.diff ? el("span", { class: "cmp-egal", "aria-hidden": "true", texte: "≠ " }) : null,
            c.diff ? el("span", { class: "cache", texte: "différent de la référence : " }) : null,
            el("span", { texte: c.texte }),
            c.delta ? el("span", { class: "cmp-delta", texte: ` (${c.delta})` }) : null))))));
      const nbPend = cols.filter((c) => !c.r).length;
      const caption = el("caption", { texte: `Synthèse : ${cols.length} étude${cols.length > 1 ? "s" : ""}, référence « ${cols.find((c) => c.ref).e.nom} ». Les cellules marquées « ≠ » diffèrent de la référence.${nbPend ? ` Calcul en cours : ${nbPend} étude${nbPend > 1 ? "s" : ""}.` : ""}` });
      // texte brut pour le tableur
      const tsv = [["Grandeur", ...cols.map((c) => propre(c.e.nom) + (c.ref ? " (référence)" : ""))],
        ...groupes.flatMap((g) => g.lignes.map((l) => [l.nom, ...l.cellules.map((c) => propre(c.texte))]))].map((l) => l.map(propre).join("\t")).join("\n");
      return { element: el("div", { class: "defile cmp-defile", tabindex: "0", role: "region", "aria-label": "Tableau de synthèse (défile horizontalement)" },
        el("table", { class: "cmp-table" }, caption, el("thead", {}, tete), corpsT)), tsv, enAttente: nbPend };
    }

    function rendreSynthese() {
      if (!etat || !zoneTableau || !zoneTableau.isConnected) return;
      const cols = colonnes();
      const t = construireTableau(cols);
      dernierTSV = t.tsv;
      dernierEnAttente = t.enAttente > 0;
      zoneTableau.replaceChildren(t.element);
      zoneTableau.classList.toggle("cmp-masque", cocheMasque.checked && cols.length > 1);
      rendreGraphe(cols);
    }

    // ---------- graphique ----------
    const COULEUR = "#7A68C0", COULEUR_REF = "#E0A030", COULEUR_SEUIL = "#D64550";
    function remplir(select, options, voulu) {
      const cle = JSON.stringify(options);
      if (select._cle !== cle) {
        select.replaceChildren(...options.map((o) => el("option", { value: o.id, texte: o.label })));
        select._cle = cle;
      }
      select.value = options.some((o) => o.id === voulu) ? voulu : (options[0] ? options[0].id : "");
      return select.value;
    }
    const valeurX = (col, id) => {
      if (id === "__etude") return col.e.nom;
      const v = col.s[id], c = parId.get(id);
      return typeof v === "number" ? v : valeurTexte(c, v);
    };
    function valeurY(r, id) {
      if (id === "s") return Number.isFinite(r.sMin) ? r.sMin : null;
      if (id === "taux") return r.tauxMax === null ? null : 100 * r.tauxMax;
      const g = r.grandeurs.get(id.slice(2));
      return g && typeof g.num === "number" ? g.num : null;
    }
    function rendreGraphe(cols) {
      const calculees = cols.filter((c) => c.r && !c.r.erreur);
      const cles = ordreCles.filter((k) => cols.some((c) => k in c.e.ecarts) && scalaires.some((c) => c.id === k));
      const optX = [...cles.map((k) => ({ id: k, label: libelleCle(k) })), { id: "__etude", label: "Étude (nom)" }];
      const optY = [];
      if (calculees.some((c) => c.r.sMin !== null)) optY.push({ id: "s", label: "Coefficient de sécurité minimal s" }, { id: "taux", label: "Taux de travail maximal (%)" });
      const { cles: noms, libelles } = grandeursCommunes(cols);
      for (const n of noms) if (calculees.some((c) => { const g = c.r.grandeurs.get(n); return g && typeof g.num === "number"; })) optY.push({ id: "g:" + n, label: libelles.get(n) });
      const xId = remplir(selX, optX, prefs.x);
      const yId = remplir(selY, optY.length ? optY : [{ id: "", label: "(aucune grandeur numérique)" }], prefs.y);
      if (!yId || !calculees.length) {
        zoneGraphe.replaceChildren();
        zoneDescription.textContent = calculees.length ? "Aucune grandeur numérique à tracer pour ce calcul." : "Graphique indisponible : aucune étude n'est encore calculée.";
        return;
      }
      const xLabel = optX.find((o) => o.id === xId).label, yLabel = optY.find((o) => o.id === yId).label;
      const points = calculees.map((c) => ({ nom: c.e.nom, ref: c.ref, x: valeurX(c, xId), y: valeurY(c.r, yId), seuil: yId === "s" ? c.r.sDemande : yId === "taux" ? 100 : null }))
        .filter((p) => p.y !== null && Number.isFinite(p.y));
      const absentes = cols.filter((c) => !points.some((p) => p.nom === c.e.nom && p.ref === c.ref)).map((c) => c.e.nom);
      if (!points.length) {
        zoneGraphe.replaceChildren();
        zoneDescription.textContent = `« ${yLabel} » n'est pas disponible pour les études calculées : rien à tracer.`;
        return;
      }
      const numerique = points.every((p) => typeof p.x === "number");
      if (numerique) points.sort((a, b) => a.x - b.x);
      const trait = { color: "rgba(128,128,128,.9)", width: 1 };
      const grille = { gridcolor: "rgba(128,128,128,.25)", zerolinecolor: "rgba(128,128,128,.4)", linecolor: "rgba(128,128,128,.6)" };
      const noms2 = points.map((p) => p.nom + (p.ref ? " (réf.)" : ""));
      const data = [numerique
        ? { type: "scatter", mode: "lines+markers", name: yLabel, x: points.map((p) => p.x), y: points.map((p) => p.y), text: noms2, line: { color: COULEUR, width: 2 },
          marker: { color: points.map((p) => (p.ref ? COULEUR_REF : COULEUR)), size: points.map((p) => (p.ref ? 15 : 10)), symbol: points.map((p) => (p.ref ? "diamond" : "circle")), line: trait },
          hovertemplate: "%{text}<br>" + xLabel + " = %{x}<br>" + yLabel + " = %{y}<extra></extra>" }
        : { type: "bar", textposition: "none", name: yLabel, x: points.map((p) => (xId === "__etude" ? noms2[points.indexOf(p)] : String(p.x))), y: points.map((p) => p.y), text: noms2,
          marker: { color: points.map((p) => (p.ref ? COULEUR_REF : COULEUR)), line: { color: "rgba(128,128,128,.9)", width: points.map((p) => (p.ref ? 3 : 0)) }, pattern: { shape: points.map((p) => (p.ref ? "/" : "")) } },
          hovertemplate: "%{text}<br>" + yLabel + " = %{y}<extra></extra>" }];
      const avecSeuil = points.some((p) => p.seuil !== null && p.seuil !== undefined);
      const seuils = [...new Set(points.map((p) => p.seuil).filter((x) => x !== null && x !== undefined))];
      if (avecSeuil) {
        const nomSeuil = yId === "s" ? "Seuil de conformité (s demandé)" : "Seuil de conformité (taux = 100 %)";
        data.push({ type: "scatter", mode: "lines", name: nomSeuil, x: data[0].x, y: points.map((p) => p.seuil ?? seuils[0]), line: { color: COULEUR_SEUIL, width: 2, dash: "dash" }, hoverinfo: "y+name" });
      }
      const layout = { height: 340, margin: { l: 64, r: 16, t: 14, b: 56 }, showlegend: true, legend: { orientation: "h", y: -0.28 },
        xaxis: { title: { text: xLabel }, type: numerique ? "linear" : "category", ...grille }, yaxis: { title: { text: yLabel }, ...grille } };
      zoneGraphe.replaceChildren(App.figure({ data, layout }));
      const fx = (x) => (typeof x === "number" ? nf(x, 4) : String(x));
      zoneDescription.textContent = `Graphique ${numerique ? "en courbe" : "en barres"} : ${yLabel} selon ${xLabel}. ${points.length} point${points.length > 1 ? "s" : ""} : `
        + points.map((p) => `${p.nom}${p.ref ? " (référence)" : ""}, ${xId === "__etude" ? "" : xLabel + " = " + fx(p.x) + ", "}${yLabel} = ${nf(p.y, 4)}`).join(" ; ") + "."
        + (numerique ? " La référence est le losange." : " La référence est la barre hachurée.")
        + (avecSeuil ? ` Seuil de conformité : ${yId === "s" ? "s demandé = " + seuils.map((x) => nf(x)).join(" ou ") : "taux de travail = 100 %"} (en dessous, l'étude ne respecte pas le critère).` : "")
        + (absentes.length ? ` Non représentée${absentes.length > 1 ? "s" : ""} (non calculable ou grandeur absente) : ${absentes.join(", ")}.` : "");
    }

    // ---------- copie et impression ----------
    async function copierSynthese(e) {
      const bouton_ = e.currentTarget;
      if (dernierEnAttente) return dire("avertissement", "Des calculs sont encore en cours : réessayez dans un instant.");
      const ok = await App.copier(dernierTSV);
      App.confirmer(bouton_, ok, "Synthèse copiée", "Copie impossible", "Synthèse copiée : à coller dans Excel.");
    }
    async function imprimer(e) {
      const b = e.currentTarget;
      if (dernierEnAttente) return dire("avertissement", "Des calculs sont encore en cours : réessayez dans un instant.");
      b.disabled = true;
      let image = null;
      const gd = zoneGraphe && zoneGraphe.querySelector(".js-plotly-plot");
      if (gd && gd._figure && window.Plotly) { // version claire du graphique, quelle que soit le thème affiché
        try {
          const fig = copie(gd._figure);
          const url = await Plotly.toImage({ data: fig.data, layout: { ...fig.layout, paper_bgcolor: "#fff", plot_bgcolor: "#fff", font: { color: "#000" }, width: 900, height: 360 } }, { format: "png", scale: 2 });
          image = el("img", { src: url, alt: zoneDescription.textContent, class: "cmp-image-impression" });
        } catch (err) { image = null; }
      }
      const tableau = zoneTableau.firstElementChild.cloneNode(true);
      tableau.querySelectorAll(".cmp-ecran").forEach((x) => x.remove());
      tableau.removeAttribute("tabindex");
      const zone = el("div", { id: "cmp-impression" },
        el("h1", { texte: `Comparaison d'études : ${App.pageCourante() ? App.pageCourante().titre + " · " : ""}${titreCalcul}` }),
        el("p", { class: "legende", texte: `Référence : « ${etudeRef().nom} » · ${etat.etudes.length} études · MecaStruct RdM ${App.VERSION} · ${new Date().toLocaleDateString("fr-FR")}` }),
        tableau, image, el("p", { class: "legende", texte: zoneDescription.textContent }),
        el("p", { class: "legende", texte: "Outil d'aide au pré-dimensionnement : résultats à vérifier." }));
      tableau.classList.toggle("cmp-masque", zoneTableau.classList.contains("cmp-masque"));
      document.body.append(zone);
      document.body.classList.add("cmp-imprime");
      const fin = () => { document.body.classList.remove("cmp-imprime"); zone.remove(); b.disabled = false; window.removeEventListener("afterprint", fin); };
      window.addEventListener("afterprint", fin);
      try { window.print(); } finally { setTimeout(fin, 1500); }
    }

    // ---------- ouverture ----------
    details.addEventListener("toggle", () => {
      if (!details.open) { jeton++; return; }
      rendreTout();
    });
    // la saisie de la page change : l'écart avec la référence est remis à jour
    let minuterieEtat = null;
    bloc.addEventListener("input", (ev) => { if (!section.contains(ev.target)) { clearTimeout(minuterieEtat); minuterieEtat = setTimeout(majEtatPage, 300); } });
    bloc.addEventListener("change", (ev) => { if (!section.contains(ev.target)) { clearTimeout(minuterieEtat); minuterieEtat = setTimeout(majEtatPage, 300); } });
    // redimensionnement des figures après l'ouverture ou un changement de thème
    document.addEventListener("themechange", () => { if (details.open && etat && section.isConnected) rendreSynthese(); });

    const ouvrir = () => {
      if (!details.open) details.open = true;
      else if (!zoneContenu.hasChildNodes()) rendreTout();
      section.scrollIntoView({ block: "start", behavior: sansMouvement() ? "auto" : "smooth" });
      resume.focus({ preventScroll: true });
    };
    return {
      ouvrir,
      // bouton « Comparer des études » à placer près des exports (recréé à chaque résultat)
      bouton: () => el("button", { type: "button", class: "secondaire", texte: "Comparer des études", "aria-controls": "cmp-" + ident,
        aide: "Garde l'étude actuelle comme référence et compare des variantes (un autre diamètre, un autre matériau…) : verdict, coefficient de sécurité, graphique.", onclick: ouvrir }),
    };
  }

  App.comparer = { monter };
})();
