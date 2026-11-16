"""Squelette des pages de calcul : en-tête, saisie à gauche, visualisation à droite, volets déplaçables."""

import re
from collections.abc import Callable
from typing import Any, NamedTuple

from mecastruct.bureau import state, tache
from mecastruct.bureau.formula_panel import formula_panel
from PySide6.QtWidgets import QTabWidget

from mecastruct.bureau.widgets import Page, Zone

POSITIONS = ("Haut", "Bas")
_MORCEAU = re.compile(r"^(?P<label>[^=:]{1,25}?) = (?P<value>[^()]+?)(?: \((?P<note>[^()]+)\))?$")


class Volet(NamedTuple):
    """Un volet de saisie : clé, titre, position par défaut (« Haut » ou « Bas »), ouvert par défaut, affichage."""

    cle: str
    titre: str
    defaut: str
    ouvert: bool
    saisie: Callable[[Zone], None]


def modes_resultat(z: Zone, tab: str, res: dict, status: str | None = None, ok: Any = "verdict", extras: dict | None = None,
                   ident: str | None = None, saisie: dict | None = None) -> None:  # fmt: skip
    """Verdict de l'onglet `tab` : diagramme des modes de ruine, ou bandeau coloré s'il n'y a pas de limite à comparer.

    `ok` : « verdict » (lu dans la ligne d'état, comme sur le site), ou True, False, None. `extras` : résultats annexes
    (clavette et goupille pour le cisaillement). Saisie modifiée depuis le calcul : diagramme grisé.
    """
    from mecastruct.services import criteres

    status = status or str(res.get("status", ""))
    if ok == "verdict":
        ok = criteres.verdict(status)
    saisie = saisie if saisie is not None else state.saisie(tab)
    try:
        crit = criteres.criteres(ident or tab, saisie, res if extras is None else {**res, "extras": extras})
    except Exception:  # noqa: BLE001 : un critère impossible à lire n'empêche pas d'afficher le calcul
        crit = []
    if crit:
        z.modes(crit, status, ok, perime=not state.is_current(tab))
    else:
        z.statut(status, ok)


def synthese_statut(z: Zone, status: str) -> None:
    """Valeurs clés tirées d'une ligne d'état « A = 1 u, B = 2 u (vérifié) — C = 3 u » ; rien sans « x = y »."""
    valeurs = []
    for morceau in re.split(r",\s|\s—\s", status):
        m = _MORCEAU.match(morceau.strip())
        if m is None:
            continue
        valeur, _, verdict = m["value"].partition(" : ")
        note = (m["note"] or verdict).strip()
        v = {"label": m["label"].strip(), "value": valeur.strip()}
        if note:
            v["delta"] = note
            v["delta_color"] = {"vérifié": "green", "NON vérifié": "red"}.get(note, "off")
        valeurs.append(v)
    if valeurs:
        z.synthese(valeurs)


def synthese_resultat(z: Zone, tab: str) -> None:
    """Valeurs clés du résultat de l'onglet `tab` ; saisie modifiée depuis le calcul : texte neutre à la place."""
    res = state.result(tab)
    if isinstance(res, dict) and res.get("status"):
        if state.is_current(tab):
            synthese_statut(z, res["status"])
        else:
            z.legende("(saisie modifiée : cliquez sur Calculer)")


def synthese_suivie(z: Zone, tab: str) -> None:
    """Valeurs clés du résultat `tab`, redessinées à chaque changement de la saisie (verdict neutre si elle a changé)."""
    z.section(lambda s: synthese_resultat(s, tab), suit=True)


def panels(z: Zone, page: str, volets: list[Volet]) -> None:
    """Volets de saisie en deux zones (haut, puis « Fonctions avancées ») et volet « Mise en page » pour les déplacer."""

    def pos(v: Volet) -> str:
        return state.v.get(f"mise_en_page.{page}.{v.cle}", v.defaut)

    haut = [v for v in volets if pos(v) == "Haut"]
    bas = [v for v in volets if pos(v) != "Haut"]
    for zone in (haut, bas):
        if zone is bas and bas:
            z.sousTitre("Fonctions avancées")
        for v in zone:
            z.repliable(v.titre, ouvert=v.ouvert, rendu=v.saisie, cle=f"{page}.{v.cle}")

    def raz() -> None:
        for v in volets:
            state.v[f"mise_en_page.{page}.{v.cle}"] = v.defaut
        z.page.rafraichirSaisie()

    def reglage(c: Zone) -> None:
        c.legende("Pour chaque volet : en haut de la colonne, ou dans les fonctions avancées en bas.")
        for v in volets:
            c.radio(v.titre, POSITIONS, f"mise_en_page.{page}.{v.cle}", defaut=v.defaut, apres=z.page.rafraichirSaisie)
        c.bouton("Réinitialiser la mise en page", raz)

    z.repliable("Mise en page", rendu=reglage, cle=f"{page}.mise_en_page")


