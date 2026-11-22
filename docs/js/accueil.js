"use strict";
// Accueil : ce que fait l'outil en une phrase, les cinq familles et leurs pages, les deux façons de l'utiliser.

(() => {
  const { el } = App;

  // Titre repliable (<details>/<summary> natifs). Clic et clavier seulement (pas de survol : il ouvrait et fermait des blocs
  // sous le pointeur). Ouvert d'office sur grand écran (900 px et plus), replié sur téléphone. Échap referme un repli ouvert
  // quand le focus est dedans. Le contenu pousse la mise en page.
  const GRAND = 900;
  function repliable(titre, contenu) {
    const resume = el("summary", {}, titre);
    const d = el("details", { class: "repli", open: window.innerWidth >= GRAND }, resume, contenu);
    d.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !e.defaultPrevented && d.open && d.contains(document.activeElement)) { d.open = false; resume.focus(); }
    });
    return d;
  }

  App.genre("accueil", (contenu) => {
    const familles = App.FAMILLES.map((f) => {
      const pages = App.PAGES.filter((p) => p.famille === f.id);
      return el("section", { class: "carte famille-carte" },
        el("p", { class: "legende", texte: f.texte }),
        repliable(el("h2", { texte: f.titre }),
          el("ul", { class: "liste-pages" }, pages.map((p) => el("li", {},
            el("a", { href: "#/" + p.id, texte: p.titre }),
            p.genre === "bureau" ? el("span", { class: "pastille", texte: "bureau", aide: "Disponible dans l'application de bureau ; arrive bientôt dans le navigateur." }) : null,
            el("span", { class: "legende", texte: " " + p.texte }))))));
    });

    contenu.append(
      el("section", { class: "vedette" },
        el("div", {},
          el("h1", { texte: "Calculs de résistance des matériaux et d'éléments de machines" }),
          el("p", { class: "intro", texte: "Chaque calcul donne un verdict, un diagramme des modes de ruine avec les coefficients de sécurité, les formules remplies avec vos valeurs et la démarche pas à pas. Il s'exporte en dossier de validation, en bloc-notes ou en Excel à formules. Plus de 1 300 tests vérifient les calculs." }),
          el("div", { class: "ligne" },
            el("a", { class: "bouton primaire", href: "#/ajustements", texte: "Commencer par un ajustement ISO 286" }),
            el("a", { class: "bouton secondaire", href: "#/limites", texte: "Ce qui est vérifié" }))),
        el("div", { class: "carte deux-facons" },
          repliable(el("h2", { texte: "Deux façons de l'utiliser" }),
            el("dl", {},
              el("dt", { texte: "Dans ce navigateur" }),
              el("dd", { texte: "Aucune installation, toutes les pages. Le premier chargement prend 15 à 30 secondes, les suivants quelques secondes. Vos saisies restent dans ce navigateur." }),
              el("dt", { texte: "Sur le bureau Windows" }),
              el("dd", {}, "Démarrage immédiat, hors ligne, dossiers de validation PDF et Word. ",
                el("a", { href: App.DEPOT + "/releases/latest", texte: "Télécharger l'installateur" }), ".")))),
      ),
      App.exemple(App.page("accueil")) || "",
      el("div", { class: "cartes" }, familles),
    );
  });
})();
