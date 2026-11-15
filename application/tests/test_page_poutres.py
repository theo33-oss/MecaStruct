"""Tests de la page « Poutres » : exécution, exemple isostatique, cas du README, fonctions avancées."""

import pytest

from mecastruct.bureau import state

VOLET_EC3 = "Eurocode 3 simplifié (flexion + tranchant)"


def _poutres(bureau):
    bureau.ouvre("poutres")
    return state.saisie("Beam")


def _charge(bureau, variante):
    bureau.choisit("Exemple", variante)
    bureau.clique("Charger l'exemple")


def test_page_s_ouvre(bureau):
    _poutres(bureau)
    assert bureau.a_texte("Poutres")


def test_exemple_isostatique_puis_calcul(bureau):
    _poutres(bureau)
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    res = state.result("Beam")
    assert res["sol"]["extrema"]["Mfz"]["max"] > 0
    assert not res["unreliable"]


def test_cas_readme_en_champs(bureau):
    """IPE 200, L = 4 m, 10 kN/m, sans tranchant : flèche 9,029 mm et Mfz max 20 kN·m."""
    s = _poutres(bureau)
    bureau.saisit("Longueur L (m)", "4")
    bureau.saisit("S (mm²)", "2848")
    bureau.saisit("Iz — flexion (x,y) (mm⁴)", "19430000")
    bureau.saisit("Iy — flexion (x,z) (mm⁴)", "1424000")
    bureau.saisit("E (GPa)", "190")
    bureau.case("Tranchant dans Castigliano", False)
    s["sup"] = [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 4.0, "type": "appui_simple", "name": "B"}]
    s["pl"] = []
    s["dl"] = [{"a": 0.0, "b": 4.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}]
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    res = state.result("Beam")
    assert res["sol"]["extrema"]["Mfz"]["max"] / 1e3 == pytest.approx(20.0, rel=1e-6)
    assert res["defl"]["integration"]["fmax"] * 1e3 == pytest.approx(9.029, abs=5e-4)
    assert "9.029" in res["status"]


def test_virgule_ou_point_et_saisie_illisible(bureau):
    s = _poutres(bureau)
    bureau.saisit("Longueur L (m)", "7,5")
    assert s["L"] == 7.5
    bureau.saisit("Longueur L (m)", "abc")  # illisible : l'ancienne valeur revient
    assert s["L"] == 7.5 and bureau.valeur("Longueur L (m)") == "7,5"
    bureau.saisit("Longueur L (m)", "8.25")
    assert s["L"] == 8.25


def test_combinaisons_avec_enveloppe(bureau):
    _poutres(bureau)
    bureau.ouvre_volet("Combinaisons de cas (G permanentes, Q exploitation, W vent, S neige)")
    bureau.clique("Calculer les combinaisons")
    assert state.result("BeamCombo")["Combinaison"].iloc[-1] == "Enveloppe"
    assert "Combinaisons" in bureau.onglets()
    bureau.saisit("Longueur L (m)", "9")  # saisie modifiée : l'onglet le signale
    assert "Combinaisons (saisie modifiée depuis)" in bureau.onglets()


def test_eurocode_fatigue_et_profile_sur_exemple_ipe(bureau):
    _poutres(bureau)
    for volet, bouton in (
        (VOLET_EC3, "Vérifier selon l'Eurocode 3"),
        ("Fatigue (Goodman)", "Vérifier la fatigue"),
        ("Dimensionnement : profilé le plus léger", "Chercher le profilé le plus léger"),
    ):
        bureau.ouvre_volet(volet)
        bureau.clique(bouton)
    assert {"BeamEC3", "BeamFat", "BeamProf"} <= set(state.v["res"])
    assert state.result("BeamProf")[1] is not None


def test_eurocode_refuse_une_section_saisie_a_la_main(bureau):
    _poutres(bureau)
    bureau.saisit("S (mm²)", "5000")  # valeur à la main : plus de forme associée
    bureau.ouvre_volet(VOLET_EC3)
    bureau.clique("Vérifier selon l'Eurocode 3")
    assert state.result("BeamEC3") is None


