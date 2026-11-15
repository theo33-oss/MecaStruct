"use strict";
// Accueil : ce que fait l'outil en une phrase, les cinq familles et leurs pages, les deux façons de l'utiliser.

(() => {
  const { el } = App;

  App.genre("accueil", (contenu) => {
    const familles = App.FAMILLES.map((f) => {
      const pages = App.PAGES.filter((p) => p.famille === f.id);
      return el("section", { class: "carte famille-carte" },
        el("h2", { texte: f.titre }),
        el("p", { class: "legende", texte: f.texte }),
        el("ul", { class: "liste-pages" }, pages.map((p) => el("li", {},
          el("a", { href: "#/" + p.id, texte: p.titre }),
          p.genre === "bureau" ? el("span", { class: "pastille", texte: "bureau", aide: "Disponible dans l'application de bureau ; arrive bientôt dans le navigateur." }) : null,
          el("span", { class: "legende", texte: " " + p.texte })))));
    });

    contenu.append(
      el("section", { class: "vedette" },
        el("div", {},
          el("h1", { texte: "Calculs de résistance des matériaux et d'éléments de machines" }),
          el("p", { class: "intro", texte: "Chaque calcul donne un verdict en toutes lettres, les formules remplies avec vos valeurs et la démarche pas à pas. Les moteurs viennent d'une application MATLAB et sont vérifiés contre elle par plus de 1 300 tests." }),
          el("div", { class: "ligne" },
            el("a", { class: "bouton primaire", href: "#/ajustements", texte: "Commencer par un ajustement ISO 286" }),
            el("a", { class: "bouton secondaire", href: "#/limites", texte: "Ce qui est vérifié" }))),
        el("div", { class: "carte deux-facons" },
          el("h2", { texte: "Deux façons de l'utiliser" }),
          el("dl", {},
            el("dt", { texte: "Dans ce navigateur" }),
            el("dd", { texte: "Aucune installation. Le premier chargement prend quelques dizaines de secondes, vos saisies restent dans ce navigateur." }),
            el("dt", { texte: "Sur le bureau Windows" }),
            el("dd", {}, "Toutes les pages, démarrage immédiat, hors ligne, dossiers de validation PDF et Word. ",
              el("a", { href: App.DEPOT + "/releases/latest", texte: "Télécharger l'installateur" }), "."))),
      ),
      el("div", { class: "cartes" }, familles),
    );
  });
})();
