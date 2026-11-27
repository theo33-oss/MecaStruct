"use strict";
// Parcours et études : pages récentes, favoris, copies de saisie, export et import. Tout reste dans ce navigateur (App.memoire) :
// rien n'est envoyé sur Internet, et ouvrir une page depuis ici ne change aucune donnée et ne lance aucun calcul.
//
// Clés App.memoire utilisées (en plus des « saisie.<calcul> » que les pages écrivent déjà) :
//   recents  : [{ id: "<page>", t: <ms> }]            5 dernières pages de calcul visitées, la plus récente d'abord
//   favoris  : [{ id: "<page>", t: <ms> }]            pages marquées d'une étoile
//   etudes   : [{ id, nom, page, calcul, cree, saisie }]   copies de saisie nommées (« Dupliquer »), 30 au plus
// Fichier d'export : { format: "mecastruct-etudes", version: 1, schema_version: 1, outil, exporte, favoris, recents, copies, saisies: { "<calcul>": saisie } }
// (« saisies » = toutes les saisie.<calcul> gardées dans ce navigateur).

(() => {
  const { el } = App;
  const FORMAT = "mecastruct-etudes";
  const SCHEMA_VERSION = 1; // numéro de format de l'export (« schema_version ») ; même valeur que mecastruct.SCHEMA_VERSION
  const MAX_RECENTS = 5, MAX_COPIES = 30, MAX_FAVORIS = 30, MAX_SAISIES = 60;
  const IDENT = /^[A-Za-z0-9_]{1,40}$/;
  const objet = (x) => !!x && typeof x === "object" && !Array.isArray(x);
  const copie = (x) => JSON.parse(JSON.stringify(x));

  // ---------- données ----------

  const lireListe = (cle) => { const l = App.memoire.lire(cle, []); return Array.isArray(l) ? l : []; };
  const pageCalcul = (id) => { const p = typeof id === "string" ? App.page(id) : null; return p && p.genre === "machine" ? p : null; };
  const pageFavorite = (id) => { const p = typeof id === "string" ? App.page(id) : null; return p && p.famille && p.genre !== "bureau" ? p : null; };
  const avecDate = (r) => objet(r) && Number.isFinite(r.t);
  const recents = () => lireListe("recents").filter((r) => avecDate(r) && pageCalcul(r.id)).slice(0, MAX_RECENTS);
  const favoris = () => lireListe("favoris").filter((r) => avecDate(r) && pageFavorite(r.id));
  const copieValide = (c) => objet(c) && typeof c.id === "string" && typeof c.nom === "string" && pageCalcul(c.page) && IDENT.test(String(c.calcul)) && objet(c.saisie);
  const copies = () => lireListe("etudes").filter(copieValide);
  const estFavori = (id) => favoris().some((f) => f.id === id);

  function noterVisite(p) {
    App.memoire.ecrire("recents", [{ id: p.id, t: Date.now() }, ...recents().filter((r) => r.id !== p.id)].slice(0, MAX_RECENTS));
  }

  // Calcul affiché d'une page : son onglet actif s'il en a plusieurs.
  function identActif(p) {
    const g = App.memoire.lire("onglet.page." + p.id, "");
    return p.calculs.includes(g) ? g : p.calculs[0];
  }

  let cacheFormulaires = null;
  function formulaires() {
    if (!cacheFormulaires && App.pret) { const r = App.calculer("formulaires"); if (r.ok) cacheFormulaires = r.sortie; }
    return cacheFormulaires;
  }

  const affiche = (v) => (typeof v === "number" ? App.exposants(App.fr(String(Number(v.toPrecision(4))))) : App.fr(v ?? ""));

  // Deux ou trois valeurs de la saisie gardée (celles que l'on a changées d'abord) : « Longueur L 8 m · Diamètre nominal 100 mm ».
  // Seulement si une saisie est gardée et si le calcul est chargé (les noms des champs viennent des formulaires du calcul).
  function resume(p) {
    const ident = identActif(p);
    const brut = App.memoire.lire("saisie." + ident, null);
    const tous = formulaires();
    const f = tous && tous[ident];
    if (!objet(brut) || !f) return "";
    const lignes = f.groupes.flatMap((g) => g.champs).filter((c) => c.id in f.defaut && (c.type === "nombre" || c.type === "liste" || c.type === undefined))
      .filter((c) => [].concat(c.si || []).every((k) => k.valeurs.includes(k.id in brut ? brut[k.id] : f.defaut[k.id])))
      .map((c) => { const v = c.id in brut ? brut[c.id] : f.defaut[c.id]; return { c, v, change: JSON.stringify(v) !== JSON.stringify(f.defaut[c.id]) }; })
      .filter(({ c, v }) => (c.type === "liste" ? (typeof v === "string" || typeof v === "number") && String(v).length <= 14 : typeof v === "number" && Number.isFinite(v)) && String(c.libelle).length > 2 && String(c.libelle).length <= 24);
    const choix = [...lignes.filter((x) => x.change), ...lignes.filter((x) => !x.change && x.c.type !== "liste")].slice(0, 3);
    return choix.map(({ c, v }) => `${c.libelle} ${affiche(v)}${c.unite ? " " + c.unite : ""}`).join(" · ");
  }

  function relatif(t) {
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return "à l'instant";
    if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
    if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
    const j = Math.floor(s / 86400);
    if (j === 1) return "hier";
    if (j < 30) return `il y a ${j} jours`;
    return new Date(t).toLocaleDateString("fr-FR");
  }
  const dateComplete = (t) => new Date(t).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" });
  const identifiant = () => "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

  // ---------- étoile « Ajouter aux favoris » près du titre de chaque page ----------

  function etoile(p, contenu) {
    const h1 = contenu.querySelector("h1");
    if (!h1 || h1.closest(".titre-page")) return;
    const etoileTexte = el("span", { "aria-hidden": "true", class: "favori-etoile" });
    const b = el("button", { type: "button", class: "favori secondaire", "aria-pressed": "false", "aria-label": "Ajouter aux favoris" }, etoileTexte, el("span", { class: "favori-texte", "aria-hidden": "true", texte: "Favori" }));
    const maj = () => { const oui = estFavori(p.id); b.setAttribute("aria-pressed", String(oui)); etoileTexte.textContent = oui ? "★" : "☆"; b.title = oui ? "Retirer des favoris" : "Ajouter aux favoris"; };
    b.addEventListener("click", () => {
      if (estFavori(p.id)) {
        App.memoire.ecrire("favoris", favoris().filter((f) => f.id !== p.id));
        App.toast("Retiré des favoris : " + p.titre);
      } else {
        App.memoire.ecrire("favoris", [{ id: p.id, t: Date.now() }, ...favoris()].slice(0, MAX_FAVORIS));
        App.toast("Ajouté aux favoris : " + p.titre + " (visible sur l'accueil, dans « Mes études »)");
      }
      maj();
    });
    maj();
    const bloc = el("div", { class: "titre-page" });
    h1.replaceWith(bloc);
    bloc.append(h1, b);
  }

  // ---------- section « Mes études » de l'accueil ----------

  let courante = null; // { corps, rafraichir } de la section affichée

  function sectionAccueil(contenu) {
    const cartes = contenu.querySelector(".cartes");
    if (!cartes) return;
    const corps = el("div", { class: "etudes-corps" });
    const resumeTitre = el("summary", {}, el("h2", { texte: "Mes études" }));
    // repliée à l'arrivée, comme les autres cartes de l'accueil (js/accueil.js) ; un clic dedans la garde ouverte
    const details = el("details", { class: "repli repli-accueil etudes" }, resumeTitre, corps);
    const section = el("section", { class: "mes-etudes", "aria-label": "Mes études" }, details);
    App.repliAuSurvol(section, details, resumeTitre, { epingleDedans: true });
    const rafraichir = (focus, niveau, texte) => {
      corps.replaceChildren(...construire(rafraichir));
      if (texte) corps.querySelector(".etudes-msg").replaceChildren(App.message(niveau, texte));
      const cible = focus && (corps.querySelector(`[data-bloc="${focus}"]`) || corps.querySelector('[data-bloc="debut"]'));
      if (cible) cible.focus();
    };
    rafraichir();
    courante = { corps, rafraichir };
    cartes.before(section);
  }

  // Une ligne : lien vers la page (ouvre la page telle quelle), repère de date, résumé, actions.
  function ligne(p, { quand, actions }) {
    const famille = App.FAMILLES.find((f) => f.id === p.famille);
    const t = resume(p);
    return el("li", { class: "etude" },
      el("div", { class: "etude-tete" },
        el("a", { href: "#/" + p.id, texte: p.titre }),
        el("span", { class: "legende" }, famille ? famille.titre : "", famille && quand ? " · " : "", quand || "")),
      t ? el("p", { class: "legende etude-resume", texte: t }) : null,
      el("div", { class: "ligne etude-actions" }, actions));
  }

  function construire(rafraichir) {
    const msg = el("div", { class: "etudes-msg", "aria-live": "polite" });
    const dire = (niveau, texte) => msg.replaceChildren(App.message(niveau, texte));
    const demander = (texte, libelle, fn) => msg.replaceChildren(el("p", { class: "message avertissement", role: "status" }, texte, " ",
      el("button", { type: "button", class: "primaire petit", texte: libelle, onclick: () => { msg.replaceChildren(); fn(); } }), " ",
      el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: () => msg.replaceChildren() })));

    const rec = recents(), fav = favoris(), cop = copies();
    const sorties = [];
    sorties.push(el("p", { class: "legende", tabindex: "-1", "data-bloc": "debut", texte: "Conservé uniquement dans ce navigateur (rien n'est envoyé sur Internet). Ouvrir une page d'ici ne modifie aucune donnée et ne lance aucun calcul." }));
    if (!rec.length && !fav.length && !cop.length) {
      sorties.push(el("p", { texte: "Vos cinq dernières pages de calcul et vos favoris apparaîtront ici. Pour ajouter un favori, utilisez l'étoile « Favori » à côté du titre d'une page." }));
    }

    // duplication : un petit formulaire sous la ligne, qui garde la saisie courante du calcul sous un nom
    const dupliquer = (p, li) => {
      const ancien = li.querySelector(".etude-dup");
      if (ancien) { ancien.querySelector("input").focus(); return; }
      const ident = identActif(p);
      const champ = el("input", { type: "text", value: p.titre + " (copie)", maxlength: "60", "aria-label": "Nom de la copie" });
      const form = el("form", { class: "etude-dup ligne" }, el("label", {}, "Nom de la copie ", champ),
        el("button", { type: "submit", class: "primaire petit", texte: "Enregistrer la copie" }),
        el("button", { type: "button", class: "secondaire petit", texte: "Annuler", onclick: () => form.remove() }));
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const nom = champ.value.trim().replace(/\s+/g, " ").slice(0, 60);
        if (!nom) return dire("avertissement", "Donnez un nom à la copie.");
        if (copies().length >= MAX_COPIES) return dire("avertissement", `Au plus ${MAX_COPIES} copies : supprimez-en une d'abord.`);
        const saisie = copie(App.lireSaisie(ident));
        App.memoire.ecrire("etudes", [{ id: identifiant(), nom, page: p.id, calcul: ident, cree: new Date().toISOString(), saisie }, ...copies()]);
        App.toast("Copie enregistrée : " + nom);
        rafraichir("copies");
      });
      li.append(form);
      champ.focus();
      champ.select();
    };
    const boutonDupliquer = (p) => {
      const b = el("button", { type: "button", class: "secondaire petit", texte: "Dupliquer", "aria-label": "Dupliquer l'étude " + p.titre,
        title: App.pret ? "Garde une copie de la saisie actuelle sous un nom" : "Disponible quand le calcul est chargé" });
      b.disabled = !App.pret;
      b.addEventListener("click", () => dupliquer(p, b.closest("li")));
      return b;
    };

    if (fav.length) {
      sorties.push(el("h3", { class: "titre-mineur", tabindex: "-1", "data-bloc": "favoris", texte: "Favoris" }),
        el("ul", { class: "etudes-liste" }, fav.map((f) => {
          const p = pageFavorite(f.id);
          return ligne(p, { quand: "ajouté " + relatif(f.t), actions: [
            pageCalcul(p.id) ? boutonDupliquer(p) : null,
            el("button", { type: "button", class: "secondaire petit", texte: "Retirer", "aria-label": "Retirer " + p.titre + " des favoris", onclick: () => {
              App.memoire.ecrire("favoris", favoris().filter((x) => x.id !== p.id));
              rafraichir("favoris");
              App.toast("Retiré des favoris : " + p.titre);
            } })] });
        })));
    }

    if (rec.length) {
      sorties.push(el("h3", { class: "titre-mineur", tabindex: "-1", "data-bloc": "recents", texte: "Récemment utilisés" }),
        el("ul", { class: "etudes-liste" }, rec.map((r) => {
          const p = pageCalcul(r.id);
          const quand = el("time", { datetime: new Date(r.t).toISOString(), title: dateComplete(r.t), texte: relatif(r.t) });
          return ligne(p, { quand, actions: [boutonDupliquer(p)] });
        })),
        el("p", { class: "ligne" }, el("button", { type: "button", class: "secondaire petit", texte: "Vider l'historique", onclick: () => {
          App.memoire.ecrire("recents", []);
          rafraichir("debut");
          App.toast("Historique vidé (les favoris et les copies sont conservés)");
        } })));
    }

    if (cop.length) {
      sorties.push(el("h3", { class: "titre-mineur", tabindex: "-1", "data-bloc": "copies", texte: "Copies enregistrées" }),
        el("ul", { class: "etudes-liste" }, cop.map((c) => {
          const p = pageCalcul(c.page);
          const ouvrir = () => {
            App.memoire.ecrire("saisie." + c.calcul, copie(c.saisie));
            if (p.calculs.includes(c.calcul)) App.memoire.ecrire("onglet.page." + p.id, c.calcul);
            location.hash = "#/" + p.id;
          };
          return el("li", { class: "etude" },
            el("div", { class: "etude-tete" }, el("strong", { texte: c.nom }), el("span", { class: "legende", texte: p.titre + " · enregistrée " + relatif(Date.parse(c.cree) || 0) })),
            el("div", { class: "ligne etude-actions" },
              el("button", { type: "button", class: "secondaire petit", texte: "Ouvrir", "aria-label": "Ouvrir la copie " + c.nom, onclick: () => {
                const actuelle = App.memoire.lire("saisie." + c.calcul, null);
                if (!objet(actuelle)) return ouvrir();
                demander(`Remplacer la saisie actuelle de « ${p.titre} » par la copie « ${c.nom} » ? La saisie actuelle sera perdue ; dupliquez-la d'abord pour la garder.`, "Remplacer et ouvrir", ouvrir);
              } }),
              el("button", { type: "button", class: "secondaire petit", texte: "Supprimer", "aria-label": "Supprimer la copie " + c.nom, onclick: () => demander(`Supprimer la copie « ${c.nom} » ?`, "Supprimer", () => {
                App.memoire.ecrire("etudes", copies().filter((x) => x.id !== c.id));
                rafraichir("copies");
                App.toast("Copie supprimée : " + c.nom);
              }) })));
        })));
    }

    // export et import de toutes les études
    const entree = el("input", { type: "file", accept: ".json,application/json", hidden: true });
    entree.addEventListener("change", async () => {
      const fic = entree.files[0];
      entree.value = "";
      if (!fic) return;
      if (fic.size > 3_000_000) return dire("erreur", "Fichier trop gros pour un export d'études MecaStruct.");
      let texte;
      try { texte = await fic.text(); } catch (e) { return dire("erreur", "Le fichier n'a pas pu être lu."); }
      const v = lireImport(texte);
      if (!v.ok) return dire("erreur", v.erreur + " Rien n'a été importé.");
      const d = v.donnees;
      demander(`Importer « ${fic.name} » : ${d.favoris.length} favori(s), ${d.copies.length} copie(s) et ${d.saisies.length} saisie(s) de calcul. Les favoris et les copies s'ajoutent aux vôtres ; les saisies du fichier remplacent celles de ce navigateur pour les mêmes calculs.`,
        "Importer", () => { appliquerImport(d); rafraichir("debut", "succes", `Études importées depuis « ${fic.name} ».`); App.toast("Études importées"); });
    });
    sorties.push(el("div", { class: "etudes-fichiers" },
      el("h3", { class: "titre-mineur", texte: "Sauvegarder ou changer d'appareil" }),
      el("p", { class: "legende", texte: "Vos études sont conservées uniquement dans ce navigateur : le fichier JSON exporté est le seul moyen de les garder ailleurs ou de les retrouver si le navigateur efface ses données." }),
      el("p", { class: "ligne" },
        el("button", { type: "button", class: "secondaire petit", texte: "Exporter mes études (JSON)", onclick: () => App.telecharger("mecastruct-etudes.json", JSON.stringify(exporter(), null, 2)) }),
        el("button", { type: "button", class: "secondaire petit", texte: "Importer un fichier d'études", onclick: () => entree.click() }), entree)));
    sorties.push(msg);
    return sorties;
  }

  // ---------- export et import ----------

  function toutesLesSaisies() {
    const r = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const cle = localStorage.key(i);
        if (cle && cle.startsWith("mecastruct.saisie.")) {
          const ident = cle.slice("mecastruct.saisie.".length);
          const v = App.memoire.lire("saisie." + ident, null);
          if (IDENT.test(ident) && objet(v)) r.push([ident, v]);
        }
      }
    } catch (e) { /* stockage bloqué : rien à exporter */ }
    return r;
  }

  function exporter() {
    return { format: FORMAT, version: 1, schema_version: SCHEMA_VERSION, outil: "MecaStruct RdM " + App.VERSION, exporte: new Date().toISOString(),
      favoris: favoris(), recents: recents(), copies: copies(), saisies: Object.fromEntries(toutesLesSaisies()) };
  }

  // Contrôle d'un fichier d'export : format, types, tailles. Les saisies sont gardées en liste de paires (pas d'objet à clés libres).
  function lireImport(texte) {
    let d;
    try { d = JSON.parse(texte); } catch (e) { return { ok: false, erreur: "Ce fichier n'est pas du JSON valide." }; }
    if (!objet(d) || d.format !== FORMAT) return { ok: false, erreur: "Ce fichier n'est pas un export d'études MecaStruct." };
    if (d.version !== 1) return { ok: false, erreur: "Ce fichier vient d'une autre version du format (" + String(d.version).slice(0, 10) + ")." };
    // « schema_version » absent : version 1 (anciens fichiers) ; clés inconnues : ignorées ; format plus récent : refusé
    const sv = d.schema_version === undefined ? 1 : d.schema_version;
    if (!Number.isInteger(sv) || sv < 1) return { ok: false, erreur: "Ce fichier a un numéro de format illisible : il ne s'ouvre pas ici." };
    if (sv > SCHEMA_VERSION) {
      const par = typeof d.outil === "string" && d.outil.trim() ? " (écrit par " + d.outil.slice(0, 60) + ")" : "";
      return { ok: false, erreur: "Ce fichier vient d'une version plus récente de MecaStruct" + par + " : format " + sv + ", alors que cette version lit jusqu'au format "
        + SCHEMA_VERSION + ". Mettez l'application à jour pour l'ouvrir." };
    }
    const liste = (x) => (Array.isArray(x) ? x : []);
    const fav = liste(d.favoris).filter((r) => avecDate(r) && pageFavorite(r.id)).map((r) => ({ id: r.id, t: r.t }));
    const rec = liste(d.recents).filter((r) => avecDate(r) && pageCalcul(r.id)).map((r) => ({ id: r.id, t: r.t }));
    const cop = liste(d.copies).filter((c) => copieValide(c) && /^[\w-]{1,40}$/.test(c.id) && JSON.stringify(c.saisie).length <= 100000)
      .map((c) => ({ id: c.id, nom: c.nom.trim().replace(/\s+/g, " ").slice(0, 60) || "Copie", page: c.page, calcul: c.calcul, cree: typeof c.cree === "string" ? c.cree.slice(0, 40) : "", saisie: c.saisie }));
    const sai = objet(d.saisies) ? Object.entries(d.saisies).filter(([k, v]) => IDENT.test(k) && k !== "__proto__" && objet(v) && JSON.stringify(v).length <= 100000) : [];
    if (sai.length > MAX_SAISIES) return { ok: false, erreur: "Trop de saisies dans ce fichier (" + sai.length + ")." };
    if (!fav.length && !cop.length && !sai.length && !rec.length) return { ok: false, erreur: "Ce fichier ne contient aucune étude." };
    return { ok: true, donnees: { favoris: fav, recents: rec, copies: cop, saisies: sai } };
  }

  function appliquerImport(d) {
    const parId = (a, b) => { const m = new Map(); for (const x of [...a, ...b]) if (!m.has(x.id) || m.get(x.id).t < x.t) m.set(x.id, x); return [...m.values()].sort((x, y) => y.t - x.t); };
    App.memoire.ecrire("favoris", parId(favoris(), d.favoris).slice(0, MAX_FAVORIS));
    App.memoire.ecrire("recents", parId(recents(), d.recents).slice(0, MAX_RECENTS));
    const dejaLa = new Set(copies().map((c) => c.id));
    App.memoire.ecrire("etudes", [...copies(), ...d.copies.filter((c) => !dejaLa.has(c.id))].slice(0, MAX_COPIES));
    for (const [ident, saisie] of d.saisies) App.memoire.ecrire("saisie." + ident, saisie);
  }

  // ---------- pied de page : « Utilisable hors ligne » quand le service worker est actif ----------

  // « ready » ne se résout que si un service worker est enregistré ; la mention n'apparaît que si cette page est déjà servie par lui
  // (à la première visite il vient d'être installé : la copie n'existe pas encore, on ne promet rien).
  function horsLigne() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.ready.then(() => {
      const m = App.$("hors-ligne");
      if (m && navigator.serviceWorker.controller) m.hidden = false;
    }).catch(() => { /* pas de service worker : rien à dire */ });
  }

  // ---------- branchements ----------

  document.addEventListener("mecastruct:page", (e) => {
    const { page: p, contenu } = e.detail;
    if (pageCalcul(p.id)) noterVisite(p);
    if (pageFavorite(p.id)) etoile(p, contenu);
    if (p.id === "accueil") sectionAccueil(contenu);
  });
  // le calcul vient d'être chargé : les résumés (noms des champs) et le bouton « Dupliquer » deviennent disponibles
  document.addEventListener("mecastruct:pret", () => { if (courante && courante.corps.isConnected) courante.rafraichir(); });
  horsLigne();
  App.etudes = { recents, favoris, copies, resume, exporter, lireImport };
})();
