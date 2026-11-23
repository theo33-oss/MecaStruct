"""Briques communes des pages « Éléments de machines » : saisie, Calculer, résultats et explications du calcul.

La saisie vit dans state.v sous les clés « <page>.<champ> » et le résultat sous « <page>.res » avec l'empreinte de la
saisie qui l'a donné (résultat périmé signalé).
"""

from collections.abc import Callable
from typing import Any

from mecastruct.bureau import exports, machine_dossier, state
from mecastruct.bureau.page_calcul import PageCalcul, PageOnglets
from mecastruct.bureau.widgets import Section, Zone, schema_replier
from mecastruct.services import sources

SAISIE_MODIFIEE = "(saisie modifiée : cliquez sur Calculer)"


def init(page: str, defaut: dict) -> None:
    """Valeurs de départ des champs de `page` (exemple d'école), sans écraser une saisie en cours."""
    for k, v in defaut.items():
        state.v.setdefault(f"{page}.{k}", v)


def num(z: Zone, page: str, champ: str, label: str, unite: str = "", min_value: float | None = None,
        max_value: float | None = None, step: Any = None) -> None:  # fmt: skip
    """Champ numérique « label (unité) » de la page."""
    if champ == "s" and label.startswith("Coefficient de sécurité"):
        z.securite(label, f"{page}.{champ}")
        return
    z.nombre(f"{label} ({unite})" if unite else label, f"{page}.{champ}", mini=min_value, maxi=max_value)


def saisie(page: str, defaut: dict) -> dict:
    """Saisie courante de `page` (mêmes clés que `defaut`)."""
    return {k: state.v.get(f"{page}.{k}", v) for k, v in defaut.items()}


def lance(pg: Any, page: str, defaut: dict, travail: Callable[[dict], dict]) -> None:
    """Calcule `page` avec la saisie courante ; garde le résultat et l'empreinte de la saisie, ou l'erreur."""
    s = saisie(page, defaut)
    schema_replier(page)  # « Calculer » : le schéma se replie, il ne reste que les résultats (sauf choix mémorisé)

    def fin(res: dict) -> None:
        state.v[f"{page}.res"] = {"res": res, "empreinte": repr(s)}

    def echec() -> None:
        state.v.pop(f"{page}.res", None)

    pg.lancer(lambda: travail(s), fin, f"erreur.{page}", echec)


def calcul(z: Zone, page: str, defaut: dict, travail: Callable[[dict], dict]) -> None:
    """Bouton « Calculer » et erreur éventuelle du dernier calcul."""
    z.bouton("Calculer", lambda: lance(z.page, page, defaut, travail), primaire=True)
    z.erreurGardee(f"erreur.{page}")


def apercu(z: Zone, dessin: Callable[[], Any]) -> None:
    """Schéma dessiné d'après la saisie actuelle : il suit chaque valeur modifiée, avant même « Calculer »."""
    def dessiner(c: Zone) -> None:
        try:
            fig = dessin()
        except Exception as err:  # noqa: BLE001 : saisie incomplète ou hors du domaine dessinable : schéma omis
            c.legende(f"Schéma indisponible : {getattr(err, 'message', err)}")
            return
        c.plot(fig)

    # même clé que `lance` (identifiant du calcul) : le clic sur « Calculer » replie ce bloc
    z.schema(getattr(z.page, "P", "") or type(z.page).__name__, dessiner)


