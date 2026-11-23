"""Lot 3 : JSON versionné (schema_version), CSV des diagrammes de Poutres, parties de la note de calcul, SVG et CSV du site."""

import csv
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from mecastruct import SCHEMA_VERSION, __version__, schema_refuse
from mecastruct.bureau import etudes
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from mecastruct.pont import noyau
from mecastruct.services import project_io, sources
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import loadExample

noyau.charger("structures")
FORMULAIRES = noyau.tous_formulaires()
RACINE = Path(__file__).resolve().parents[2]


def appel(ident, saisie=None):
    s = FORMULAIRES[ident.split(".")[0]]["defaut"] if saisie is None else saisie
    r = json.loads(noyau.appeler(ident, json.dumps(s)))
    return r


def sortie(ident, saisie=None):
    r = appel(ident, saisie)
    assert r["ok"], r.get("erreur")
    return r["sortie"]


def lire_csv(texte, point=False):
    """(en-têtes, lignes de nombres) d'un CSV de MecaStruct : séparateur « ; », BOM d'Excel, décimale virgule ou point."""
    assert texte.startswith("﻿")
    lignes = list(csv.reader(io.StringIO(texte[1:]), delimiter=";"))
    conv = (lambda x: float(x)) if point else (lambda x: float(x.replace(",", ".")))
    return lignes[0], [[conv(x) for x in ligne] for ligne in lignes[1:]]


# ------------------------------------------------------------------------------------- CSV des diagrammes de Poutres


@pytest.fixture(scope="module")
def poutre():
    """Saisie de l'exemple de Poutres, et le résultat du moteur recalculé (celui que la page et le CSV lisent)."""
    s = FORMULAIRES["beam"]["defaut"]
    return s, vr.recompute("Beam", json.loads(json.dumps(s)), noyau.dm(), None)


def test_csv_colonnes_et_unites(poutre):
    s, _ = poutre
    entetes, lignes = lire_csv(sortie("beam.csv", s)["texte"])
    assert entetes == ["x (m)", "N (kN)", "Ty (kN)", "Tz (kN)", "Mt (kN·m)", "Mfy (kN·m)", "Mfz (kN·m)",
                       "Rotation α (mrad)", "Flèche v (mm)"]  # fmt: skip
    assert all(len(ligne) == len(entetes) for ligne in lignes)