def test_charge_mobile(bureau):
    _poutres(bureau)
    bureau.ouvre_volet("Charge mobile (convoi d'essieux, enveloppe)")
    bureau.clique("Calculer l'enveloppe de la charge mobile")
    assert state.result("BeamMov") is not None


def test_annexe_nationale_remet_gamma_a_1(bureau):
    s = _poutres(bureau)
    bureau.ouvre_volet(VOLET_EC3)
    bureau.choisit("Annexe nationale", "Autre : saisir γM0 et γM1")
    bureau.saisit("γM0 (-), résistance des sections", "1,1")
    assert s["gM0"] == pytest.approx(1.1)
    bureau.choisit("Annexe nationale", "France (NF EN 1993-1-1/NA)")
    assert s["gM0"] == 1.0 and s["gM1"] == 1.0


def test_charge_rapide_ajoute_une_ligne(bureau):
    _poutres(bureau)
    avant = len(state.saisie("Beam")["dl"])
    bureau.ouvre_volet("Charge rapide (ajoute une ligne au tableau des charges réparties)")
    bureau.choisit("Forme", "Triangulaire croissante (0 → p)")
    bureau.clique("Ajouter cette charge")
    dl = state.saisie("Beam")["dl"]
    assert len(dl) == avant + 1 and dl[-1]["type"] == "linéaire" and dl[-1]["vals"].startswith("0 ")


def test_tassement_ressort_rotule_et_poids_propre_editables(bureau):
    _poutres(bureau)
    _charge(bureau, "tassement")
    assert state.saisie("Beam")["supx"][0]["dy"] == -10.0
    bureau.ouvre_volet("Ressorts, tassements, rotules, température, poids propre")
    bureau.saisit("ΔT uniforme (°C)", "20")
    bureau.case("Poids propre (ρ·S·g, cas G)", True)
    bureau.clique("Calculer")
    s = state.saisie("Beam")
    assert s["thDT"] == 20.0 and s["selfw"] is True and state.result("Beam") is not None
    _charge(bureau, "gerber")
    bureau.clique("Calculer")
    assert len(state.saisie("Beam")["hg"]) == 1


def test_annuler_retablit_le_premier_exemple(bureau):
    _poutres(bureau)
    _charge(bureau, "console")
    L1 = state.saisie("Beam")["L"]
    _charge(bureau, "deuxtravees")
    L2 = state.saisie("Beam")["L"]
    assert L1 != L2
    bureau.clique("↶ Annuler")
    assert state.saisie("Beam")["L"] == L1
    bureau.clique("↷ Rétablir")
    assert state.saisie("Beam")["L"] == L2


def test_envoyer_au_tenseur(bureau):
    _poutres(bureau)
    bureau.clique("Envoyer au tenseur (point le plus sollicité)")
    ten = state.saisie("Ten")
    sigma = state.result("Beam")["check"]["sigma"] / 1e6
    assert ten["sig"][0][0] == pytest.approx(sigma) and ten["mat"] == "S235"


def test_graphiques_empiles_puis_en_onglets(bureau):
    _poutres(bureau)
    bureau.clique("Calculer")
    assert {"Schéma", "Diagrammes", "Déformée α(s), v(s)"} <= set(bureau.textes())
    assert "Équations par tronçon" in bureau.onglets()
    bureau.case("Graphiques en onglets", True)
    assert "Diagrammes" in bureau.onglets()


ESSENTIELS = ["Poutre et matériau", "Section", "Appuis et charges", "Calcul et affichage"]
AVANCES = ["Fatigue (Goodman)", VOLET_EC3, "Charge mobile (convoi d'essieux, enveloppe)"]


def test_volets_avances_sous_le_bouton_calculer(bureau):
    _poutres(bureau)
    ordre = bureau.ordre_vertical(bureau.page.sections[1])
    avance, mise = ordre.index("Fonctions avancées"), ordre.index("Mise en page")
    assert all(ordre.index(t) < avance for t in ESSENTIELS)
    assert all(avance < ordre.index(t) < mise for t in AVANCES)


