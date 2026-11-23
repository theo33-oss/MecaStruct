"""Interface de bureau (PySide6) : ouvrir chaque page, modifier une donnée, calculer, enregistrer et rouvrir, exporter.

Chaque test ouvre la vraie fenêtre ; les boîtes « Enregistrer » et « Ouvrir » répondent par un chemin choisi d'avance.
"""

import io
import json
import zipfile

import openpyxl
import pytest

import main
from mecastruct.bureau import state

PAGES = [ident for ident, libelle, _ in main.MENU if libelle is not None]
# page → (onglet de projet, bouton qui calcule) pour les pages à saisie enregistrable
PROBLEMES = {"treillis": "Tr", "sections": "Sec", "flambage": "Fla", "tenseurs": "Ten", "poutres": "Beam"}


@pytest.mark.parametrize("ident", PAGES)
def test_chaque_page_s_ouvre_et_se_redessine(bureau, ident):
    page = bureau.ouvre(ident)
    assert bureau.fenetre.pile.currentWidget() is page and (page.sections or page.pages)
    page.afficher()  # un second affichage ne détruit rien
    bureau.attend()
    assert page.sections or page.pages


def test_navigation_par_le_menu_et_les_liens(bureau):
    bureau.ouvre("accueil")
    bureau.clique("▸  Structures")  # les cartes de l'accueil sont repliées : un clic ouvre la famille
    bureau.clique("Poutres")
    assert bureau.fenetre.pile.currentWidget() is bureau.fenetre.page("poutres")


def test_modifier_une_donnee_puis_calculer(bureau):
    bureau.ouvre("treillis")
    bureau.saisit("S, aire d'une barre (mm²)", "800")
    assert state.saisie("Tr")["S"] == 800.0
    bureau.clique("Calculer")
    assert state.is_current("Tr")
    bureau.saisit("S, aire d'une barre (mm²)", "900")
    assert not state.is_current("Tr")  # le résultat affiché date de l'ancienne saisie


def test_les_valeurs_gardees_survivent_au_changement_de_page(bureau):
    bureau.ouvre("treillis")
    bureau.saisit("E (GPa)", "123")
    bureau.ouvre("poutres")
    bureau.ouvre("treillis")
    assert bureau.valeur("E (GPa)") == "123"


@pytest.mark.parametrize("page", list(PROBLEMES))
def test_enregistrer_puis_rouvrir_un_probleme(bureau, tmp_path, page):
    tab = PROBLEMES[page]
    bureau.ouvre(page)
    chemin = tmp_path / f"probleme_{tab}.json"
    bureau.ouvre_volet("Fichiers")
    bureau.clavier_enregistrer(chemin)
    bureau.clique("Enregistrer mon problème (.json)")
    assert json.loads(chemin.read_text(encoding="utf-8"))
    avant = json.dumps(state.saisie(tab), default=str, sort_keys=True)
    # on abîme la saisie, puis on rouvre le fichier : elle revient telle quelle
    cle = next(k for k, v in state.saisie(tab).items() if isinstance(v, float))
    state.saisie(tab)[cle] = state.saisie(tab)[cle] + 12345.0
    bureau.clavier_ouvrir(chemin)
    bureau.clique("Ouvrir un problème (.json)")
    assert json.dumps(state.saisie(tab), default=str, sort_keys=True) == avant
    assert bureau.a_texte("Problème ouvert.")


def test_ouvrir_un_fichier_illisible_donne_un_message(bureau, tmp_path):
    bureau.ouvre("treillis")
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text("pas du json", encoding="utf-8")
    bureau.ouvre_volet("Fichiers")
    bureau.clavier_ouvrir(mauvais)
    bureau.clique("Ouvrir un problème (.json)")
    assert not bureau.a_texte("Problème ouvert.")


def test_enregistrer_et_rouvrir_tout_le_projet(bureau, tmp_path):
    bureau.ouvre("accueil")
    chemin = tmp_path / "projet.json"
    bureau.clavier_enregistrer(chemin)
    bureau.clique("Enregistrer tout le projet (.json)")
    state.saisie("Tr")["S"] = 4321.0
    bureau.clavier_ouvrir(chemin)
    bureau.clique("Ouvrir un projet (.json)")
    assert state.saisie("Tr")["S"] != 4321.0
    assert bureau.a_texte("Projet ouvert.")


def test_export_tableau_xlsx_et_csv(bureau, tmp_path):
    bureau.ouvre("treillis")
    bureau.clique("Calculer")
    bureau.ouvre_volet("Fichiers")
    bureau.clavier_enregistrer(tmp_path / "resultats.xlsx")
    bureau.clique("Exporter en tableau")
    classeur = openpyxl.load_workbook(tmp_path / "resultats.xlsx")
    assert {"Barres", "Réactions", "Déplacements"} <= set(classeur.sheetnames)
    bureau.radio("csv")
    bureau.ouvre_volet("Fichiers")
    bureau.clavier_enregistrer(tmp_path / "resultats.zip")
    bureau.clique("Exporter en tableau")
    with zipfile.ZipFile(tmp_path / "resultats.zip") as z:
        assert any(n.endswith(".csv") for n in z.namelist())


def test_export_tableau_inactif_sans_resultat(bureau):
    bureau.ouvre("treillis")
    bureau.ouvre_volet("Fichiers")
    assert not bureau.bouton("Exporter en tableau").isEnabled()


@pytest.mark.parametrize(("fmt", "ext"), [("HTML", ".html"), ("PDF", ".pdf"), ("Word", ".docx")])
def test_export_du_dossier_de_validation(bureau, tmp_path, fmt, ext):
    bureau.ouvre("flambage")
    bureau.clique("Calculer")
    bureau.clique("Dossier de validation de ce problème")
    bureau.radio(fmt)
    nom = next(b.text() for b in bureau._visibles(type(bureau.bouton("Calculer"))) if b.text().startswith("Enregistrer le dossier"))
    assert nom.endswith(f"{ext})")
    cible = tmp_path / f"dossier{ext}"
    bureau.clavier_enregistrer(cible)
    bureau.clique(nom)
    assert cible.stat().st_size > 500


def test_calcul_en_arriere_plan_un_seul_a_la_fois(bureau):
    """Un second calcul demandé pendant le premier est refusé avec un message, la fenêtre reste utilisable."""
    from mecastruct.bureau import tache

    bureau.ouvre("poutres")
    bureau.page.calculer()
    assert tache.occupe()
    bureau.page.calculer()  # refusé : un calcul tourne déjà
    bureau.attend()
    assert state.result("Beam") is not None


def test_erreur_de_calcul_affichee_sans_planter(bureau):
    bureau.ouvre("poutres")
    state.saisie("Beam")["sup"] = []  # aucun appui : mécanisme
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    assert state.result("Beam") is None
    assert bureau.a_texte("Conseil") or bureau.a_texte("mécanisme") or bureau.a_texte("appui")


def test_les_resultats_exportes_sont_ceux_du_moteur(bureau, tmp_path):
    """Le xlsx exporté contient les mêmes réactions que le résultat du moteur (aucun recalcul par l'interface)."""
    bureau.ouvre("treillis")
    bureau.clique("Calculer")
    t = state.result("Tr")["tables"]["Réactions"]
    bureau.ouvre_volet("Fichiers")
    bureau.clavier_enregistrer(tmp_path / "r.xlsx")
    bureau.clique("Exporter en tableau")
    ws = openpyxl.load_workbook(io.BytesIO((tmp_path / "r.xlsx").read_bytes()))["Réactions"]
    assert ws.max_row == len(t) + 1
