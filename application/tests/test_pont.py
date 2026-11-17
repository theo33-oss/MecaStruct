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
    boutons = ("action", "bouton", "extra", "transfert", "figure")
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
    # ajustement : aucune limite n'est comparée, le site n'écrit donc pas « vérifié » (audit utilisateur)
    assert sortie["ok"] == (None if ident == "aju" else attendu["ok"])
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


@pytest.mark.parametrize("ident", ["beam.combos", "beam.ec3", "beam.fatigue", "beam.mobile", "beam.leger"])
def test_calculs_complementaires_de_poutres(ident):
    r = appel(ident, FORMULAIRES["beam"]["defaut"])
    assert r["ok"], r.get("erreur")
    assert r["sortie"]["status"] and r["sortie"]["tables"]


def test_les_boutons_de_calcul_complementaire_existent():
    """Chaque bouton « extra » d'un formulaire désigne un calcul du pont."""
    calculs = set(json.loads(pont.catalogue()))
    boutons = {c["calcul"] for f in FORMULAIRES.values() for g in f["groupes"] for c in g["champs"] if c["type"] in ("extra", "bouton", "action", "transfert")}
    assert boutons <= calculs, boutons - calculs


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


def test_ossature_3d_tous_les_exemples_sont_a_l_equilibre():
    from mecastruct.services import ossature3d

    f = FORMULAIRES["ossature"]
    for nom in f["exemples"]:
        e = appel("ossature.exemple", {"nom": nom})["sortie"]
        r = appel("ossature", {**f["defaut"], **e})
        assert r["ok"], f"{nom} : {r.get('erreur')}"
        assert r["sortie"]["ok"] is None and "Équilibre global vérifié" in r["sortie"]["status"], nom  # équilibre juste, pas de verdict de résistance
    assert set(f["exemples"]) == set(ossature3d.exemples(pont.noyau.dm()))


def test_ossature_3d_console_flexion_theorique():
    """Console IPE 200 de 2 m, 10 kN en bout : flèche P·L³/(3·E·I) = 6,535 mm."""
    f = FORMULAIRES["ossature"]
    e = appel("ossature.exemple", {"nom": "Console"})["sortie"]
    s = appel("ossature", {**f["defaut"], **e, "pp": False})["sortie"]  # sans poids propre : le calcul à la main n'en a pas
    assert "6,535 mm" in s["metriques"][0][1].replace(".", ",")


def test_ossature_3d_erreurs_lisibles():
    f = FORMULAIRES["ossature"]
    r = appel("ossature", {**f["defaut"], "noeuds": [], "pieces": []})
    assert not r["ok"] and "nœud" in r["erreur"]
    m = {**f["defaut"], "noeuds": [{"id": 1, "x": 0, "y": 0, "z": 0, "appui": "libre", "ddl": ""}, {"id": 2, "x": 1000, "y": 0, "z": 0, "appui": "libre", "ddl": ""}]}
    assert not appel("ossature", m)["ok"]  # structure libre : mécanisme, message en français


def test_transferts_entre_pages_comme_le_bureau():
    from mecastruct.core.data_manager import DataManager
    from mecastruct.services import beam_design, beam_services, compute

    dm = DataManager()
    sec, beam = FORMULAIRES["sec"]["defaut"], FORMULAIRES["beam"]["defaut"]
    t = appel("transfert.section", {"sec": sec, "beam": beam})["sortie"]
    res = compute.computeSection(sec, dm)["result"]
    attendu = beam_design.sectionToBeamInput(beam, res["sec"], res["P"], dm.getMaterial(sec["mat"]))
    assert abs(t["beam"]["Iz"] - attendu["Iz"]) < 1e-6 * attendu["Iz"] and t["beam"]["mat"] == sec["mat"]
    assert t["fla"]["S"] == t["beam"]["S"] and "Sections" in t["info"]
    # la saisie transmise reste calculable (la section a fait l'aller-retour JSON)
    assert appel("beam", t["beam"])["ok"]
    # efforts de la poutre → Sections, en s puis au point le plus sollicité
    e = appel("transfert.efforts", {"beam": beam, "cible": {**sec, "s0": 2.0}, "key": "Sec", "mode": "abscisse"})["sortie"]
    ref = beam_design.loadFromBeam({**sec, "s0": 2.0}, beam_services.computeBeam(beam, dm), "Sec", "abscisse")
    assert abs(e["cible"]["Mfz"] - ref["Mfz"]) < 1e-9 and e["cible"]["s0"] == 2.0
    assert appel("transfert.efforts", {"beam": beam, "cible": {**sec, "s0": 99.0}, "key": "Sec", "mode": "abscisse"})["ok"] is False
    # poutre → tenseurs : σxx seul non nul
    ten = appel("transfert.tenseur", {"beam": beam})["sortie"]["ten"]
    assert ten["sig"][0][0] != 0 and ten["sig"][1][1] == 0 and ten["mat"] == beam["mat"]
    assert appel("ten", {**FORMULAIRES["ten"]["defaut"], **ten})["ok"]
    # section → cisaillement, flexion
    c = appel("transfert.section_seule", {"sec": sec})["sortie"]["cible"]
    assert appel("fle", {**FORMULAIRES["fle"]["defaut"], **c})["ok"]