class PageCalcul(Page):
    """Page à deux panneaux. Sous-classes : titre, fiche (formulaire rapide), tab, saisie(z), visualisation(z), calculer()."""

    titre = ""
    fiche: str | None = None
    tab = ""
    sous = False  # sous-page d'une PageOnglets : le titre est celui de l'onglet

    def construire(self) -> None:
        state.init()
        if self.tab:
            state.abonner(self.tab, self.rafraichirTout)
        self.deuxPanneaux(self.entete, self.saisie, self.visu)
        self.ajuste()

    def entete(self, z: Zone) -> None:
        if not self.sous:
            z.titre(self.titre)
        formula_panel(z, self.fiche)

    def visu(self, z: Zone) -> None:
        ligne = z.colonnes([3, 2])
        ligne[0].case("Agrandir la visualisation", self._cleLarge(), apres=self.ajuste,
                      aide="Élargit cette zone vers la gauche ; la saisie reste accessible dans la colonne étroite.")  # fmt: skip
        ligne[1].bouton("Calculer", self.calculer, primaire=True)
        self.visualisation(z)

    def _cleLarge(self) -> str:
        return f"zones.{self.tab or self.titre}.large"

    def ajuste(self) -> None:
        self.panneau.setSizes([200, 1100] if state.v.get(self._cleLarge()) else [480, 820])

    def rafraichirTout(self) -> None:
        super().rafraichirTout()
        if hasattr(self, "parentPage"):
            self.parentPage.rafraichirPied()

    def surSaisie(self) -> None:
        super().surSaisie()
        if hasattr(self, "parentPage"):
            self.parentPage.rafraichirPied()

    def saisie(self, z: Zone) -> None:
        raise NotImplementedError

    def visualisation(self, z: Zone) -> None:
        raise NotImplementedError

    def calculer(self) -> None:
        raise NotImplementedError

    def lancer(self, travail: Callable[[], Any], fin: Callable[[Any], None], cleErreur: str,
               apresErreur: Callable[[], None] | None = None) -> None:  # fmt: skip
        """Exécute `travail` hors du fil de l'interface, puis `fin(résultat)` ; une erreur est gardée sous cleErreur."""

        def ok(r: Any) -> None:
            state.v.pop(cleErreur, None)
            fin(r)
            self.rafraichirTout()

        def ko(e: Exception) -> None:
            state.v[cleErreur] = e
            if apresErreur:
                apresErreur()
            self.rafraichirTout()

        if not tache.lancer(travail, ok, ko):
            state.v[cleErreur] = RuntimeError("Un calcul est déjà en cours : patientez un instant.")
            self.rafraichirTout()

    def calcule_onglet(self, tab: str, travail: Callable[[], Any], source: str | None = None) -> None:
        """Calcul simple : le résultat de `travail()` devient le résultat de l'onglet `tab`."""
        self.lancer(
            travail,
            lambda r: state.set_result(tab, r, source),
            f"erreur.{tab}",
            lambda: state.effacer_resultat(tab),
        )


class PageOnglets(Page):
    """Page à sous-onglets : chaque onglet est une PageCalcul (sous-classes : titre, sousPages = [(nom, classe)])."""

    titre = ""
    sousPages: list = []

    def construire(self) -> None:
        z = Zone(self, self.d)
        z.titre(self.titre)
        self.onglets = QTabWidget()
        self.pages = []
        for nom, classe in self.sousPages:
            p = classe(self.fenetre)
            p.sous = True
            self.onglets.addTab(p, nom.replace("&", "&&"))
            self.pages.append(p)
        cle = f"onglet.{type(self).__name__}"
        self.onglets.setCurrentIndex(state.v.get(cle, 0))
        self.onglets.currentChanged.connect(lambda i: (state.v.__setitem__(cle, i), self.pages[i].afficher()))
        self.d.addWidget(self.onglets, 1)

    def afficher(self) -> None:
        if not self.bati:
            self.bati = True
            self.construire()
        self.pages[self.onglets.currentIndex()].afficher()