def resultats(z: Zone, page: str, s: dict, graphique: Callable[[dict], Any] | None = None, titre: str = "") -> None:
    """Ligne d'état, graphique, synthèse et explications du calcul (formules remplies et démarche)."""
    calc = state.v.get(f"{page}.res")
    if calc is None:
        z.info("Renseignez les données, puis cliquez sur « Calculer ».")
        return
    res = calc["res"]
    if calc["empreinte"] == repr(s):  # empreinte propre à ces pages
        from mecastruct.services import criteres

        crit = criteres.criteres(page, s, res)
        ok = None if page == "aju" else res["ok"]  # un ajustement n'est comparé à aucune limite : pas de « vérifié »
        z.decision(page, crit, ok, s)  # bloc « Décision » en tête, comme sur le site
        if crit:
            z.modes(crit, res["status"], ok)
        else:
            z.statut(res["status"], ok)
    else:  # verdict coloré retiré : il ne vaut plus pour la saisie affichée
        z.decision(page, [], None, s, perime=True)
        z.avertissement(
            "Saisie modifiée depuis le dernier calcul : les résultats affichés datent de l'ancienne saisie. "
            "Cliquez sur « Calculer » pour les actualiser."
        )
        z.legende(f"{SAISIE_MODIFIEE} {res['status']}")
    if titre:  # bloc-notes et Excel de validation, sous le verdict
        exports.boutons(z, page, s, titre)
    onglets = {"Synthèse": lambda c: c.tableau(res["tables"]["Synthèse"])}
    if graphique is not None:
        onglets = {"Graphique": lambda c: c.plot(graphique(res["result"])), **onglets}
    onglets["Explications du calcul"] = lambda c: explications(c, res)
    z.onglets(onglets, cle=f"onglet.{page}")


def explications(z: Zone, res: dict) -> None:
    """Formules appliquées aux données (avec les valeurs), puis la démarche détaillée du moteur."""

    def ecrire(c: Zone) -> None:
        c.texte("**Formules appliquées à vos données**")
        c.formules(res["result"]["latex"])
        c.texte("**Démarche**")
        for ligne in res["result"]["rapport"][1:]:
            c.texte(f"- {ligne}")

    z.copiable(ecrire, nom="Explications du calcul")


class PageMachine(PageCalcul):
    """Page d'un calcul : sous-classes P, DEFAUT, travail(s), champs(z), notes(z), apercu(z, s), graphique(s), pied."""

    P = ""
    DEFAUT: dict = {}
    pied = None  # (nom, titre, calculs) du bouton « Dossier de validation de cette page », si la page est seule

    def __init__(self, fenetre: Any) -> None:
        super().__init__(fenetre)
        init(self.P, self.DEFAUT)

    @property
    def tab(self) -> str:  # noqa: D102 : pas d'onglet de projet pour ces pages
        return ""

    def travail(self, s: dict) -> dict:
        raise NotImplementedError

    def champs(self, z: Zone) -> None:
        raise NotImplementedError

    def notes(self, z: Zone) -> None:
        """Texte d'aide sous les champs."""

    def apercu(self, z: Zone, s: dict) -> None:
        """Schéma de la saisie, au-dessus des résultats."""

    def graphique(self, s: dict) -> Callable[[dict], Any] | None:
        return None

    def calculer(self) -> None:
        lance(self, self.P, self.DEFAUT, self.travail)

    def saisie(self, z: Zone) -> None:
        calcul(z, self.P, self.DEFAUT, self.travail)
        self.champs(z)
        self.notes(z)
        if sources.source(self.P):
            z.legende(sources.source(self.P))

    def visualisation(self, z: Zone) -> None:
        s = saisie(self.P, self.DEFAUT)
        self.apercu(z, s)
        resultats(z, self.P, s, self.graphique(s), self.titre or self.P)
        if self.pied:
            machine_dossier.bouton(z, *self.pied)


class PageMachineOnglets(PageOnglets):
    """Page à sous-onglets avec, dessous, le bouton « Dossier de validation de cette page » (attribut pied)."""

    pied = None

    def construire(self) -> None:
        super().construire()
        self.piedSection = Section(self, lambda z: machine_dossier.bouton(z, *self.pied), suit=True)
        self.sections.append(self.piedSection)
        self.d.addWidget(self.piedSection)
        for p in self.pages:
            p.parentPage = self

    def actives(self) -> list:
        return []  # chaque sous-page se redessine seule ; le pied est rafraîchi par elles (rafraichirPied)

    def rafraichirPied(self) -> None:
        self.piedSection.rafraichir()

    def afficher(self) -> None:
        super().afficher()
        self.rafraichirPied()
