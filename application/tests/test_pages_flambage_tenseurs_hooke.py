"""Tests des pages Flambage, Tenseurs et critères et Hooke et jauges : exécution, exemples, transferts."""

import pytest

from mecastruct.bureau import state
from mecastruct.bureau.pages.hooke_jauges import MODES


def _hooke(bureau, onglet=0):
    bureau.ouvre("hooke_jauges")
    bureau.page.onglets.setCurrentIndex(onglet)
    bureau.attend()


@pytest.mark.parametrize("nom", ["flambage", "tenseurs", "hooke_jauges"])
def test_la_page_s_ouvre(bureau, nom):
    bureau.ouvre(nom)
    assert bureau.page.bati


@pytest.mark.parametrize(
    ("page", "onglet", "resultat"),
    [("flambage", 0, "Fla"), ("tenseurs", 0, "Ten"), ("hooke_jauges", 0, "Hoo"), ("hooke_jauges", 1, "Jau")],
)
def test_chaque_exemple_se_calcule(bureau, page, onglet, resultat):
    bureau.ouvre(page)
    if page == "hooke_jauges":
        bureau.page.onglets.setCurrentIndex(onglet)
        bureau.attend()
    bureau.clique("Calculer")
    assert state.result(resultat) is not None


@pytest.mark.parametrize("mode", list(MODES))
def test_hooke_chaque_mode_se_calcule(bureau, mode):
    _hooke(bureau)
    bureau.choisit("Loi", MODES[mode])
    bureau.clique("Recharger l'exemple")
    bureau.clique("Calculer")
    assert state.result("Hoo")["result"]["mode"] == mode


def test_hooke_champs_inactifs_selon_le_mode(bureau):
    _hooke(bureau)
    bureau.choisit("Loi", MODES["planeStrain"])
    assert not bureau.champ("σxx (MPa)").isEnabled() and bureau.champ("εxx (µdéf)").isEnabled()
    bureau.choisit("Loi", MODES["ortho"])
    assert not bureau.champ("E (GPa)").isEnabled()
    bureau.ouvre_volet("Orthotrope (axes 1, 2, 3 = x, y, z)")
    assert bureau.champ("E1 (GPa)").isEnabled()


def test_flambage_regime_et_verdict_lisibles(bureau):
    """Le régime est mis en évidence (Rankine pour l'exemple) et le verdict suit P ; P = 0 : pas de verdict."""
    bureau.ouvre("flambage")
    bureau.clique("Calculer")
    assert bureau.a_texte("Régime : Poutre moyenne")
    assert bureau.a_texte("vérifié")
    bureau.saisit("P appliquée (compression > 0, 0 = aucune) (kN)", "0")
    bureau.clique("Calculer")
    assert not bureau.a_texte("Padm = ")


def test_flambage_alerte_pres_du_seuil_et_libelle_de_p(bureau):
    """λ à ±10 % de λlim : avertissement visible ; le libellé de P précise le signe (compression > 0)."""
    bureau.ouvre("flambage")
    assert bureau.a_texte("compression > 0")
    bureau.clique("Calculer")
    assert not bureau.a_texte("λlim =") or not bureau.a_texte("change de modèle")
    b = state.result("Fla")["result"]["analysis"]
    L = state.saisie("Fla")["L"] * b["lambdaLim"] / b["lambda"]
    bureau.saisit("Longueur L (m)", f"{L:.10g}")
    bureau.clique("Calculer")
    assert bureau.a_texte("change de modèle")


@pytest.mark.parametrize("cond", ["encastre-libre", "encastre-articule", "encastre-encastre"])
def test_flambage_conditions_aux_limites(bureau, cond):
    from mecastruct.bureau.pages.flambage import CONDITIONS

    bureau.ouvre("flambage")
    bureau.choisit("Conditions aux limites", CONDITIONS[cond])
    bureau.clique("Calculer")  # la ligne d'état peut être rouge : P = 300 kN dépasse Padm pour encastré-libre
    assert state.result("Fla")["result"]["analysis"]["condition"] == cond