def test_abaques_kt_comme_le_bureau():
    from mecastruct.core import kt_mohr

    cat = appel("kt.catalogue")["sortie"]
    assert {c["id"] for c in cat} == {c["id"] for c in kt_mohr.ktCharts()}
    r = appel("kt", {"id": "arbre_epaulement_flexion", "p1": 0.1, "p2": 1.5})["sortie"]
    assert abs(r["Kt"] - kt_mohr.evalKt("arbre_epaulement_flexion", [0.1, 1.5])) < 1e-12 and r["dansLeDomaine"]
    assert abs(appel("kt", {"id": "plaque_trou_traction", "p1": 0.3, "p2": 0})["sortie"]["Kt"] - 2.34909) < 1e-4
    assert not appel("kt", {"id": "arbre_epaulement_flexion", "p1": -1, "p2": 1.5})["ok"]


@pytest.mark.parametrize("ident", ["rlt", "rlt_ens", "eng", "trn", "epi", "frn", "emb", "mot"])
def test_dossier_de_validation_des_pages_de_machines(ident):
    """Chaque contrôle refait à la main concorde avec le solveur (aucun écart, aucune hypothèse non satisfaite)."""
    assert FORMULAIRES[ident]["dossierMachine"]
    r = appel(ident + ".dossier", FORMULAIRES[ident]["defaut"])
    assert r["ok"], r.get("erreur")
    html = r["sortie"]["html"]
    assert "contrôles de calcul concordent" in html and "écart(s) à examiner" not in html
    assert "NON satisfaite" not in html and "non exécutée" not in html


def test_schema_de_poutre_rapide_avec_une_longueur_minuscule():
    """L = 0,043 m tapé dans l'exemple (appuis et charges à 6 m) : message immédiat, plus de gel du navigateur."""
    import json
    import time

    from mecastruct.pont import noyau

    noyau.charger("structures")
    s = json.loads(json.dumps(noyau.tous_formulaires()["beam"]["defaut"]))
    for L in (0.04, 0.043):
        s["L"] = L
        t = time.time()
        r = json.loads(noyau.appeler("beam.apercu", json.dumps(s)))
        assert time.time() - t < 2
        assert not r["ok"] and "hors de la poutre" in r["erreur"]


def test_schema_de_poutre_borne_le_nombre_de_fleches():
    """Charge répartie bien plus longue que la poutre dessinée : au plus 30 flèches."""
    from mecastruct.plots import beam_plots

    modele = {"L": 0.05, "supports": [{"pos": 0.0, "type": "encastrement"}],
              "distLoads": [{"a": 0.0, "b": 0.05, "dir": "y", "coeffs": [-1000.0], "name": "q"}]}
    fig = beam_plots.beamSchematic(modele, None)
    assert len(fig.layout.annotations) < 60


def test_schema_du_filetage_pour_chaque_diametre():
    """Le schéma du filetage donne d > d2 > ds > d3 et met en avant le diamètre de calcul choisi."""
    from mecastruct.pont import noyau
    from mecastruct.pont import structures as st

    noyau.charger("structures")
    for nom in st.PAS_ISO:
        for choix, cle in (("noyau", "d3"), ("resistant", "ds")):
            t = st.tige_filetee(nom, choix)
            assert t["d"] > t["d2"] > t["ds"] > t["d3"] > 0
            r = json.loads(noyau.appeler("beam.filetage", json.dumps({"secSrc": "tige", "tigeM": nom, "tigeD": choix})))
            assert r["ok"], r
            textes = [a["text"] for a in r["sortie"]["layout"]["annotations"]]
            assert sum("← calcul" in x for x in textes) == 1
            assert any(x.startswith(f"<b>{cle} = ") for x in textes)
    vide = json.loads(noyau.appeler("beam.filetage", json.dumps({"secSrc": "forme"})))
    assert "vide" in vide["sortie"]


