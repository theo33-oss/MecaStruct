"use strict";
// Bandeau du menu repliable : une punaise en bas à droite. Épinglé (par défaut), le menu reste ouvert.
// Détaché, il se replie en une ligne « Famille › Page » et se rouvre au survol, au clavier ou au clic, PAR-DESSUS
// la page : une marge basse négative garde la place prise par la ligne repliée, rien ne bouge sous la souris.
// Seulement avec une vraie souris et un écran assez haut : au tactile et en paysage bas, le menu reste entier.

(() => {
  const { el } = App;
  const CLE = "bandeau.libre";
  const DELAI_FERMETURE = 250;
  // punaise des logiciels de CAO : debout quand le menu est épinglé, couchée quand il se replie tout seul
  const PUNAISE = (angle) => '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">'
    + `<g transform="rotate(${angle} 10 10)"><path d="M6 2h8v2h-1.2l.5 5.5c1.3.4 2.2 1.3 2.2 2.5h-11c0-1.2.9-2.1 2.2-2.5L7.2 4H6z" fill="currentColor"/>`
    + '<path d="M10 12v6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></g></svg>';
  const EPINGLEE = PUNAISE(0);
  const LIBRE = PUNAISE(90);

  const barre = App.$("barre");
  if (!barre || App.$("verrou")) return;
  const souris = matchMedia("(hover: hover) and (pointer: fine) and (min-height: 521px)");
  let libre = App.memoire.lire(CLE, false);
  let ouvert = false, survol = false, minuterie = null;

  const verrou = el("button", { type: "button", id: "verrou", class: "verrou secondaire", "aria-label": "Épingler le menu" });
  const fil = el("span", { class: "fil", "aria-hidden": "true", texte: "Accueil" });
  barre.insertBefore(verrou, App.$("recherche-panneau"));
  barre.append(fil);

  const annuler = () => { clearTimeout(minuterie); minuterie = null; };

  // Pose les classes et la marge : la hauteur repliée est mesurée à chaque fois (le menu ouvert peut tenir sur plusieurs lignes).
  function placer() {
    const actif = souris.matches && libre;
    verrou.hidden = !souris.matches;
    barre.classList.toggle("avec-verrou", souris.matches);
    barre.classList.toggle("repliable", actif);
    barre.classList.remove("ouvert");
    barre.style.marginBottom = "";
    if (actif && ouvert) {
      const repliee = barre.getBoundingClientRect().height;
      barre.classList.add("ouvert");
      barre.style.marginBottom = Math.min(0, repliee - barre.getBoundingClientRect().height) + "px";
    }
    App.majBarre();
  }

  function dessinerVerrou() {
    verrou.innerHTML = libre ? LIBRE : EPINGLEE;
    verrou.setAttribute("aria-pressed", String(!libre));
    verrou.dataset.aide = libre ? "Menu replié automatiquement. Cliquer pour l'épingler : il reste ouvert." : "Menu épinglé. Cliquer pour qu'il se replie tout seul.";
  }

  function ouvrir() {
    annuler();
    if (ouvert) return;
    ouvert = true;
    placer();
  }

  // Referme, sauf si la souris est dessus, si le clavier est dans le menu ou si la recherche est ouverte.
  function refermerBientot() {
    annuler();
    minuterie = setTimeout(() => {
      minuterie = null;
      const recherche = App.$("recherche-panneau");
      if (!ouvert || survol || barre.querySelector("#menu :focus-visible, #sous :focus-visible") || (recherche && !recherche.hidden)) return;
      ouvert = false;
      placer();
    }, DELAI_FERMETURE);
  }

  verrou.addEventListener("click", () => {
    libre = !libre;
    App.memoire.ecrire(CLE, libre);
    ouvert = true; // la souris (ou le clavier) est sur la punaise : le menu ne se replie qu'après
    dessinerVerrou();
    placer();
    if (!survol) refermerBientot();
  });
  barre.addEventListener("pointerenter", (e) => { if (e.pointerType !== "touch") { survol = true; ouvrir(); } });
  barre.addEventListener("pointerleave", (e) => { if (e.pointerType !== "touch") { survol = false; refermerBientot(); } });
  fil.addEventListener("click", () => { ouvrir(); verrou.focus({ preventScroll: true }); });
  barre.addEventListener("focusin", (e) => { if (e.target.closest("#menu, #sous") && e.target.matches(":focus-visible")) ouvrir(); });
  barre.addEventListener("focusout", refermerBientot);
  barre.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || e.defaultPrevented || !libre || !ouvert) return;
    annuler();
    verrou.focus({ preventScroll: true });
    ouvert = false;
    placer();
  });
  document.addEventListener("pointerdown", (e) => { if (!barre.contains(e.target)) { survol = false; refermerBientot(); } });
  document.addEventListener("mecastruct:page", (e) => {
    const p = e.detail.page;
    const famille = App.FAMILLES.find((f) => f.id === p.famille);
    fil.textContent = famille ? famille.titre + " › " + p.titre : p.titre;
    placer();
  });
  window.addEventListener("resize", placer);
  souris.addEventListener("change", placer);

  dessinerVerrou();
  placer();
})();