def test_flambage_charger_un_profile(bureau):
    bureau.ouvre("flambage")
    bureau.choisit("Famille de profilé", "IPE")
    bureau.choisit("Profilé", "IPE 300")
    bureau.clique("Charger le profilé")
    assert state.saisie("Fla")["S"] == pytest.approx(5381.0)
    assert "IPE 300" in state.v["Fla_info"]


def test_flambage_importer_sans_section_calculee(bureau):
    bureau.ouvre("flambage")
    bureau.clique("← Importer depuis Sections")
    assert bureau.a_texte("Calculez d'abord une section")


def test_section_envoyee_depuis_sections_se_lit_dans_flambage(bureau):
    """La section calculée dans Sections arrive dans Flambage (valeurs, texte, matériau, calcul)."""
    bureau.ouvre("sections")
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    bureau.clique("Utiliser cette section pour une poutre")
    saisie = state.saisie("Fla")
    bureau.ouvre("flambage")
    assert bureau.valeur("S (mm²)") == f"{saisie['S']:.6g}".replace(".", ",")
    assert bureau.a_texte("profil en I")
    bureau.clique("Calculer")
    assert not state.result("Fla")["result"]["analysis"]["ok"]  # IPE 200 de 4 m sous 300 kN : NON vérifié
    assert bureau.a_texte("NON vérifié")


def test_flambage_importer_depuis_sections_met_a_jour_poutres_et_flambage(bureau):
    bureau.ouvre("sections")
    bureau.clique("Calculer")
    state.saisie("Sec")["type"] = "disque"
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    bureau.ouvre("flambage")
    bureau.clique("← Importer depuis Sections")
    P = state.result("Sec")["result"]["P"]
    assert state.saisie("Fla")["Iz"] == pytest.approx(P["Iz"] * 1e12)
    assert state.saisie("Beam")["Iz"] == pytest.approx(P["Iz"] * 1e12)
    assert bureau.a_texte("disque")


def test_poutre_vers_tenseurs_se_lit_dans_la_page_tenseurs(bureau):
    """Le σxx du point le plus sollicité de la poutre arrive dans Tenseurs et se calcule."""
    bureau.ouvre("poutres")
    bureau.clique("Envoyer au tenseur (point le plus sollicité)")
    sigma = state.result("Beam")["check"]["sigma"] / 1e6
    bureau.ouvre("tenseurs")
    assert bureau.champ("Re = σe (MPa)").text() == f"{state.saisie('Beam')['Re']:.6g}".replace(".", ",")
    bureau.clique("Calculer")
    pr = state.result("Ten")["result"]["principal"]
    assert pr["sigmaI"] / 1e6 == pytest.approx(sigma, rel=1e-9)  # σxx seul : la contrainte principale est σxx
    assert pr["sigmaII"] == pytest.approx(0.0, abs=1e-6) and pr["sigmaIII"] == pytest.approx(0.0, abs=1e-6)


def test_tenseurs_facette_par_normale(bureau):
    bureau.ouvre("tenseurs")
    bureau.choisit("Définition", "Normale n (nx, ny, nz)")
    assert not bureau.champ("θ (°)").isEnabled() and bureau.champ("nx (-)").isEnabled()
    bureau.clique("Calculer")
    assert state.result("Ten") is not None


def test_grille_du_tenseur_reste_symetrique(bureau):
    from PySide6.QtWidgets import QTableWidget

    bureau.ouvre("tenseurs")
    grille = next(t for t in bureau._visibles(QTableWidget))
    grille.item(0, 1).setText("12,5")
    bureau.attend()
    sig = state.saisie("Ten")["sig"]
    assert sig[0][1] == 12.5 and sig[1][0] == 12.5


def test_symmetrize_garde_le_tenseur_symetrique():
    from mecastruct.services.compute import symmetrize

    sig = [[80.0, 30.0, 0.0], [30.0, -40.0, 0.0], [0.0, 0.0, 20.0]]
    out = symmetrize(sig, {0: {"y": 12.0}, 2: {"x": None}, 1: {"y": -5.0}})
    assert out == [[80.0, 12.0, 0.0], [12.0, -5.0, 0.0], [0.0, 0.0, 20.0]]
    assert sig[0][1] == 30.0  # entrée inchangée
