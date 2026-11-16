"use strict";
// Convertisseur d'unités : grandeur, valeur, de, vers ; résultat à copier et valeur dans toutes les unités.

(() => {
  const { el } = App;

  App.genre("convertisseur", (contenu, page, { pret }) => {
    contenu.append(el("h1", { texte: page.titre }), el("p", { class: "intro", texte: page.texte }));
    if (!pret) {
      contenu.append(App.message("info", "Le calcul se charge : le convertisseur apparaîtra dans quelques secondes."));
      return;
    }
    const cat = App.calculer("conv.catalogue").sortie;
    const garde = App.memoire.lire("conv", {});
    const grandeur = el("select", {}, cat.grandeurs.map((g) => el("option", { value: g.nom, texte: g.nom })));
    const valeur = el("input", { type: "text", inputmode: "decimal" });
    const de = el("select"), vers = el("select");
    const resultat = el("div", { "aria-live": "polite" });

    const remplirUnites = (g, choixDe, choixVers) => {
      const opts = () => g.unites.map((u) => el("option", { value: u, texte: u }));
      de.replaceChildren(...opts());
      vers.replaceChildren(...opts());
      de.value = g.unites.includes(choixDe) ? choixDe : g.unites[g.de];
      vers.value = g.unites.includes(choixVers) ? choixVers : g.unites[g.vers];
    };
    const g0 = cat.grandeurs.find((g) => g.nom === garde.grandeur) || cat.grandeurs[0];
    grandeur.value = g0.nom;
    valeur.value = App.fr(garde.valeur ?? 1);
    remplirUnites(g0, garde.de, garde.vers);

    const convertir = () => {
      const v = App.nombre(valeur.value);
      valeur.classList.toggle("invalide", v === "" || Number.isNaN(v));
      if (v === "" || Number.isNaN(v)) return resultat.replaceChildren(App.message("avertissement", "Saisissez un nombre."));
      const s = { grandeur: grandeur.value, valeur: v, de: de.value, vers: vers.value };
      App.memoire.ecrire("conv", s);
      const r = App.calculer("conv", s);
      if (!r.ok) return resultat.replaceChildren(App.message("erreur", r.erreur));
      const copie = el("button", { type: "button", class: "secondaire petit", texte: "Copier la valeur" });
      copie.addEventListener("click", async () => { copie.textContent = (await App.copier(r.sortie.texte)) ? "Copié" : "Copie impossible"; });
      resultat.replaceChildren(
        el("p", { class: "message succes verdict" }, `${App.fr(v)} ${de.value} = ${r.sortie.affiche} ${vers.value} `, copie),
        App.tableau(r.sortie.tableau));
    };
    grandeur.addEventListener("change", () => { remplirUnites(cat.grandeurs.find((g) => g.nom === grandeur.value)); convertir(); });
    for (const x of [valeur, de, vers]) x.addEventListener(x === valeur ? "input" : "change", convertir);
    const inverser = el("button", { type: "button", class: "secondaire", texte: "Inverser", onclick: () => { [de.value, vers.value] = [vers.value, de.value]; convertir(); } });

    contenu.append(
      el("div", { class: "grille conv" }, el("label", {}, "Grandeur", grandeur), el("label", {}, "Valeur", valeur),
        el("label", {}, "De", de), el("label", {}, "Vers", vers), el("div", { class: "bas" }, inverser)),
      resultat,
      App.message("info", "Les champs de saisie de l'application sont en mm, m, kN et MPa ; les résultats aussi."),
      el("div", { class: "cartes" },
        el("section", { class: "carte" }, el("h2", { texte: "Unités attendues dans les champs" }), App.tableau(cat.attendues)),
        el("section", { class: "carte" }, el("h2", { texte: "Équivalences utiles en RdM" }), App.tableau(cat.equivalences))));
    convertir();
  });
})();
