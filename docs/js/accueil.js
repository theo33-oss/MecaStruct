"use strict";
// Accueil : ce que fait l'outil en une phrase, les cinq familles et leurs pages, les deux façons de l'utiliser.

(() => {
  const { el } = App;

  // Carte à titre repliable (<details>/<summary> natifs), repliée par défaut sur tous les écrans.
  // Référence : clic, Entrée, Espace (un clic ouvre et GARDE ouvert, un second clic referme), Échap referme.
  // En plus, avec une vraie souris (hover: hover + pointer: fine) : la carte s'ouvre au survol et se referme 250 ms après que le
  // pointeur l'a quittée, sauf si elle a été ouverte par un clic (épinglée) ou si le focus clavier est dedans.
  // L'animation (hauteur et fondu) est faite en CSS (::details-content) ; sans elle, l'ouverture est simplement immédiate.
  const DELAI_FERMETURE = 250;
  const souris = () => matchMedia("(hover: hover) and (pointer: fine)").matches;
  function carteRepliable(balise, classe, avant, titre, contenu) {
    const resume = el("summary", {}, titre);
    const d = el("details", { class: "repli repli-accueil" }, resume, contenu);
    const carte = el(balise, { class: classe }, avant, d);
    let epingle = false;   // ouverte (ou gardée) par un clic ou le clavier
    let parSurvol = false; // ouverte seulement par le survol
    let minuterie = null;
    const annuler = () => { clearTimeout(minuterie); minuterie = null; };
    const refermer = () => { annuler(); epingle = false; parSurvol = false; d.open = false; };
    resume.addEventListener("click", (e) => {
      annuler();
      if (d.open && parSurvol) { // ouverte par le survol : le clic la garde ouverte (il ne la referme pas)
        e.preventDefault(); parSurvol = false; epingle = true;
      } else if (d.open) { epingle = false; parSurvol = false; } // le clic referme
      else { epingle = true; parSurvol = false; }                 // le clic ouvre et garde ouvert
    });
    d.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !e.defaultPrevented && d.open && (d.contains(document.activeElement) || parSurvol)) {
        refermer();
        if (d.contains(document.activeElement)) resume.focus();
      }
    });
    carte.addEventListener("pointerenter", (e) => {
      if (e.pointerType === "touch" || !souris()) return;
      annuler();
      if (!d.open) { d.open = true; parSurvol = true; epingle = false; }
    });
    carte.addEventListener("pointerleave", (e) => {
      if (e.pointerType === "touch" || !parSurvol) return;
      annuler();
      minuterie = setTimeout(() => {
        minuterie = null;
        if (parSurvol && !d.contains(document.activeElement)) refermer();
      }, DELAI_FERMETURE);
    });
    return carte;
  }

  App.genre("accueil", (contenu) => {
    const familles = App.FAMILLES.map((f) => {
      const pages = App.PAGES.filter((p) => p.famille === f.id);
      return carteRepliable("section", "carte famille-carte", el("p", { class: "legende", texte: f.texte }),
        el("h2", { texte: f.titre }),
        el("ul", { class: "liste-pages" }, pages.map((p) => el("li", {},
          el("a", { href: "#/" + p.id, texte: p.titre }),
          p.genre === "bureau" ? el("span", { class: "pastille", texte: "bureau", aide: "Disponible dans l'application de bureau ; arrive bientôt dans le navigateur." }) : null,
          el("span", { class: "legende", texte: " " + p.texte })))));
    });

    contenu.append(
      el("section", { class: "vedette" },
        el("div", {},
          el("h1", { texte: "Calculs de résistance des matériaux et d'éléments de machines" }),
          el("p", { class: "intro", texte: "Chaque calcul donne un verdict, un diagramme des modes de ruine avec les coefficients de sécurité, les formules remplies avec vos valeurs et la démarche pas à pas. Il s'exporte en dossier de validation, en bloc-notes ou en Excel à formules. Plus de 1 300 tests vérifient les calculs." }),
          el("div", { class: "ligne" },
            el("a", { class: "bouton primaire", href: "#/ajustements", texte: "Commencer par un ajustement ISO 286" }),
            el("a", { class: "bouton secondaire", href: "#/limites", texte: "Ce qui est vérifié" }))),
        carteRepliable("div", "carte deux-facons", null, el("h2", { texte: "Deux façons de l'utiliser" }),
          el("dl", {},
            el("dt", { texte: "Dans ce navigateur" }),
            el("dd", { texte: "Aucune installation, toutes les pages. Le premier chargement prend 15 à 30 secondes, les suivants quelques secondes. Vos saisies restent dans ce navigateur." }),
            el("dt", { texte: "Sur le bureau Windows" }),
            el("dd", {}, "Démarrage immédiat, hors ligne, dossiers de validation PDF et Word. ",
              el("a", { href: App.DEPOT + "/releases/latest", texte: "Télécharger l'installateur" }), ".")))),
      App.exemple(App.page("accueil")) || "",
      el("div", { class: "cartes" }, familles),
    );
  });
})();
