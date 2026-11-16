"""Le bureau a la forme du site : mêmes familles, mêmes noms de pages et même ordre (docs/app.js est la référence)."""

import re
from pathlib import Path

import main
from mecastruct.services.pages_texte import FAMILLES, INTROS

APP_JS = (Path(__file__).resolve().parents[2] / "docs" / "app.js").read_text(encoding="utf-8")
# écarts voulus : le train épicycloïdal est un onglet d'Engrenages sur le site mais une page sur le bureau ;
# « À propos » est en pied de page sur le site
SEULEMENT_BUREAU = {"Trains épicycloïdaux", "À propos"}


def menu_du_bureau() -> dict[str, list[str]]:
    familles: dict[str, list[str]] = {}
    for ident, libelle, _ in main.MENU:
        if libelle is None:
            familles[ident] = []
            courante = ident
        elif ident != "accueil":
            familles[courante].append(libelle)
    return familles


def menu_du_site() -> dict[str, list[str]]:
    familles = {m[1]: [] for m in re.findall(r'\{ id: "([a-z]+)", titre: "([^"]+)", texte: "[^"]*" \}', APP_JS)}
    ids = {m[0]: m[1] for m in re.findall(r'\{ id: "([a-z]+)", titre: "([^"]+)", texte', APP_JS)}
    for titre, famille in re.findall(r'\{ id: "[a-z-]+", titre: "([^"]+)", famille: "([a-z]+)"', APP_JS):
        familles[ids[famille]].append(titre)
    return familles


def test_memes_familles_dans_le_meme_ordre():
    assert list(menu_du_bureau()) == list(menu_du_site())


def test_memes_pages_dans_le_meme_ordre():
    bureau = {f: [p for p in pages if p not in SEULEMENT_BUREAU] for f, pages in menu_du_bureau().items()}
    assert bureau == menu_du_site()


def test_les_phrases_sous_les_titres_sont_celles_du_site():
    for titre, texte in re.findall(r'titre: "([^"]+)"[^\n]*? texte: "([^"]+)" \}', APP_JS):
        if titre in INTROS:
            assert INTROS[titre] == texte.replace("\'", "'") or titre in {"Treillis", "Engrenages"}, titre


def test_les_phrases_des_familles_sont_celles_du_site():
    for titre, texte in re.findall(r'\{ id: "[a-z]+", titre: "([^"]+)", texte: "([^"]+)" \}', APP_JS):
        if titre in FAMILLES:
            assert FAMILLES[titre] == texte, titre