def test_mise_en_page_deplace_un_volet_puis_reinitialise(bureau):
    _poutres(bureau)
    gauche = bureau.page.sections[1]
    state.v["mise_en_page.Beam.fatigue"] = "Haut"
    bureau.page.rafraichirSaisie()
    ordre = bureau.ordre_vertical(gauche)
    assert ordre.index("Fatigue (Goodman)") < ordre.index("Fonctions avancées")
    state.v["mise_en_page.Beam.section"] = "Bas"
    bureau.page.rafraichirSaisie()
    ordre = bureau.ordre_vertical(gauche)
    assert ordre.index("Section") > ordre.index("Fonctions avancées")
    bureau.ouvre_volet("Mise en page")
    bureau.clique("Réinitialiser la mise en page")
    ordre = bureau.ordre_vertical(gauche)
    assert ordre.index("Section") < ordre.index("Fonctions avancées") < ordre.index("Fatigue (Goodman)")


def test_mise_en_page_survit_au_chargement_d_un_exemple(bureau):
    _poutres(bureau)
    state.v["mise_en_page.Beam.fatigue"] = "Haut"
    bureau.clique("Charger l'exemple")
    assert state.v["mise_en_page.Beam.fatigue"] == "Haut"


def test_synthese_sous_le_bouton_calculer(bureau):
    _poutres(bureau)
    assert not bureau.a_texte("Réaction max")
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    for libelle in ("Réaction max", "|T| max", "|Mf| max", "Flèche max", "Kt·σ max"):
        assert bureau.a_texte(libelle)
    fleche = state.result("Beam")["defl"]["integration"]["fmax"] * 1e3
    assert bureau.a_texte(f"{fleche:.4g} mm")


def test_formulaire_rapide_present(bureau):
    _poutres(bureau)
    assert bureau.a_texte("Formulaire rapide")


def test_schema_suit_la_saisie_apres_un_calcul(bureau):
    _poutres(bureau)
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    assert not bureau.a_texte("Le schéma suit la saisie")
    bureau.saisit("Longueur L (m)", "8")
    assert bureau.a_texte("Le schéma suit la saisie")
    bureau.clique("Calculer")
    assert not bureau.a_texte("Le schéma suit la saisie")


def test_verdict_efface_apres_erreur_et_changement_d_exemple(bureau):
    _poutres(bureau)
    bureau.clique("Calculer")
    assert state.v["Beam_etat"][1] is True
    bureau.saisit("Fibre extrême |y|max (mm)", "0")  # fibre extrême nulle : calcul impossible
    bureau.clique("Calculer")
    assert "Beam_etat" not in state.v and state.result("Beam") is None
    _charge(bureau, "isostatique")
    bureau.clique("Calculer")
    assert "Beam_etat" in state.v
    _charge(bureau, "console")
    bureau.page.rafraichirTout()
    assert "Beam_etat" not in state.v


def test_eurocode_non_pondere_jamais_vert(bureau):
    _poutres(bureau)
    bureau.ouvre_volet(VOLET_EC3)
    bureau.choisit("Efforts de calcul", "Dernier « Calculer » (non pondéré, indicatif)")
    bureau.saisit("Lcr : longueur entre maintiens latéraux (m, 0 = L)", "1")
    bureau.clique("Vérifier selon l'Eurocode 3")
    texte, ok, cle = state.v["Beam_etat"]
    assert cle == "BeamEC3" and ok is not True and "(vérifié)" not in texte


def test_volet_section_dessine_la_section_utilisee(bureau):
    from PySide6.QtWidgets import QWidget

    from mecastruct.bureau.widgets import VueFigure

    _poutres(bureau)
    assert state.saisie("Beam")["section"] is not None
    gauche = bureau.page.sections[1]
    assert [w for w in gauche.findChildren(VueFigure)], "aucun dessin de section dans le volet Section"
    bureau.saisit("S (mm²)", "5000")  # valeurs saisies à la main : plus de forme, donc plus de dessin
    assert not gauche.findChildren(VueFigure)
    _ = QWidget
