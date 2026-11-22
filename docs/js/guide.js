"use strict";
// Mode guidé des pages de calcul : un parcours volontaire qui désigne, case après case, ce qu'il faut remplir.
// Les étapes sont déduites du formulaire de la page (champs réellement affichés, ordre des groupes), puis le bouton
// « Calculer » (pages non automatiques) et le verdict. Le guide ne modifie jamais les données : il observe seulement
// la page (événements du formulaire) et surligne l'élément visé. Aucune avance automatique : « Suivant » s'active
// quand l'action annoncée est faite ; « Passer cette étape » et « Précédent » sont toujours là.
//
// Mémoire : « guide.masque » (App.memoire) = ne plus proposer ; « guide.propose » = la proposition a déjà été faite ;
// l'étape d'un parcours interrompu est dans sessionStorage (« mecastruct.guide.etape.<page> »), propre à l'onglet.

(() => {
  const { el } = App;
  const MAX_ETAPES = 8;
  const PAR_GROUPE = 3; // première passe : au plus 3 champs par groupe, pour couvrir toute la page
  const TYPES_SAISIE = [undefined, "nombre", "liste", "liste-fixe"]; // nombres et listes
  let actif = null; // parcours en cours : { arreter(effacer) }

  const session = {
    cle: (ident) => "mecastruct.guide.etape." + ident,
    lire(ident) {
      try { const v = sessionStorage.getItem(this.cle(ident)); const n = v === null ? NaN : Number(v); return Number.isInteger(n) && n >= 0 ? n : null; } catch (e) { return null; }
    },
    ecrire(ident, n) { try { sessionStorage.setItem(this.cle(ident), String(n)); } catch (e) { /* sans mémoire */ } },
    oublier(ident) { try { sessionStorage.removeItem(this.cle(ident)); } catch (e) { /* sans mémoire */ } },
  };

  const nombreTexte = (v) => (typeof v === "number" && Number.isFinite(v) ? App.fr(Number(v.toPrecision(10))) : String(v ?? ""));
  const sansMouvement = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const estListe = (c) => c.type === "liste" || c.type === "liste-fixe";
  // Groupes de tableaux sans champ numérique ni liste, que le générateur d'étapes ne couvre pas : une étape « groupe » les
  // ouvre et les explique, sans rien exiger (calcul → titre du groupe → phrase). Un groupe absent d'ici n'a pas d'étape.
  const GROUPES = {
    beam: { "Appuis et charges": "Appuis : où la poutre repose ; charges : forces à appliquer." },
    ossature: {
      "Nœuds et pièces": "Nœuds : les points de la structure ; pièces : les barres qui relient deux nœuds.",
      "Charges (repère global)": "Charges : forces et moments appliqués aux nœuds, ou répartis sur les pièces, dans le repère global.",
    },
  };

  function monter(ident, f, bloc, opts = {}) {
    const formulaire = opts.formulaire;
    const resultat = opts.resultat;
    const lireSaisie = typeof opts.saisie === "function" ? opts.saisie : () => ({});
    const auto = opts.auto !== false;
    if (!formulaire || !resultat) return;

    const bouton = el("button", { type: "button", class: "secondaire petit guide-bouton", "aria-pressed": "false", texte: "Mode guidé",
      aide: "Un guide pas à pas désigne les cases à remplir, avec un exemple et l'effet de chaque réglage. Il ne modifie rien et se quitte à tout moment (Échap)." });
    const barre = el("div", { class: "guide-barre" }, bouton);
    bloc.prepend(barre);

    // ---------- proposition discrète ----------
    const masque = () => App.memoire.lire("guide.masque", false) === true;
    function bandeau(reprise) {
      const retirer = () => bandeauEl && bandeauEl.remove();
      const boutons = reprise !== null
        ? [el("button", { type: "button", class: "secondaire petit", texte: "Reprendre le guide", onclick: () => { retirer(); demarrer(reprise); } }),
          el("button", { type: "button", class: "secondaire petit", texte: "Abandonner", onclick: () => { session.oublier(ident); retirer(); } })]
        : [el("button", { type: "button", class: "secondaire petit", texte: "Démarrer le guide", onclick: () => { App.memoire.ecrire("guide.propose", true); retirer(); demarrer(0); } }),
          el("button", { type: "button", class: "secondaire petit", texte: "Ne plus proposer", onclick: () => { App.memoire.ecrire("guide.masque", true); retirer(); } })];
      const bandeauEl = el("div", { class: "guide-bandeau", role: "region", "aria-label": "Proposition du mode guidé" },
        el("span", { texte: reprise !== null ? `Un guide était en cours (étape ${reprise + 1}).` : "Première fois sur cette page ? Le mode guidé vous montre, case par case, quoi saisir et ce qui change." }),
        el("span", { class: "guide-bandeau-boutons" }, boutons));
      return bandeauEl;
    }
    const reprise = session.lire(ident);
    if (reprise !== null) barre.append(bandeau(reprise));
    else if (!masque() && App.memoire.lire("guide.propose", false) !== true) {
      barre.append(bandeau(null));
      // « une seule fois » : retenu quand la proposition est restée affichée quelques secondes (la page peut être redessinée
      // juste après son arrivée, et la proposition ne doit pas disparaître sans avoir été vue)
      setTimeout(() => { if (barre.isConnected) App.memoire.ecrire("guide.propose", true); }, 4000);
    }
    bouton.addEventListener("click", () => { if (actif && actif.bouton === bouton) actif.arreter(true, true); else demarrer(0); });

    // ---------- étapes déduites du formulaire ----------
    const chercheChamp = (c) => formulaire.querySelector(`[data-id="${CSS.escape(c.id)}"]`);
    const cibleGroupe = (titre) => [...formulaire.querySelectorAll("details.groupe")].find((d) => d.dataset.titre === titre) || null;
    function construireEtapes() {
      const champs = [];
      const groupes = []; // étapes « groupe », chacune avant le champ de rang `apres` de la liste `champs` (l'ordre de la page)
      for (const g of f.groupes || []) {
        let rang = 0;
        for (const c of g.champs || []) {
          if (!TYPES_SAISIE.includes(c.type) || !chercheChamp(c)) continue; // non affiché (condition « si ») : pas d'étape
          champs.push({ genre: "champ", c, rang: rang++ });
        }
        const note = (GROUPES[ident] || {})[g.titre];
        if (note && cibleGroupe(g.titre)) groupes.push({ genre: "groupe", g, note, apres: champs.length });
      }
      const places = MAX_ETAPES - 1 - (auto ? 0 : 1);
      const premiers = champs.filter((x) => x.rang < PAR_GROUPE);
      const choisis = new Set(premiers.slice(0, places));
      for (const x of champs) if (choisis.size < places) choisis.add(x);
      const liste = [];
      champs.forEach((x, i) => {
        for (const e of groupes) if (e.apres === i) liste.push(e);
        if (choisis.has(x)) liste.push(x);
      });
      for (const e of groupes) if (e.apres >= champs.length) liste.push(e);
      if (!auto) liste.push({ genre: "calcul" });
      liste.push({ genre: "verdict" });
      return liste;
    }

    // élément visé par une étape (jamais gardé : le formulaire est redessiné quand un champ en commande un autre)
    function cible(e) {
      let x = null;
      if (e.genre === "champ") { const i = chercheChamp(e.c); x = i ? (i.closest("label") || i) : null; }
      else if (e.genre === "groupe") x = cibleGroupe(e.g.titre);
      else if (e.genre === "calcul") x = [formulaire.querySelector('.actions-saisie button[type="submit"]'), bloc.querySelector(".actions-schema button")].find((b) => b && b.getClientRects().length) // celui des deux qui est visible (CSS : un seul « Calculer » à la fois)
          || formulaire.querySelector('.actions-saisie button[type="submit"]') || bloc.querySelector(".actions-schema button");
      else x = resultat.querySelector(".bilan, .verdict") || resultat;
      return x && x.isConnected ? x : null;
    }
    const ouvrirParents = (x) => { for (let d = x.parentElement && x.parentElement.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true; };
    const ferme = (x) => { for (let d = x.parentElement && x.parentElement.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) if (!d.open) return true; return false; };
    // les navigateurs gardent des cadres pour le contenu d'un <details> replié : il faut le tester à part
    const rendu = (x) => !!x && x.getClientRects().length > 0 && !x.closest("[inert]") && !ferme(x);

    // ---------- parcours ----------
    function demarrer(depart) {
      if (actif) actif.arreter(false);
      const etapes = construireEtapes();
      let index = Math.min(Math.max(depart || 0, 0), etapes.length - 1);
      const faits = new Set();
      const ecouteurs = [];
      const ecouter = (cible_, type, fn, options) => { cible_.addEventListener(type, fn, options); ecouteurs.push(() => cible_.removeEventListener(type, fn, options)); };

      const corps = el("div", { class: "guide-corps" });
      const etat = el("p", { class: "guide-etat", role: "status", "aria-live": "polite" });
      const desactive = (b, oui) => b.setAttribute("aria-disabled", String(!!oui)); // jamais « disabled » : le focus reste sur le bouton
      const actionner = (b, fn) => b.addEventListener("click", () => { if (b.getAttribute("aria-disabled") !== "true") fn(); });
      const precedent = el("button", { type: "button", class: "secondaire petit", texte: "Précédent" });
      const suivant = el("button", { type: "button", class: "primaire petit guide-suivant", texte: "Suivant" });
      const passer = el("button", { type: "button", class: "secondaire petit", texte: "Passer cette étape" });
      const aller = el("button", { type: "button", class: "secondaire petit" });
      const quitter = el("button", { type: "button", class: "secondaire petit", texte: "Quitter", aide: "Ferme le guide (Échap). Vos données ne sont pas modifiées." });
      const carte = el("div", { class: "guide-carte", role: "region", "aria-label": "Guide pas à pas", "data-mode": "pres" },
        corps, etat, el("div", { class: "guide-boutons" }, precedent, suivant, passer, aller, quitter));
      barre.after(carte);
      document.body.classList.add("guide-actif");
      document.dispatchEvent(new Event("mecastruct:guide")); // la barre résumé se range (machine.js)
      bouton.setAttribute("aria-pressed", "true");

      const lireValeur = (e) => {
        const c = e.c, x = chercheChamp(c);
        if (x && x.tagName === "SELECT") return x.selectedOptions[0] ? x.selectedOptions[0].textContent : String(x.value);
        if (x) return x.value + (c.unite ? " " + c.unite : "");
        return nombreTexte(lireSaisie()[c.id]);
      };
      const texteExemple = (c) => {
        const v = (f.defaut || {})[c.id];
        if (v === undefined || v === null || (typeof v === "number" && Number.isNaN(v)) || typeof v === "object") return "";
        if (estListe(c)) { const i = (c.options || []).indexOf(v); return c.etiquettes && i >= 0 ? c.etiquettes[i] : String(v); }
        return nombreTexte(v) + (c.unite ? " " + c.unite : "");
      };
      const limites = (c) => {
        const p = [];
        if (c.entier) p.push("entier");
        if (c.min !== null && c.min !== undefined) p.push(`${c.minExclu ? "strictement supérieur à" : "au moins"} ${App.fr(c.min)}`);
        if (c.max !== null && c.max !== undefined) p.push(`au plus ${App.fr(c.max)}`);
        return p.length ? ` (${p.join(", ")})` : "";
      };
      const ligne = (titre, texte, classe) => el("p", { class: "guide-ligne" + (classe ? " " + classe : "") }, el("strong", { texte: titre + " " }), texte);
      const effet = () => {
        const schema = !!opts.apercu || !!f.apercu;
        if (auto) return schema ? "le schéma et le résultat se mettent à jour tout de suite." : "le résultat se met à jour tout de suite.";
        return schema ? "le schéma se met à jour ; le résultat reste celui du dernier calcul jusqu'à « Calculer »."
          : "le résultat reste celui du dernier calcul jusqu'à « Calculer ».";
      };

      function contenu(e, i) {
        const tete = el("p", { class: "guide-numero", texte: `Étape ${i + 1} sur ${etapes.length}` });
        if (e.genre === "champ") {
          const c = e.c;
          const exemple = texteExemple(c);
          return [tete, el("h3", { class: "guide-titre", texte: c.libelle + (c.unite ? ` (${c.unite})` : "") }),
            ligne("Attendu :", estListe(c) ? "un choix dans la liste surlignée." : `un nombre${c.unite ? " en " + c.unite : ""}${limites(c)}.`),
            c.aide ? el("p", { class: "guide-ligne guide-aide", texte: c.aide }) : null,
            exemple ? ligne("Exemple :", `${exemple} (valeur de départ de la page).`) : null,
            ligne("Ensuite :", effet())];
        }
        if (e.genre === "groupe") {
          const tableaux = (e.g.champs || []).filter((c) => c.type === "tableau").map((c) => c.libelle.replace(/ \(.*\)$/, "").toLowerCase());
          return [tete, el("h3", { class: "guide-titre", texte: e.g.titre }),
            ligne("En bref :", e.note),
            ligne("Attendu :", `rien d'obligatoire ici : lisez le groupe surligné et ajustez ses tableaux${tableaux.length ? " (" + tableaux.join(", ") + ")" : ""} si besoin. L'exemple de départ est déjà rempli.`),
            ligne("Ensuite :", effet())];
        }
        if (e.genre === "calcul") {
          return [tete, el("h3", { class: "guide-titre", texte: "Lancer le calcul" }),
            ligne("Attendu :", "cliquer sur le bouton « Calculer » surligné (ou Entrée dans un champ)."),
            ligne("Ensuite :", "le calcul se lance : le résultat, le schéma et les graphiques passent à votre saisie.")];
        }
        return [tete, el("h3", { class: "guide-titre", texte: "Lire le verdict" }),
          ligne("Attendu :", "rien à saisir, regardez le cadre « Résultat » surligné."),
          ligne("Exemple :", "« Vérifié » ou « Non vérifié », puis une ligne par mode de ruine ; le trait de la barre marque 100 % de l'admissible."),
          ligne("Ensuite :", "si la saisie change, le résultat se met à jour" + (auto ? " tout seul." : " après un nouveau clic sur « Calculer ».") )];
      }

      function evaluer() {
        const e = etapes[index];
        const x = cible(e);
        if (e.genre === "groupe") return { ok: true, texte: x ? "Rien de bloquant : regardez le groupe, puis cliquez sur « Suivant »." : "Ce groupe n'est pas affiché : passez à l'étape suivante." };
        if (e.genre === "champ") {
          if (!x) return { ok: true, texte: "Cette case n'est pas affichée avec les réglages actuels : passez à l'étape suivante." };
          const champ = chercheChamp(e.c);
          if (champ && (champ.classList.contains("invalide") || champ.dataset.refuse || champ.getAttribute("aria-invalid") === "true"))
            return { ok: false, texte: "Valeur refusée : corrigez-la dans la case surlignée (le message est sous la case)." };
          if (faits.has(index)) return { ok: true, texte: `Fait : « ${e.c.libelle} » vaut maintenant ${lireValeur(e)}. Cliquez sur « Suivant ».` };
          // la case porte déjà une valeur valide (exemple de départ, saisie gardée) : l'étape est validée d'office
          if (champ && String(champ.value).trim() !== "") return { ok: true, texte: `Valeur déjà renseignée : ${lireValeur(e)}. Cliquez sur « Suivant », ou modifiez-la d'abord.` };
          return { ok: false, texte: estListe(e.c)
            ? "En attente : choisissez une valeur dans la liste."
            : "En attente : saisissez une valeur et validez avec Entrée." };
        }
        if (e.genre === "calcul") return faits.has(index) ? { ok: true, texte: "Fait : le calcul est lancé. Cliquez sur « Suivant »." }
          : { ok: false, texte: "En attente : clic sur « Calculer »." };
        const pret = !!resultat.querySelector(".bilan, .verdict");
        return pret ? { ok: true, texte: "Fait : le verdict est affiché. Cliquez sur « Terminer »." } : { ok: false, texte: "En attente du résultat." };
      }
      function majEtat() {
        const s = evaluer();
        if (etat.textContent !== s.texte) etat.textContent = s.texte;
        etat.classList.toggle("fait", s.ok);
        desactive(suivant, !s.ok);
      }

      // ---------- surlignage et placement ----------
      let surligne = null;
      function surligner() {
        const x = cible(etapes[index]);
        if (surligne === x) return;
        if (surligne) surligne.classList.remove("guide-cible");
        surligne = x;
        if (x) x.classList.add("guide-cible");
      }
      // bas du menu une fois collé en haut de la fenêtre (position « sticky ») : sa hauteur, pas sa position du moment
      const hautLibre = () => (App.hautBarre ? App.hautBarre() : 0) + 6; // 0 quand le menu n'est plus collant (paysage bas)
      const borner = (v, a, b) => Math.max(a, Math.min(v, b));
      function placer() {
        if (!bloc.isConnected) return arreter(false);
        const x = cible(etapes[index]);
        const vw = document.documentElement.clientWidth, vh = window.innerHeight;
        let mode = "dock", top = 0, left = 0;
        if (x && rendu(x) && vw >= 700) {
          carte.dataset.mode = "pres";
          carte.style.top = "0px"; carte.style.left = "0px";
          const w = carte.offsetWidth, h = carte.offsetHeight, r = x.getBoundingClientRect(), haut = hautLibre();
          const essais = [
            [r.bottom + 12, borner(r.left, 8, vw - w - 8)],                                    // sous l'élément
            [r.top - 12 - h, borner(r.left, 8, vw - w - 8)],                                   // au-dessus
            [borner(r.top, haut, vh - h - 8), r.right + 12],                                   // à droite
            [borner(r.top, haut, vh - h - 8), r.left - 12 - w],                                // à gauche
          ];
          for (const [t, l] of essais) {
            if (t >= haut && t + h <= vh - 8 && l >= 8 && l + w <= vw - 8) { mode = "pres"; top = t; left = l; break; }
          }
        }
        carte.dataset.mode = mode;
        if (mode === "pres") { carte.style.top = Math.round(top) + "px"; carte.style.left = Math.round(left) + "px"; }
        else { carte.style.top = ""; carte.style.left = ""; }
        // carte en bas : la page gagne autant de marge, pour que rien (bouton, pied de page) ne reste caché dessous
        document.documentElement.style.setProperty("--guide-bas", mode === "dock" ? carte.offsetHeight + 16 + "px" : "0px");
        document.body.classList.toggle("guide-dock", mode === "dock");
        return mode;
      }
      // à l'arrivée sur une étape : ouvre le groupe replié, amène l'élément à l'écran, puis le dégage de la carte
      // Zone libre : sous le menu collant, au-dessus de la carte quand elle est en bas (mode « dock »). La barre résumé se range
      // pendant le guide (machine.js), elle ne prend donc plus de place. L'élément visé s'y range en entier, ou au moins par le haut.
      function amener() {
        const x = cible(etapes[index]);
        if (!x) return;
        ouvrirParents(x);
        if (x.matches("details")) x.open = true; // étape « groupe » : le groupe visé s'ouvre
        const vh = window.innerHeight;
        const r = x.getBoundingClientRect();
        if (r.top < hautLibre() + 8 || r.bottom > vh - 8 || !rendu(x)) x.scrollIntoView({ block: r.height > vh * 0.45 ? "start" : "center", behavior: "instant" });
        if (placer() === "dock") {
          const haut = hautLibre() + 8, bas = carte.getBoundingClientRect().top - 8;
          const r2 = x.getBoundingClientRect();
          let d = 0;
          if (r2.height >= bas - haut) d = r2.top - haut; // plus grand que la zone libre : on en montre le début
          else if (r2.top < haut || r2.bottom > bas) d = (r2.top + r2.bottom) / 2 - (haut + bas) / 2; // sinon, au milieu de la zone libre
          if (Math.abs(d) >= 1) window.scrollBy({ top: d, behavior: "instant" });
        }
      }

      function afficher(i) {
        index = i;
        session.ecrire(ident, i);
        const e = etapes[i];
        corps.replaceChildren(...contenu(e, i));
        desactive(precedent, i === 0);
        suivant.textContent = i === etapes.length - 1 ? "Terminer" : "Suivant";
        passer.hidden = i === etapes.length - 1;
        aller.hidden = e.genre === "verdict";
        aller.textContent = e.genre === "calcul" ? "Aller au bouton" : "Aller à la case";
        corps.scrollTop = 0;
        surligner();
        majEtat(); // avant amener() : la hauteur de la carte doit être définitive pour dégager l'élément
        amener();
      }

      function arreter(effacer = true, rendreFocus = false) {
        if (actif && actif.carte !== carte) return;
        const dansCarte = carte.contains(document.activeElement);
        for (const defaire of ecouteurs) defaire();
        observateur.disconnect();
        if (surligne) surligne.classList.remove("guide-cible");
        carte.remove();
        document.body.classList.remove("guide-actif", "guide-dock");
        document.documentElement.style.removeProperty("--guide-bas");
        document.dispatchEvent(new Event("mecastruct:guide")); // la barre résumé reparaît si besoin
        bouton.setAttribute("aria-pressed", "false");
        if (effacer) session.oublier(ident);
        actif = null;
        if (rendreFocus || dansCarte) bouton.focus({ preventScroll: true });
      }

      function terminer() { arreter(true, true); App.toast("Guide terminé : vos données n'ont pas été modifiées."); }
      actionner(suivant, () => { if (index === etapes.length - 1) terminer(); else afficher(index + 1); });
      actionner(precedent, () => afficher(index - 1));
      actionner(passer, () => afficher(index + 1));
      actionner(aller, () => {
        const x = cible(etapes[index]);
        const champ = x && (x.matches("input, select, button") ? x : x.matches("details") ? x.querySelector("summary") : x.querySelector("input, select"));
        if (champ) { amener(); champ.focus({ preventScroll: true }); } // jamais de saut de page : amener() range déjà la case hors de la carte
      });
      actionner(quitter, () => arreter(true, true));

      // ---------- conditions : on observe la page, on ne la modifie pas ----------
      const surChamp = (e) => {
        const etape = etapes[index];
        if (etape.genre !== "champ") return;
        const t = e.target;
        if (!t || !t.dataset || t.dataset.id !== etape.c.id) return;
        if (e.type === "input" && (t.classList.contains("invalide") || t.dataset.refuse || t.tagName === "SELECT")) return majEtat(); // valeur refusée : pas validée
        if (e.type === "keydown" && e.key !== "Enter") return;
        faits.add(index);
        majEtat();
      };
      for (const type of ["input", "change", "keydown"]) ecouter(formulaire, type, surChamp);
      ecouter(formulaire, "submit", () => { if (etapes[index].genre === "calcul") { faits.add(index); setTimeout(majEtat, 0); } });
      ecouter(bloc, "click", (e) => {
        if (etapes[index].genre === "calcul" && e.target.closest && e.target.closest(".actions-schema button")) { faits.add(index); setTimeout(majEtat, 0); }
      });
      // Échap quitte le guide, sauf s'il a déjà servi à autre chose (panneau IA fermé) ou s'il annule une saisie dans un champ
      ecouter(document, "keydown", (e) => {
        if (e.key !== "Escape" || e.defaultPrevented) return;
        if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
        arreter(true, carte.contains(document.activeElement));
      });
      ecouter(window, "hashchange", () => arreter(false)); // changement de page : l'étape reste mémorisée pour la reprise

      let trame = 0;
      const replacer = () => {
        if (trame) return;
        trame = requestAnimationFrame(() => { trame = 0; if (!bloc.isConnected) return arreter(false); surligner(); majEtat(); placer(); });
      };
      ecouter(window, "resize", replacer);
      ecouter(document, "scroll", replacer, true); // aussi le défilement de la colonne de résultat
      const observateur = new MutationObserver(replacer);
      observateur.observe(formulaire, { childList: true, subtree: true });
      observateur.observe(resultat, { childList: true, subtree: true });
      // changement d'onglet ou de page : le bloc quitte le document, le guide s'arrête (étape gardée pour la reprise)
      const surveillant = new MutationObserver(() => { if (!bloc.isConnected) arreter(false); });
      surveillant.observe(document.getElementById("contenu") || document.body, { childList: true, subtree: true });
      ecouteurs.push(() => surveillant.disconnect());

      actif = { carte, bouton, arreter };
      afficher(index);
    }
  }

  App.guide = { monter };
})();
