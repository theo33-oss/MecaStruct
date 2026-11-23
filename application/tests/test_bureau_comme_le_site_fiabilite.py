"""Corrections de fiabilité du site reprises dans le bureau : bornes de Poutres, mécanisme, convertisseur, matériaux."""

import copy
import json

import pytest

from mecastruct import pont
from mecastruct.bureau import state
from mecastruct.bureau.pages import base_de_donnees, convertisseur
from mecastruct.bureau.pages import poutres as page_poutres
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import beam_services

pont.charger("structures")
DEFAUT = json.loads(pont.appeler("formulaires"))["sortie"]["beam"]["defaut"]
DM = DataManager()


def _poutre_vide():
    s = copy.deepcopy(DEFAUT)
    for cle in ("sup", "supx", "hg", "pl", "pm", "dl"):
        s[cle] = []
    s["combo"] = [{"name": "ELU", "gG": 1.35, "gQ": 1.5, "gW": 0.0, "gS": 0.0}]
    return s


@pytest.mark.parametrize(("cle", "valeur", "mot"), [("L", 0, "longueur"), ("L", -2, "longueur"), ("E", 0, "Young"),
                                                     ("G", -1, "cisaillement"), ("Re", 0, "élastique"), ("Kt", 0.5, "Kt")])
def test_poutre_refuse_les_bornes_avec_un_message_clair(cle, valeur, mot):
    s = copy.deepcopy(DEFAUT)
    s[cle] = valeur
    with pytest.raises(MecaStructError) as e:
        beam_services.computeBeam(s, DM)
    assert mot in e.value.message and "model." not in e.value.message


def test_poutre_de_l_exemple_et_kt_egal_un_se_calculent():
    s = copy.deepcopy(DEFAUT)
    s["Kt"] = 1.0
    assert beam_services.computeBeam(s, DM)["status"]


def test_combinaisons_et_profile_disent_mecanisme():
    s = _poutre_vide()
    with pytest.raises(MecaStructError) as e:
        page_poutres._combinaisons(s, DM)
    assert "Mécanisme" in e.value.message and "nan" not in e.value.message
    with pytest.raises(MecaStructError) as e:
        page_poutres._plus_leger(s, DM)
    assert "Mécanisme" in e.value.message
    T = page_poutres._combinaisons(copy.deepcopy(DEFAUT), DM)  # la poutre de l'exemple se calcule
    assert len(T) >= 2


def test_convertisseur_refuse_sous_le_zero_absolu_et_les_valeurs_trop_grandes():
    with pytest.raises(MecaStructError, match="zéro absolu"):
        convertisseur.convertir(-1000, "Température absolue", "°C", "K")
    assert convertisseur.convertir(-273.15, "Température absolue", "°C", "K") == pytest.approx(0.0, abs=1e-9)
    assert convertisseur.convertir(-459.67, "Température absolue", "°F", "K") == pytest.approx(0.0, abs=1e-6)
    with pytest.raises(MecaStructError, match="trop grande"):
        convertisseur.convertir(1e308, "Longueur", "m", "mm")


def test_page_convertisseur_affiche_le_refus(bureau):
    bureau.ouvre("convertisseur")
    bureau.choisit("Grandeur", "Température absolue")
    bureau.choisit("De", "°C")
    bureau.choisit("Vers", "K")
    bureau.saisit("Valeur", "-1000")
    assert bureau.a_texte("zéro absolu")


def test_recherche_de_materiau_rognee_et_aucune_categorie():
    T = DM.Materials
    cats = sorted(T["Category"].dropna().unique())
    assert len(base_de_donnees.filtre_materiaux(T, cats, "")) == len(T)
    assert base_de_donnees.filtre_materiaux(T, [], "").empty  # aucune catégorie cochée : rien, pas « tout »
    nom = T["Name"].iloc[0]
    assert not base_de_donnees.filtre_materiaux(T, cats, f"  {nom}  ").empty


def test_suppression_de_materiau_demande_confirmation(bureau, monkeypatch):
    bureau.ouvre("base_de_donnees")
    bureau.clique("Ajouter / remplacer")
    monkeypatch.setattr(base_de_donnees, "_confirme", lambda parent, texte: False)
    bureau.clique("Supprimer le matériau utilisateur choisi")
    assert "Acier utilisateur" in state.dm().listMaterials()  # refusé : rien n'est supprimé
    monkeypatch.setattr(base_de_donnees, "_confirme", lambda parent, texte: True)
    bureau.clique("Supprimer le matériau utilisateur choisi")
    assert "Acier utilisateur" not in state.dm().listMaterials()


def test_annuler_apres_charger_l_exemple_et_profile_affiche(bureau):
    bureau.ouvre("poutres")
    bureau.clique("Charger l'exemple")
    assert bureau.a_texte("Section utilisée : ")
    bureau.saisit("Longueur L (m)", "7")
    bureau.clique("↶ Annuler")
    assert state.saisie("Beam")["L"] != 7.0
