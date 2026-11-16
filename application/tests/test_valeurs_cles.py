"""Valeurs clés et « Formulaire rapide » partagés entre le bureau et le site (1.5.0)."""

import json

import pytest

from mecastruct.pont import noyau
from mecastruct.services import fiches, valeurs_cles

noyau.charger("structures")
FORMULAIRES = noyau.tous_formulaires()


def appel(ident, saisie=None):
    r = json.loads(noyau.appeler(ident, json.dumps(FORMULAIRES[ident]["defaut"] if saisie is None else saisie)))
    assert r["ok"], r.get("erreur")
    return r["sortie"]


def test_valeurs_cles_d_une_ligne_d_etat():
    cartes = valeurs_cles.valeurs("σI = 87.08 MPa, σIII = -47.08 MPa — VM = 116.2 MPa (vérifié)")
    assert [(c["label"], c["value"]) for c in cartes] == [("σI", "87.08 MPa"), ("σIII", "-47.08 MPa"), ("VM", "116.2 MPa")]
    assert cartes[2]["delta"] == "vérifié" and cartes[2]["delta_color"] == "green" and "delta" not in cartes[0]
    assert valeurs_cles.valeurs("Clavette : longueur minimale Lmin = 41.2 mm") == []
    ko = valeurs_cles.valeurs("h = 0 (isostatique) — P = 12.5 kN : NON vérifié")
    assert ko[0]["delta"] == "isostatique" and ko[1]["delta_color"] == "red"


def test_le_bureau_utilise_le_meme_analyseur():
    from mecastruct.bureau.page_calcul import synthese_statut

    class Espion:
        def __init__(self):
            self.valeurs = []

        def synthese(self, v):
            self.valeurs.extend(v)

    z = Espion()
    ligne = "σmax = 159.2 MPa (NON vérifié) — ΔL = 0.7579 mm"
    synthese_statut(z, ligne)
    assert z.valeurs == valeurs_cles.valeurs(ligne)


@pytest.mark.parametrize("ident", ["tra", "cis", "tor", "fle", "fla", "ten", "fre", "pal", "rlt", "eng", "truss"])
def test_chaque_calcul_donne_ses_cartes(ident):
    s = appel(ident)
    assert s["valeurs"], ident
    assert all({"label", "value"} <= set(c) for c in s["valeurs"])


def test_cartes_du_treillis_en_toutes_lettres():
    cartes = appel("truss")["valeurs"]
    assert [c["label"] for c in cartes][:2] == ["h", "|N|max"] and cartes[0]["delta"] == "isostatique"


def test_fiches_de_formules():
    r = fiches.fiche("tenseurs")
    assert len(r["cles"]) == 19 and r["cle"] == "tenseurs" and r["fiches"]
    assert all(f["titre"] and f["latex"].startswith("$") for f in r["fiches"])
    assert fiches.fiche("n'importe quoi")["cle"] == r["cles"][0]["id"]  # clé inconnue : première fiche
    sortie = appel("fiche", {"cle": "flexion"})
    assert sortie["cle"] == "flexion" and sortie["cles"][0]["titre"] == "Matériaux"


def test_chaque_formulaire_de_rdm_a_sa_fiche():
    attendu = {"beam": "equilibre", "truss": "treillis", "sec": "geometrie", "tra": "traction", "cis": "cisaillement",
               "tor": "torsion", "fle": "flexion", "fla": "flambage", "ten": "tenseurs", "hoo": "hooke", "jau": "extensometrie"}  # fmt: skip
    cles = {c["id"] for c in fiches.fiche()["cles"]}
    for ident, cle in attendu.items():
        assert FORMULAIRES[ident]["fiche"] == cle and cle in cles
    for ident in ("rlt", "eng", "mot", "fre", "ossature"):
        assert FORMULAIRES[ident]["fiche"] is None  # pas de fiche pour les machines, comme au bureau