def test_csv_memes_valeurs_que_le_moteur(poutre):
    s, calc = poutre
    sol, integ = calc["sol"], calc["defl"]["integration"]
    _, lignes = lire_csv(sortie("beam.csv", s)["texte"])
    x = np.array([ligne[0] for ligne in lignes])
    # mêmes abscisses que la feuille « Efforts » de l'export Excel : nombre de lignes égal, croissantes, de 0 à L
    efforts = project_io.beamEffortSheets(sol)["Efforts"]
    assert len(lignes) == len(efforts) and x[0] == 0 and x[-1] == pytest.approx(s["L"]) and np.all(np.diff(x) > 0)
    for j, c in enumerate(("N", "Ty", "Tz", "Mt", "Mfy", "Mfz"), start=1):
        np.testing.assert_allclose([ligne[j] for ligne in lignes], ppEval(sol[c], x) / 1e3, rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose([ligne[7] for ligne in lignes], ppEval(integ["alphaPP"], x) * 1e3, rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose([ligne[8] for ligne in lignes], ppEval(integ["vPP"], x) * 1e3, rtol=1e-12, atol=1e-9)
    # la flèche maximale du CSV est celle du moteur, à la finesse de la grille près
    assert max(abs(ligne[8]) for ligne in lignes) == pytest.approx(integ["fmax"] * 1e3, rel=2e-2)
    mfz = max(abs(sol["extrema"]["Mfz"][b]) for b in ("max", "min")) / 1e3  # extremum entre deux points de la grille
    assert max(abs(ligne[6]) for ligne in lignes) == pytest.approx(mfz, rel=1e-2)


def test_csv_point_ou_virgule(poutre):
    s, _ = poutre
    virgule = sortie("beam.csv", s)["texte"]
    point = sortie("beam.csv", {**s, "_point": True})["texte"]
    assert "," in virgule.splitlines()[1] and "." not in virgule.splitlines()[1]
    assert "." in point.splitlines()[1] and "," not in point.splitlines()[1] and ";" in point
    assert lire_csv(virgule)[1] == lire_csv(point, point=True)[1]  # mêmes nombres, seule la décimale change


def test_csv_sans_deformee_et_sans_resultat(poutre):
    _, calc = poutre
    entetes, _ = lire_csv(project_io.beamDiagramCsv(calc["sol"]))
    assert entetes[-1] == "Mfz (kN·m)"  # sans résultat de flèche : seulement x et les efforts
    with pytest.raises(MecaStructError, match="Calculer"):
        project_io.beamDiagramCsv({})


def test_csv_plan_xz_nomme_beta_et_w(poutre):
    _, calc = poutre
    defl = {**calc["defl"], "plane": "xz"}
    entetes, _ = lire_csv(project_io.beamDiagramCsv(calc["sol"], defl))
    assert entetes[-2:] == ["Rotation β (mrad)", "Flèche w (mm)"]


def test_csv_poutre_est_declare_dans_le_pont():
    assert FORMULAIRES["beam"]["exports"] and "beam.csv" in noyau._REGISTRE
    assert "truss.csv" not in noyau._REGISTRE  # seules les Poutres ont des diagrammes par abscisse


# ---------------------------------------------------------------------------------------------------- JSON versionné


def test_ecriture_porte_le_numero_de_schema_et_l_outil():
    outil = f"{project_io.APP} {__version__}"
    p = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    assert p["schema_version"] == SCHEMA_VERSION == 1 and p["outil"] == outil and p["version"] == project_io.FORMAT_VERSION
    saisies = {k: loadExample(k) for k in project_io.PROJECT_KEYS}
    q = json.loads(project_io.projectToJson(saisies))
    assert q["schema_version"] == 1 and q["outil"] == outil and q["version"] == project_io.FORMAT_VERSION
    m = json.loads(sortie("machine.enregistrer", {"ident": "rlt", "saisie": FORMULAIRES["rlt"]["defaut"]})["texte"])
    assert m["schema_version"] == 1 and m["outil"] == outil and m["version"] == 1
    p2 = json.loads(sortie("fla.enregistrer", FORMULAIRES["fla"]["defaut"])["texte"])  # fichier du site
    assert p2["schema_version"] == 1 and p2["onglet"] == "Fla"


def test_ancien_fichier_sans_la_cle_s_ouvre():
    d = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    del d["schema_version"], d["outil"]  # fichier écrit par une version d'avant le lot 3
    onglet, saisie = project_io.problemFromJson(json.dumps(d))
    assert onglet == "Fla" and saisie == loadExample("Fla")
    projet = json.loads(project_io.projectToJson({k: loadExample(k) for k in project_io.PROJECT_KEYS}))
    del projet["schema_version"], projet["outil"]
    relus, non_lus = project_io.projectFromJson(json.dumps(projet))
    assert set(relus) == set(project_io.PROJECT_KEYS) and non_lus == []
    machine = json.loads(sortie("machine.enregistrer", {"ident": "rlt", "saisie": FORMULAIRES["rlt"]["defaut"]})["texte"])
    del machine["schema_version"], machine["outil"]
    assert sortie("machine.ouvrir", {"ident": "rlt", "texte": json.dumps(machine)})["Fr"] == FORMULAIRES["rlt"]["defaut"]["Fr"]


def test_cle_inconnue_ignoree():
    d = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    d["une_cle_du_futur"] = {"a": [1, 2]}
    assert project_io.problemFromJson(json.dumps(d))[0] == "Fla"
    projet = json.loads(project_io.projectToJson({k: loadExample(k) for k in project_io.PROJECT_KEYS}))
    projet["autre"] = 1
    assert project_io.projectFromJson(json.dumps(projet))[1] == []
    machine = json.loads(sortie("machine.enregistrer", {"ident": "rlt", "saisie": FORMULAIRES["rlt"]["defaut"]})["texte"])
    machine["une_cle_du_futur"] = True
    assert appel("machine.ouvrir", {"ident": "rlt", "texte": json.dumps(machine)})["ok"]


@pytest.mark.parametrize("suivant", [SCHEMA_VERSION + 1, 99])
def test_version_future_refusee_proprement(suivant):
    d = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    d["schema_version"], d["outil"] = suivant, "MecaStruct RdM 9.9.9"
    with pytest.raises(MecaStructError, match="version plus récente") as e:
        project_io.problemFromJson(json.dumps(d))
    assert e.value.identifier == "MecaStruct:App:badProblemFile" and "9.9.9" in e.value.message and "Mettez" in e.value.message
    with pytest.raises(MecaStructError, match="version plus récente"):
        project_io.projectFromJson(json.dumps({**d, "projet": {}}))
    machine = {"app": project_io.APP, "version": 1, "schema_version": suivant, "page": "rlt", "saisie": {}}
    r = appel("machine.ouvrir", {"ident": "rlt", "texte": json.dumps(machine)})
    assert not r["ok"] and "version plus récente" in r["erreur"]


def test_format_ancien_version_superieure_refuse_aussi():
    d = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    d["version"] = project_io.FORMAT_VERSION + 1
    with pytest.raises(MecaStructError, match="version plus récente"):
        project_io.problemFromJson(json.dumps(d))


@pytest.mark.parametrize("valeur", ["2", 0, -1, 1.5, True, None, [1]])
def test_numero_de_schema_illisible_refuse(valeur):
    d = json.loads(project_io.problemToJson("Fla", loadExample("Fla")))
    d["schema_version"] = valeur
    with pytest.raises(MecaStructError, match="illisible"):
        project_io.problemFromJson(json.dumps(d))


def test_schema_refuse_direct():
    assert schema_refuse({}) is None and schema_refuse({"schema_version": 1}) is None
    assert "version plus récente" in schema_refuse({"schema_version": SCHEMA_VERSION + 1})


def test_export_mes_etudes_garde_son_format_et_son_numero_de_schema(bureau):
    donnees = etudes.exporter()
    assert donnees["format"] == "mecastruct-etudes" and donnees["version"] == 1  # inchangé : les anciens sites le lisent
    assert donnees["schema_version"] == SCHEMA_VERSION and donnees["outil"] == f"MecaStruct RdM {__version__}"


def test_import_des_etudes_ancien_futur_et_cle_inconnue():
    base = {"format": "mecastruct-etudes", "version": 1, "saisies": {"beam": {"L": 6}}}
    assert etudes.lire_import(json.dumps(base))["ok"]  # sans schema_version : version 1
    assert etudes.lire_import(json.dumps({**base, "schema_version": 1, "cle_du_futur": 3}))["ok"]
    futur = etudes.lire_import(json.dumps({**base, "schema_version": 2, "outil": "MecaStruct RdM 9.0.0"}))
    assert not futur["ok"] and "version plus récente" in futur["erreur"] and "9.0.0" in futur["erreur"]
    assert "illisible" in etudes.lire_import(json.dumps({**base, "schema_version": "x"}))["erreur"]
    assert "autre version" in etudes.lire_import(json.dumps({**base, "version": 9}))["erreur"]  # format historique : inchangé


# --------------------------------------------------------------------------------------- note de calcul (parties)

PARTIES_NOTE = ["OBJET ET CONCLUSION", "HYPOTHÈSES ET LIMITES", "DONNÉES", "VERDICT ET MODES DE RUINE", "RÉSULTATS",
                "DÉMARCHE DU CALCUL", "CONCLUSION", "ANNEXES : RÉFÉRENCES"]  # fmt: skip


@pytest.mark.parametrize("ident", ["beam", "tra", "fla", "rlt", "eng", "mot"])
def test_bloc_notes_parties_dans_l_ordre_du_gabarit(ident):
    t = sortie(ident + ".texte")["texte"]
    titres = [ligne for ligne in t.splitlines() if ligne in PARTIES_NOTE]
    assert titres == [p for p in PARTIES_NOTE if p in titres] and {"OBJET ET CONCLUSION", "HYPOTHÈSES ET LIMITES", "CONCLUSION",
                                                                   "ANNEXES : RÉFÉRENCES", "DONNÉES"} <= set(titres)  # fmt: skip
    assert t.index("OBJET ET CONCLUSION") < t.index("DONNÉES") < t.index("\r\nCONCLUSION\r\n") < t.index("ANNEXES")
    assert "Décision :" in t and "Action conseillée :" in t


def test_bloc_notes_contenu_venu_de_la_page():
    t = sortie("tra.texte")["texte"]
    assert "NON VÉRIFIÉ" in t.split("DONNÉES")[0]  # conclusion en tête
    fin = t.split("\r\nCONCLUSION\r\n")[1]
    assert "Décision : Non conforme" in fin and "Mode dimensionnant" in fin and "Réduire la charge" in fin
    rlt = sortie("rlt.texte")["texte"]
    annexes = rlt.split("ANNEXES : RÉFÉRENCES")[1]
    assert "cours « Calcul sur les roulements »" in annexes and sources.source("rlt")[:60] in annexes.replace("\r\n", " ")
    hyp = rlt.split("HYPOTHÈSES ET LIMITES")[1].split("DONNÉES")[0]
    assert "Table du cours" in hyp and "Source :" not in hyp  # la source va dans les annexes, pas deux fois
    assert "page « Références »" in annexes


def test_bloc_notes_se_retrouve_dans_la_consigne_ia():
    note = sortie("beam.texte")["texte"]
    assert note in sortie("beam.ia")["texte"]


# -------------------------------------------------------------------------------- dossier de validation (parties)

PARTIES_DOSSIER = ["donnees", "hypotheses", "verif", "resultats", "diagrammes", "rapport", "formules", "conclusion", "avis", "annexes"]


def test_dossier_dix_parties_dans_l_ordre():
    assert [i for i, _ in vr._SECTIONS] == PARTIES_DOSSIER
    assert [t.split(".")[0] for _, t in vr._SECTIONS] == [str(n) for n in range(1, 11)]


@pytest.mark.parametrize("ident", ["beam", "tra", "cis", "rlt", "eng"])
def test_dossier_conclusion_et_annexes(ident):
    html = sortie(ident + ".dossier")["html"]
    ids = re.findall(r'<h2 id="(\w+)">', html)
    assert ids == PARTIES_DOSSIER
    conclusion = html.split('<h2 id="conclusion">')[1].split('<h2 id="avis">')[0]
    annexes = html.split('<h2 id="annexes">')[1]
    assert len(re.sub(r"<[^>]+>", "", conclusion).strip()) > 30  # le statut du calcul, au moins
    if ident in ("beam", "tra", "cis"):  # pages de structure : bloc « Décision » de la page
        assert "Décision :" in conclusion and "Action conseillée" in conclusion
    assert "page « Références »" in annexes
    if sources.source(ident):
        assert sources.source(ident)[:40] in annexes


def test_cles_des_sources_couvrent_les_dossiers():
    """Chaque clé de dossier (onglet ou type de machine) mène à un calcul qui existe dans le pont."""
    from mecastruct.pont.machines import DOSSIERS

    for ident, (_titre, typ, _f, _b) in DOSSIERS.items():
        assert sources.IDENT_DE_CLE[typ] == ident
    for tab in project_io.PROJECT_KEYS:
        assert sources.IDENT_DE_CLE[tab] in FORMULAIRES


# ---------------------------------------------------------------------------------------- site (JavaScript, sans navigateur)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js absent")
def test_csv_du_site_formules_et_nombres(tmp_path):
    """App.csv (docs/app.js) : séparateur « ; », guillemets, BOM, nombres sans espace de milliers, pas de formule."""
    source = (RACINE / "docs" / "app.js").read_text(encoding="utf-8")
    a = source.index("  function csv(entetes")
    b = source.index("\n  }\n", a) + 4
    script = tmp_path / "csv.js"
    script.write_text(
        source[a:b]
        + """
const r = csv(["Grandeur", "Valeur (MPa)"], [["σ max", "1 234,5"], ["Note", "=1+1"], ["Écart", "−3,2"], ["Texte;long", 'dit "oui"'], ["Vide", "-"]]);
const rp = csv(["x"], [["1,5"]], true);
process.stdout.write(JSON.stringify([r, rp]));
""",
        encoding="utf-8",
    )
    sortie_js = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    r, rp = json.loads(sortie_js)
    assert r.startswith("﻿Grandeur;Valeur (MPa)\r\n")
    assert "σ max;1234,5" in r and "Écart;-3,2" in r and "Vide;-\r\n" in r
    assert "Note;'=1+1" in r  # une formule est neutralisée par une apostrophe
    assert '"Texte;long";"dit ""oui"""' in r
    assert rp == "﻿x\r\n1.5\r\n"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js absent")
def test_import_etudes_du_site_refuse_un_schema_futur(tmp_path):
    """lireImport (docs/js/etudes.js) : ancien fichier lu, clé inconnue ignorée, schéma futur refusé avec un message clair."""
    source = (RACINE / "docs" / "js" / "etudes.js").read_text(encoding="utf-8")
    a = source.index("  function lireImport(texte)")
    b = source.index("\n  }\n", a) + 4
    script = tmp_path / "etudes.js"
    script.write_text(
        """const FORMAT = "mecastruct-etudes", SCHEMA_VERSION = 1, IDENT = /^[A-Za-z0-9_]{1,40}$/, MAX_SAISIES = 60;
const objet = (x) => !!x && typeof x === "object" && !Array.isArray(x);
const avecDate = () => true, pageFavorite = () => false, pageCalcul = () => false, copieValide = () => false;
"""
        + source[a:b]
        + """
const base = { format: FORMAT, version: 1, saisies: { beam: { L: 6 } } };
const essai = (o) => lireImport(JSON.stringify(o));
process.stdout.write(JSON.stringify([essai(base).ok, essai({ ...base, schema_version: 1, inconnue: 3 }).ok,
  essai({ ...base, schema_version: 2, outil: "MecaStruct RdM 9.0.0" }), essai({ ...base, schema_version: "x" }).erreur,
  essai({ ...base, version: 9 }).erreur]));
""",
        encoding="utf-8",
    )
    sortie_js = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    ancien, inconnue, futur, illisible, autre = json.loads(sortie_js)
    assert ancien is True and inconnue is True
    assert futur["ok"] is False and "version plus récente" in futur["erreur"] and "9.0.0" in futur["erreur"]
    assert "illisible" in illisible and "autre version" in autre


def test_boutons_csv_et_svg_branches_dans_le_site():
    """Les boutons existent dans le code du site : CSV des diagrammes (Poutres), CSV des tableaux, SVG des graphiques."""
    app = (RACINE / "docs" / "app.js").read_text(encoding="utf-8")
    machine = (RACINE / "docs" / "js" / "machine.js").read_text(encoding="utf-8")
    assert "Télécharger l'image (SVG)" in app and 'format: "svg"' in app and "Exporter le tableau (CSV)" in app
    assert 'boutonImage(d, "graphique.png", true)' in app  # chaque graphique de résultat porte les deux boutons
    assert "Exporter les diagrammes (CSV)" in machine and 'ident === "beam"' in machine and 'ident + ".csv"' in machine


# ------------------------------------------------------------------------------------ bureau : boutons CSV et SVG


def _vue_figure(bureau):
    from mecastruct.bureau.widgets import VueFigure

    return next(v for v in bureau.page.findChildren(VueFigure) if v.isVisibleTo(bureau.page))


def _figure_tracee(bureau, vue) -> bool:
    """La page Plotly de la vue est chargée et le graphique est tracé."""
    r: list = []
    vue.page().runJavaScript("!!(window.Plotly && document.querySelector('.js-plotly-plot svg.main-svg'))", r.append)
    bureau.qtbot.waitUntil(lambda: bool(r), timeout=5000)
    return r[0] is True


def test_bureau_csv_des_diagrammes_de_poutres(bureau, tmp_path, monkeypatch):
    from mecastruct.bureau import state, widgets

    monkeypatch.setattr(widgets, "DUREE_RETOUR_MS", 20)  # le libellé « ✓ Enregistré » revient vite

    bureau.ouvre("poutres")
    bureau.clique("Calculer")
    bureau.attend(300)
    bureau.ouvre_volet("Fichiers")
    bouton = bureau.bouton("Exporter les diagrammes (CSV)")
    assert bouton.isEnabled()
    res = state.result("Beam")
    for point in (False, True):
        bureau.case("Point décimal dans le CSV des diagrammes", point)
        fichier = tmp_path / f"diagrammes_{point}.csv"
        bureau.clavier_enregistrer(str(fichier))
        bureau.bouton("Exporter les diagrammes (CSV)").click()
        bureau.attend(150)
        assert fichier.read_bytes() == project_io.beamDiagramCsv(res["sol"], res["defl"], point).encode("utf-8")
    entetes, lignes = lire_csv(fichier.read_text(encoding="utf-8"), point=True)
    assert entetes[0] == "x (m)" and entetes[-1] == "Flèche v (mm)" and len(lignes) > 100


def test_bureau_csv_inactif_sans_resultat(bureau):
    bureau.ouvre("poutres")
    bureau.ouvre_volet("Fichiers")
    assert not bureau.bouton("Exporter les diagrammes (CSV)").isEnabled()


def test_bureau_svg_du_graphique(bureau, tmp_path):
    bureau.ouvre("poutres")
    bureau.clique("Calculer")
    bureau.attend(500)
    vue = _vue_figure(bureau)
    bureau.qtbot.waitUntil(lambda: _figure_tracee(bureau, vue), timeout=60000)
    fichier = tmp_path / "graphique.svg"
    bureau.clavier_enregistrer(str(fichier))
    bouton = bureau.bouton("Télécharger l'image (SVG)")
    bouton.click()
    bureau.qtbot.waitUntil(fichier.exists, timeout=30000)
    bureau.attend(100)
    svg = fichier.read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg") and svg.rstrip().endswith("</svg>") and "<text" in svg
    assert bouton.text().startswith("✓")
