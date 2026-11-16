"""Tests des pages « Base de données » et « Convertisseur » : exécution, conversion, ajout d'un matériau."""

import json

from mecastruct.bureau import state


def test_base_de_donnees_s_ouvre(bureau):
    bureau.ouvre("base_de_donnees")
    assert bureau.onglets()[:3] == ["Matériaux", "Profilés", "Pressions de matage"]


def test_convertisseur_s_ouvre(bureau):
    bureau.ouvre("convertisseur")
    assert bureau.a_texte("Unités attendues dans les champs")


def test_convertisseur_pouces_en_millimetres(bureau):
    bureau.ouvre("convertisseur")
    bureau.choisit("Grandeur", "Longueur")
    bureau.choisit("De", "in")
    bureau.choisit("Vers", "mm")
    assert bureau.a_texte("25,4 mm")


def test_convertisseur_inverser_et_valeur(bureau):
    bureau.ouvre("convertisseur")
    bureau.choisit("Grandeur", "Longueur")
    bureau.choisit("De", "in")
    bureau.choisit("Vers", "mm")
    bureau.clique("Inverser")
    assert state.v["conv.de"] == "mm" and state.v["conv.vers"] == "in"
    bureau.saisit("Valeur", "50,8")
    assert bureau.a_texte("2 in")


def test_base_ajoute_un_materiau(bureau):
    bureau.ouvre("base_de_donnees")
    bureau.clique("Ajouter / remplacer")
    assert "Acier utilisateur" in state.dm().listMaterials()
    assert bureau.a_texte("Matériau « Acier utilisateur » ajouté.")


def test_base_supprime_un_materiau_utilisateur(bureau):
    bureau.ouvre("base_de_donnees")
    bureau.clique("Ajouter / remplacer")
    bureau.clique("Supprimer le matériau utilisateur choisi")
    assert "Acier utilisateur" not in state.dm().listMaterials()


def test_base_enregistre_puis_recharge_ses_ajouts(bureau, tmp_path):
    bureau.ouvre("base_de_donnees")
    bureau.clique("Ajouter / remplacer")
    bureau.onglet("Mes données")
    fichier = tmp_path / "ajouts.json"
    bureau.clavier_enregistrer(fichier)
    bureau.clique("Enregistrer mes ajouts (.json)")
    assert "Acier utilisateur" in json.dumps(json.loads(fichier.read_text(encoding="utf-8")), ensure_ascii=False)
    state.dm().removeMaterial("Acier utilisateur")
    bureau.clavier_ouvrir(fichier)
    bureau.clique("Recharger mes ajouts (.json)")
    bureau.clique("Importer ce fichier")
    assert "Acier utilisateur" in state.dm().listMaterials()


def test_base_documents_enregistrables(bureau, tmp_path):
    bureau.ouvre("base_de_donnees")
    bureau.onglet("Documents")
    cible = tmp_path / "note.html"
    bureau.clavier_enregistrer(cible)
    bureau.clique("Enregistrer : Note de calcul")
    assert cible.stat().st_size > 1000
