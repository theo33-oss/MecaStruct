"""Pont web : chaque calcul rend du JSON valide, les mêmes nombres que le service, et la page connaît ses calculs."""

import json
import re
from pathlib import Path

import pytest

from mecastruct import pont
from mecastruct.pont.noyau import nombreFr
from mecastruct.services import machine
from mecastruct.services import machine_courses as mc

DOCS = Path(__file__).resolve().parents[2] / "docs"
pont.charger("structures")
FORMULAIRES = json.loads(pont.appeler("formulaires"))["sortie"]


def appel(ident, saisie=None):
    return json.loads(pont.appeler(ident, json.dumps(saisie if saisie is not None else {})))


@pytest.mark.parametrize("ident", sorted(FORMULAIRES))
def test_chaque_calcul_repond_avec_ses_valeurs_de_depart(ident):
    f = FORMULAIRES[ident]
    r = appel(ident, f["defaut"])
    assert r["ok"], r.get("erreur")
    assert r["sortie"]["status"]
    if f.get("dossier"):  # pages de structure : chaque graphique se dessine, les explications sont là
        attendus = {"tra": 2, "cis": 3, "tor": 2, "fle": 2, "fla": 2, "ten": 3, "hoo": 1, "jau": 2, "sec": 2, "beam": 3, "truss": 1}
        assert len(r["sortie"]["figures"]) == attendus[ident]
        assert r["sortie"]["explications"]
    if f.get("apercu"):
        a = appel(ident + ".apercu", f["defaut"])
        assert a["ok"] and a["sortie"]["data"], a.get("erreur")


@pytest.mark.parametrize("ident", sorted(FORMULAIRES))
def test_les_champs_couvrent_la_saisie(ident):
    """Chaque valeur de départ a son champ, et chaque champ a sa valeur de départ (sinon la page perd une donnée)."""
    f = FORMULAIRES[ident]
    boutons = ("action", "bouton")
    champs = {c["id"] for g in f["groupes"] for c in g["champs"] if c["type"] not in boutons} | set(f.get("caches", []))
    assert champs == set(f["defaut"]), champs ^ set(f["defaut"])


@pytest.mark.parametrize(
    ("ident", "service"),
    [
        ("aju", lambda s: machine.computeFit(s)),
        ("pal", lambda s: machine.computeBearing(s)),
        ("rlt", lambda s: mc.computeBearingLife(s)),
        ("eng", lambda s: mc.computeGearMesh(s, pont.noyau.dm())),
        ("mot", lambda s: mc.computeMotor(s)),
    ],
)
def test_memes_resultats_que_le_service(ident, service):
    s = FORMULAIRES[ident]["defaut"]
    attendu = service(s)
    sortie = appel(ident, s)["sortie"]
    assert sortie["status"] == attendu["status"]
    assert sortie["ok"] == attendu["ok"]
    assert sortie["latex"] == list(attendu["result"]["latex"])


@pytest.mark.parametrize("ident", ["beam", "sec", "cis"])
def test_dossier_de_validation(ident):
    r = appel(ident + ".dossier", FORMULAIRES[ident]["defaut"])
    assert r["ok"], r.get("erreur")
    assert r["sortie"]["nom"].endswith(".html") and "<html" in r["sortie"]["html"].lower()


def test_fichier_de_probleme_identique_au_bureau_et_aller_retour():
    """Le fichier enregistré sur le site est celui du bureau (project_io) : il se relit des deux côtés."""
    from mecastruct.services import project_io

    s = {**FORMULAIRES["beam"]["defaut"], "L": 7.5}
    f = appel("beam.enregistrer", s)["sortie"]
    assert project_io.problemFromJson(f["texte"], "Beam")[1]["L"] == 7.5  # lu par le bureau
    assert appel("beam.ouvrir", {"texte": f["texte"]})["sortie"]["L"] == 7.5  # relu par le site
    assert not appel("truss.ouvrir", {"texte": f["texte"]})["ok"]  # fichier d'une autre page : refusé
    assert not appel("beam.ouvrir", {"texte": f["texte"].replace('"L": 7.5', '"L": "=1+1"')})["ok"]  # genre faux


def test_etude_de_machine_aller_retour_et_refus():
    s = {**FORMULAIRES["aju"]["defaut"], "d": 40.0}
    texte = appel("machine.enregistrer", {"ident": "aju", "saisie": s})["sortie"]["texte"]
    assert appel("machine.ouvrir", {"ident": "aju", "texte": texte})["sortie"]["d"] == 40.0
    assert not appel("machine.ouvrir", {"ident": "fre", "texte": texte})["ok"]
    assert not appel("machine.ouvrir", {"ident": "aju", "texte": texte.replace('"d"', '"inconnu"')})["ok"]
    assert not appel("machine.ouvrir", {"ident": "aju", "texte": "x" * 300_000})["ok"]


def test_export_excel():
    import base64

    r = appel("tra.excel", FORMULAIRES["tra"]["defaut"])
    assert r["ok"], r.get("erreur")
    assert base64.b64decode(r["sortie"]["base64"])[:2] == b"PK"


def test_erreur_lisible_et_calcul_inconnu():
    r = appel("aju", {**FORMULAIRES["aju"]["defaut"], "d": -5})
    assert not r["ok"] and "ISO 286" in r["erreur"]
    assert not appel("inexistant")["ok"]


def test_regles_de_montage_suivent_la_bague():
    r = appel("rlt_regle", {"bague": "extérieure", "rotation": "n'existe pas", "charge": ""})["sortie"]
    assert r["saisie"]["rotation"] in r["options"]["rotation"]
    assert "extérieure" in r["status"]


def test_convertisseur():
    g = appel("conv.catalogue")["sortie"]["grandeurs"][0]
    r = appel("conv", {"grandeur": g["nom"], "valeur": 2, "de": g["unites"][g["de"]], "vers": g["unites"][g["vers"]]})
    assert r["ok"] and r["sortie"]["tableau"]["lignes"]


def test_nombres_a_la_francaise():
    assert nombreFr(1234.5) == "1 234,5"
    assert nombreFr(-0.00012) == "−0,00012"
    assert nombreFr(float("nan")) == "–"
    assert nombreFr(3.0) == "3"


def test_la_page_ne_demande_que_des_calculs_existants():
    """Les identifiants « calculs » des pages de docs/app.js existent tous dans le pont."""
    app = (DOCS / "app.js").read_text(encoding="utf-8")
    demandes = {c for bloc in re.findall(r"calculs: \[([^\]]*)\]", app) for c in re.findall(r'"([\w.]+)"', bloc)}
    assert demandes, "aucune page de calcul trouvée dans app.js"
    assert demandes <= set(json.loads(pont.catalogue()))
