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
    if f.get("apercu"):
        a = appel(ident + ".apercu", f["defaut"])
        assert a["ok"] and a["sortie"]["data"], a.get("erreur")


@pytest.mark.parametrize("ident", sorted(FORMULAIRES))
def test_les_champs_couvrent_la_saisie(ident):
    """Chaque valeur de départ a son champ, et chaque champ a sa valeur de départ (sinon la page perd une donnée)."""
    f = FORMULAIRES[ident]
    champs = {c["id"] for g in f["groupes"] for c in g["champs"] if c["type"] != "action"} | set(f.get("caches", []))
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