def test_poutre_poids_propre_coche_de_base_avec_son_schema():
    """Poutres : poids propre coché de base (page et exemples), schéma tracé avec la charge du poids propre."""
    from mecastruct.pont import noyau

    noyau.charger("structures")
    f = noyau.tous_formulaires()["beam"]
    assert f["defaut"]["selfw"] is True
    assert next(g for g in f["groupes"] if g["titre"] == "Calcul")["ouvert"] is True
    for nom in f["exemples"]:
        assert json.loads(noyau.appeler("beam.exemple", json.dumps({"nom": nom})))["sortie"]["selfw"] is True
    r = json.loads(noyau.appeler("beam.apercu", json.dumps(f["defaut"])))
    assert r["ok"] and r["sortie"]["data"]


def test_filetages_iso_du_tableau_h7g6():
    """Le tableau (M3 à M72, pas gros et fins) donne d2, d3 ; As = π·ds²/4 retrouve la section du tableau à 1 % près."""
    from mecastruct.pont import structures

    assert len(structures.FILETAGES) == 40 and "M72" in structures.FILETAGES and "M10x1.25" in structures.FILETAGES
    for nom, v in structures.FILETAGES.items():
        t = structures.tige_filetee(nom, "resistant")
        assert t["d"] > t["d2"] > t["ds"] > t["d3"] > 0, nom
        assert abs(t["As"] - v["As_table"]) <= 0.01 * v["As_table"], (nom, t["As"], v["As_table"])
    assert abs(structures.tige_filetee("M10", "noyau")["D"] - 8.16) < 1e-9


def test_force_inclinee_dans_le_formulaire_et_le_schema():
    """Poutres : colonnes F et α du tableau des forces ; une force inclinée est dessinée par une seule flèche."""
    from mecastruct.pont import noyau

    noyau.charger("structures")
    f = noyau.tous_formulaires()["beam"]
    pl = next(c for g in f["groupes"] for c in g["champs"] if c["id"] == "pl")
    assert pl["polaire"]["plans"] == ["xy", "xz"] and {"F", "plan", "ang"} <= {k["id"] for k in pl["colonnes"]}
    s = json.loads(json.dumps(f["defaut"]))
    s["pl"] = [{"pos": 1.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "F": 10.0, "ang": -30.0, "name": "C", "case": "G"}]
    r = json.loads(noyau.appeler("beam.apercu", json.dumps(s)))
    assert r["ok"]
    textes = json.dumps(r["sortie"]["data"], ensure_ascii=False) + json.dumps(r["sortie"].get("layout", {}), ensure_ascii=False)
    assert "F = 10 kN à -30" in textes.replace("−", "-")


def test_force_inclinee_de_l_ossature_3d_dans_n_importe_quel_plan():
    """Ossature 3D : F, plan et α remplissent Fx, Fy, Fz ; mêmes déplacements qu'avec les composantes saisies."""
    import numpy as np

    from mecastruct.core import frame3d
    from mecastruct.pont import noyau, structures
    from mecastruct.services import ossature3d

    noyau.charger("structures")
    f = noyau.tous_formulaires()["ossature"]
    cn = next(c for g in f["groupes"] for c in g["champs"] if c["id"] == "charges_nodales")
    assert cn["polaire"]["plans"] == ["xy", "xz", "yz"] and {"F", "plan", "ang"} <= {k["id"] for k in cn["colonnes"]}
    base = json.loads(json.dumps(f["defaut"]))
    noeud = base["noeuds"][-1]["id"]

    def deplacements(ligne):
        s = {**base, "charges_nodales": [ligne]}
        data = ossature3d._donnees(structures._tables_3d(s), False, structures.dm())
        u = frame3d.solveFrame3D(data)["deplacements"]
        return np.array([u[k] for k in sorted(u)], dtype=float)

    incline = {"noeud": noeud, "Fx": 7.0, "Fy": 7.0, "Fz": 7.0, "F": 1000.0, "plan": "yz", "ang": -90.0}
    direct = {"noeud": noeud, "Fx": 0.0, "Fy": 0.0, "Fz": -1000.0}
    assert np.allclose(deplacements(incline), deplacements(direct), rtol=1e-9, atol=1e-15)


def test_ossature_3d_lignes_avec_et_sans_force_inclinee():
    """Une ligne d'exemple sans colonnes F, plan, α à côté d'une ligne inclinée : pas de NaN dans les composantes."""
    from mecastruct.pont import structures

    s = {"charges_nodales": [{"noeud": 1, "Fx": 5.0},
                             {"noeud": 2, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "F": 100.0, "plan": "xz", "ang": 90.0}]}
    c = structures._tables_3d(s)["charges_nodales"]
    assert c.loc[0, "Fx"] == 5.0
    assert c.loc[1, "Fx"] == 0.0 and c.loc[1, "Fz"] == 100.0
