"""Pont des pages « Liaisons et guidages » et « Transmission » : formulaires, calculs, schémas.

Les formulaires reprennent les champs, unités et bornes des pages de bureau (bureau/pages/*.py). La page web les lit
avec formulaire(id) ; elle n'a aucun libellé en dur.
"""

import json

from mecastruct import APP_NOM, APPS_ACCEPTES
from mecastruct.core import bearings, fits, plain_bearing, planetary, shrink_fit
from mecastruct.plots import machine_plots, machine_schemas
from mecastruct.pont import exports, noyau
from mecastruct.pont.formulaire import case, groupe, liste, nb
from mecastruct.pont.noyau import calcul, dm, formulaires_de
from mecastruct.services import criteres, machine, valeurs_cles
from mecastruct.services import machine_courses as mc
from mecastruct.services.sources import avec_sources


def materiaux():
    return dm().listMaterials()


def sortie(res: dict, figure=None, ident: str = "", s: dict | None = None) -> dict:
    """Sortie d'un service réduite à ce que la page affiche : verdict, modes de ruine, tableaux, formules, démarche."""
    r = res.get("result", {})
    return {
        "criteres": criteres.criteres(ident, s or {}, res),
        "valeurs": valeurs_cles.valeurs(res.get("status", "")),
        "_brut": res,
        "status": res.get("status", ""),
        "ok": res.get("ok"),
        "tables": res.get("tables", {}),
        "latex": r.get("latex", []),
        "rapport": r.get("rapport", [])[1:],
        "figure": figure,
    }


def _figure(f):
    """Figure Plotly ou None si elle ne peut pas être dessinée pour cette saisie (le calcul reste affiché)."""
    try:
        return f()
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------------------------------- formulaires


def _formulaires() -> dict:
    """Description de chaque calcul : titre d'onglet, groupes de champs, note, valeurs de départ, schéma, graphique."""
    noms = materiaux()
    return {
        "aju": {
            "titre": "Ajustement", "defaut": machine.defaultFitInput(), "apercu": False,
            "groupes": [groupe("Ajustement",
                               nb("d", "Diamètre nominal", "mm", 0.0, 3150.0, "Cote nominale commune à l'alésage et à l'arbre."),
                               liste("alesage", "Alésage", fits.LETTRES_ALESAGE, "Position de la tolérance de l'alésage (H : écart inférieur nul)."),
                               liste("qa", "Qualité alésage", fits.QUALITES, "Qualité IT : plus le nombre est petit, plus la tolérance est serrée."),
                               liste("arbre", "Arbre", fits.LETTRES_ARBRE, "Position de la tolérance de l'arbre (h : écart supérieur nul)."),
                               liste("qb", "Qualité arbre", fits.QUALITES), ligne=True)],
            "note": "Tables de l'ISO 286-1/-2 (jusqu'à 3150 mm). Correction Δ appliquée à K, M, N (qualités ≤ 8) et P à ZC "
                    "(≤ 7). Jeu négatif = serrage. Usuels : H7/g6 glissant, H7/h6 glissant juste, H7/k6 incertain, H7/p6 serré.",
        },
        "fre": {
            "titre": "Frettage", "defaut": machine.defaultShrinkInput(), "apercu": False, "norme": True,
            "groupes": [
                groupe("Efforts à transmettre", nb("C", "Couple C", "N·m", 0.0), nb("Fa", "Effort axial Fa", "N", 0.0),
                       nb("f", "Coefficient d'adhérence f", "", 0.01, aide="Acier sur acier, montage à chaud : 0,1 à 0,15."),
                       nb("s", "Coefficient de sécurité sur l'effort", "", 1.0)),
                groupe("Géométrie", nb("d", "Diamètre fretté d", "mm", 0.0), nb("di", "Diamètre intérieur de l'arbre (0 = plein)", "mm", 0.0),
                       nb("D", "Diamètre extérieur du moyeu D", "mm", 0.0), nb("L", "Longueur frettée L", "mm", 0.0)),
                groupe("Matériaux", liste("matArbre", "Matériau de l'arbre", noms), liste("matMoyeu", "Matériau du moyeu", noms)),
                groupe("Tolérances et montage", liste("qa", "Qualité arbre", fits.QUALITES), liste("qm", "Qualité moyeu (H)", fits.QUALITES),
                       nb("lissage", "Lissage (perte de serrage)", "µm", 0.0, aide="Écrasement des rugosités au montage."),
                       nb("jeu", "Jeu de montage à chaud", "mm", 0.0)),
            ],
            "note": "Alésage normal H. L'arbre retenu est le moins serré dont l'écart inférieur couvre le serrage utile + le "
                    "lissage. Contraintes : Lamé, arbre 2p/(1 − (di/d)²), moyeu Von Mises à l'alésage.",
        },
        "pal": {
            "titre": "Palier lisse", "defaut": machine.defaultBearingInput(), "apercu": False,
            "groupes": [
                groupe("Charges et mouvement", nb("Fr", "Force radiale Fr", "N", 0.0), nb("Fa", "Force axiale Fa (collerette)", "N", 0.0),
                       nb("n", "Fréquence de rotation", "tr/min", 0.0),
                       nb("osc", "Fréquence d'oscillation", "oscillations/min", 0.0, aide="Remplace la rotation si l'oscillation et β sont renseignés."),
                       nb("beta", "Demi-amplitude β", "°", 0.0)),
                groupe("Coussinet", liste("materiau", "Matériau", [m["Name"] for m in plain_bearing.materials()]),
                       nb("d", "Alésage d (diamètre de l'arbre)", "mm", 0.0), nb("L", "Longueur L", "mm", 0.0),
                       nb("Dfl", "Diamètre de collerette (0 = sans)", "mm", 0.0)),
            ],
            "note": "Limites P, V et courbe P-V : ordres de grandeur par famille de matériau, à confirmer sur la documentation "
                    "du fabricant du coussinet.",
        },
        "rlt": {
            "dossierMachine": True, "titre": "Durée de vie", "defaut": mc.defaultBearingInput(), "apercu": True,
            "groupes": [
                groupe("Charges et vitesse", nb("Fr", "Charge radiale Fr", "N", 0.0), nb("Fa", "Charge axiale Fa", "N", 0.0),
                       nb("N", "Fréquence de rotation", "tr/min", 0.0)),
                groupe("Roulement", liste("type", "Éléments roulants", ["billes", "rouleaux"]),
                       nb("C", "Charge dynamique de base C", "N", 0.0, aide="Valeur du catalogue du fabricant."),
                       nb("C0", "Charge statique de base C0", "N", 0.0),
                       case("tableau", "e et Y dans la table du cours (billes à contact radial)"),
                       nb("e", "e", "", 0.0), nb("X", "X", "", 0.0), nb("Y", "Y", "", 0.0)),
                groupe("Fiabilité et durée visée", nb("F", "Fiabilité F", "%", 1.0, 99.9), nb("Lh", "Durée visée Lh", "h", 0.0)),
            ],
            "note": "Table du cours : e, X et Y pour les billes à contact radial, interpolés linéairement en Fa/C0. Pour les "
                    "autres roulements, saisir e, X et Y du constructeur. Fa/Fr ≤ e : P = Fr ; sinon P = X·Fr + Y·Fa.",
        },
        "rlt_ens": {
            "dossierMachine": True, "titre": "Ensemble de roulements", "defaut": mc.defaultBearingSetInput(), "apercu": True,
            "groupes": [
                groupe("Durées des roulements en série", nb("L1", "Durée du roulement 1", "h", 0.0), nb("L2", "Durée du roulement 2", "h", 0.0),
                       nb("L3", "Durée du roulement 3 (0 = absent)", "h", 0.0)),
                groupe("Guidage iso-fiable", nb("LG", "Durée du guidage LG", "h", 0.0), nb("nG", "Nombre de roulements iso-fiables", "", 1.0)),
            ],
            "note": "Roulements en série sur un même arbre : (Σ Lj^(−1,5))^(−1/1,5). Roulements iso-fiables : chacun dure "
                    "LG × n^(2/3), et l'ensemble dure LG.",
        },
        "rlt_regle": {
            "titre": "Règles de montage", "defaut": {"bague": "intérieure", "rotation": "tournante", "charge": ""}, "apercu": False,
            "auto": True,
            "groupes": [groupe("Montage", liste("bague", "Bague", ["intérieure", "extérieure"]),
                               liste("rotation", "Rotation de la bague par rapport à la charge", sorted({r for (_, r, _), _ in bearings.AJUSTEMENTS})),
                               liste("charge", "Charge", sorted({c for (_, _, c), _ in bearings.AJUSTEMENTS})))],
            "note": "Règle du cours : la bague tournante par rapport à la charge se monte serrée, la bague fixe se monte "
                    "glissante. Immobilisation axiale : anneau élastique, épaulement, entretoise, écrou à encoche, chapeau.",
        },
        "eng": {
            "dossierMachine": True, "titre": "Engrènement", "defaut": mc.defaultGearInput(), "apercu": True,
            "groupes": [
                groupe("Géométrie", nb("m", "Module m", "mm", 0.1), nb("Z1", "Dents du pignon Z1", "", 1.0, 1000.0),
                       nb("Z2", "Dents de la roue Z2", "", 1.0, 1000.0), ligne=True),
                groupe("Transmission", nb("P", "Puissance au pignon P", "W", 0.0), nb("N", "Fréquence de rotation du pignon", "tr/min", 0.1)),
                groupe("Denture et matériau", nb("k", "Largeur de denture k = b/m", "", 1.0, aide="Usuellement entre 6 et 10."),
                       nb("alpha", "Angle de pression α", "°", 14.5, 25.0,
                          aide="20° est la valeur normalisée courante (ISO 53) ; elle ne modifie que les efforts radial et normal "
                               "et le dessin : la contrainte en pied de dent (formule de Lewis simplifiée du cours) suppose un profil à 20°."),
                       liste("materiau", "Matériau du pignon", noms), nb("s", "Coefficient de sécurité sur l'effort s", "", 1.0)),
            ],
            "note": "Angle de pression 20° par défaut (14,5° à 25° possible), dent à profil normal. Contrainte de flexion en pied de dent (poutre encastrée) "
                    "comparée à Rpe = Re/s. Usuellement k entre 6 et 10 et s = 1,5 si l'effort est mal connu.",
        },
        "trn": {
            "dossierMachine": True, "titre": "Train d'engrenages", "defaut": mc.defaultGearTrainInput(), "apercu": True,
            "groupes": [
                groupe("Entrée", nb("P", "Puissance d'entrée P", "W", 0.0), nb("N", "Fréquence de rotation d'entrée", "tr/min", 0.1),
                       nb("eta", "Rendement d'un engrènement η", "", 0.01, 1.0)),
                *[groupe(f"Engrènement {i}", nb(f"Z{2 * i - 1}", f"Dents menant Z{2 * i - 1}", "", 1.0, 1000.0),
                         nb(f"Z{2 * i}", f"Dents mené Z{2 * i}", "", 1.0, 1000.0), ligne=True) for i in (1, 2, 3)],
            ],
            "note": "Chaque engrènement extérieur inverse le sens : rapport −Zmenant/Zmené. La puissance diminue de η à chaque "
                    "engrènement et le couple se calcule par C = P/ω.",
        },
        "epi": {
            "dossierMachine": True, "titre": "Train épicycloïdal", "defaut": mc.defaultPlanetaryInput(), "apercu": True,
            "groupes": [
                groupe("Dentures", nb("Z1", "Planétaire Z1", "", 1.0, 1000.0), nb("Z21", "Satellite engrenant le planétaire Z21", "", 1.0, 1000.0),
                       nb("Z22", "Satellite engrenant la couronne Z22 (= Z21 si satellite simple)", "", 1.0, 1000.0),
                       nb("Z4", "Couronne Z4", "", 1.0, 1000.0), nb("nSat", "Nombre de satellites", "", 1.0, 24.0)),
                groupe("Cinématique", liste("bloque", "Élément bloqué", planetary.ELEMENTS), liste("entree", "Élément d'entrée", planetary.ELEMENTS),
                       nb("Ne", "Fréquence de rotation de l'entrée", "tr/min")),
            ],
            "note": "L'élément restant est la sortie. Montage : Z4 = Z1 + Z21 + Z22 et (Z1 + Z4)/n_sat entier.",
        },
        "frn": {
            "dossierMachine": True, "titre": "Frein à disque", "defaut": mc.defaultBrakeInput(), "apercu": True,
            "groupes": [
                groupe("Effort et garniture", nb("F", "Effort presseur F par surface", "N", 0.0), nb("f", "Coefficient de frottement f", "", 0.0, 1.0),
                       nb("n", "Nombre de surfaces frottantes n", "", 1.0)),
                groupe("Géométrie du disque", nb("Ri", "Rayon intérieur Ri", "mm", 0.0), nb("Re", "Rayon extérieur Re", "mm", 0.1),
                       nb("N", "Fréquence de rotation au freinage", "tr/min", 0.0)),
            ],
            "note": "Couple Cf = n·f·F·(2/3)(Re³ − Ri³)/(Re² − Ri²) en pression constante, ou n·f·F·(Re + Ri)/2 en usure "
                    "constante. La puissance spécifique moyenne est à comparer à la limite du fabricant de la garniture.",
        },
        "emb": {
            "dossierMachine": True, "titre": "Embrayage", "defaut": mc.defaultClutchInput(), "apercu": True,
            "groupes": [
                groupe("Moteur et récepteur", nb("CM", "Couple moteur CM", "N·m", 0.0), nb("NM", "Fréquence de rotation du moteur", "tr/min", 0.0),
                       nb("JR", "Inertie du récepteur JR", "kg·m²", 0.0), nb("CR", "Couple résistant CR (négatif)", "N·m", None, 0.0)),
                groupe("Manœuvre", nb("ts", "Durée de synchronisation visée", "s", 0.1), nb("cadence", "Cadence", "manœuvres/h", 0.0)),
            ],
            "note": "Pendant la synchronisation le moteur est supposé à vitesse constante : le couple d'embrayage vaut "
                    "|CR| + JR·ω/ts. Il doit rester inférieur au couple moteur.",
        },
        "mot": {
            "dossierMachine": True, "titre": "Choix du moteur", "defaut": mc.defaultMotorInput(), "apercu": True,
            "groupes": [
                groupe("Cycle (couple et durée de chaque phase)", nb("Ca", "Couple en accélération Ca", "N·m"), nb("ta", "Durée de l'accélération", "s", 0.0),
                       nb("Cc", "Couple en régime établi Cc", "N·m"), nb("tc", "Durée du régime établi", "s", 0.0),
                       nb("Cfr", "Couple au freinage", "N·m"), nb("tfr", "Durée du freinage", "s", 0.0)),
                groupe("Moteur choisi", nb("Cn", "Couple nominal", "N·m", 0.0), nb("Cmax", "Couple maxi", "N·m", 0.0),
                       nb("Nmax", "Vitesse maxi", "tr/min", 0.0), nb("Nreq", "Vitesse requise par le cahier des charges", "tr/min", 0.0)),
                groupe("Inertie ramenée à l'arbre moteur", nb("Jm", "Inertie du moteur Jm", "kg·m²", 0.0),
                       nb("Js", "Inertie de la charge ramenée à sa sortie Js", "kg·m²", 0.0),
                       nb("rs", "Rapport de réduction vers la sortie", "", 0.01), ouvert=False),
            ],
            "note": "Les durées des phases ne figurent pas dans le cours : les valeurs par défaut retrouvent le couple "
                    "équivalent de 61 N·m du cours. Remplacez-les par les durées de votre cycle.",
        },
    }


formulaires_de(lambda: exports.marquer(avec_sources(_formulaires())))


# ------------------------------------------------------------------------------- dossier de validation (HTML)

# identifiant du calcul → (titre du dossier, type pour machine_validation, calcul du service, le calcul demande-t-il la base ?)
DOSSIERS = {
    "rlt": ("Roulements, durée de vie", "bearing", mc.computeBearingLife, False),
    "rlt_ens": ("Roulements, ensemble", "bearingSet", mc.computeBearingSet, False),
    "eng": ("Engrenages, engrènement", "gearMesh", mc.computeGearMesh, True),
    "trn": ("Engrenages, train", "gearTrain", mc.computeGearTrain, False),
    "epi": ("Trains épicycloïdaux", "planetary", mc.computePlanetary, False),
    "frn": ("Freins et embrayages, frein à disque", "brake", mc.computeBrake, False),
    "emb": ("Freins et embrayages, embrayage", "clutch", mc.computeClutch, False),
    "mot": ("Dimensionnement moteur", "motor", mc.computeMotor, False),
}


def _dossier(ident: str):
    titre, typ, calcul_service, avec_base = DOSSIERS[ident]

    @calcul(f"{ident}.dossier")
    def dossierMachine(s):
        """Dossier de validation : chaque grandeur refaite à la main avec la formule du cours, puis comparée au solveur."""
        from mecastruct.services import machine_validation

        res = calcul_service(s, dm()) if avec_base else calcul_service(s)
        html = machine_validation.generate(titre, [(titre, typ, s, res)], dm())
        return {"nom": machine_validation.fileName(titre), "html": html}


for _ident in DOSSIERS:
    _dossier(_ident)


# ------------------------------------------------------------------------------- fichiers d'étude (pages machines)

FORMAT = 1
TAILLE_MAXI = 200_000  # caractères : une saisie de machine en fait quelques centaines


def _genre(v) -> str:
    return "bool" if isinstance(v, bool) else "nombre" if isinstance(v, (int, float)) else type(v).__name__


@calcul("machine.enregistrer")
def machineEnregistrer(s):
    """Fichier d'étude d'une page d'éléments de machines : {app, version, page, saisie}."""
    ident = s["ident"]
    return {"nom": f"MecaStruct_{ident}.json",
            "texte": json.dumps({"app": APP_NOM, "version": FORMAT, "page": ident, "saisie": s["saisie"]},
                                ensure_ascii=False, indent=1)}  # fmt: skip


@calcul("machine.ouvrir")
def machineOuvrir(s):
    """Saisie d'un fichier d'étude, vérifiée : taille, page, champs connus et de même genre que l'exemple."""
    texte, ident = s["texte"], s["ident"]
    if len(texte) > TAILLE_MAXI:
        raise ValueError("Fichier trop gros pour une étude MecaStruct.")
    try:
        d = json.loads(texte)
    except ValueError as err:
        quoi = "il est vide" if not texte.strip() else "ce n'est pas un fichier .json valide"
        raise ValueError(f"Ce fichier n'est pas une étude MecaStruct ({quoi}).") from err
    if not isinstance(d, dict) or d.get("app") not in APPS_ACCEPTES or not isinstance(d.get("saisie"), dict):
        raise ValueError("Ce fichier n'est pas une étude MecaStruct.")
    if d.get("page") != ident:
        origine = d.get("page")
        raise ValueError(f"Cette étude vient d'une autre page (« {origine} »)." if isinstance(origine, str) and origine.strip()
                         else "Cette étude vient d'une page inconnue : elle ne s'ouvre pas ici.")
    defaut = noyau.tous_formulaires()[ident]["defaut"]
    for cle, v in d["saisie"].items():
        if cle not in defaut:
            raise ValueError(f"Champ inconnu dans l'étude : « {cle} ».")
        if _genre(v) != _genre(defaut[cle]):
            raise ValueError(f"Champ « {cle} » invalide dans l'étude.")
    return {**defaut, **d["saisie"]}


# ------------------------------------------------------------------------------------------------------ calculs


@calcul("aju")
def ajustement(s):
    res = machine.computeFit(s)
    return sortie(res, _figure(lambda: machine_plots.fitZones(res["result"], f"{s['alesage']}{s['qa']}", f"{s['arbre']}{s['qb']}")), "aju", s) | {"ok": None}  # aucune limite comparée : pas de « vérifié »


@calcul("fre")
def frettage(s):
    return sortie(machine.computeShrinkFit(s, dm()), None, "fre", s)


@calcul("fre.norme")
def frettageNorme(s):
    """Qualités, lissage et jeu conseillés par la norme pour le diamètre saisi ; None si hors table."""
    n = shrink_fit.normValues(float(s["d"]))
    if n is None:
        return None
    return {"qa": int(n["qualiteArbre"]), "qm": int(n["qualiteMoyeu"]), "lissage": n["lissage"], "jeu": n["jeu"]}


@calcul("pal")
def palier(s):
    res = machine.computeBearing(s)
    return sortie(res, _figure(lambda: machine_plots.pvDiagram(res["result"])), "pal", s)


@calcul("rlt")
def roulement(s):
    res = mc.computeBearingLife(s)
    return sortie(res, _figure(lambda: machine_schemas.bearingLife(res["result"], s)), "rlt", s)


@calcul("rlt.apercu")
def roulementApercu(s):
    return machine_schemas.bearingSection(s)


@calcul("rlt_ens")
def ensemble(s):
    return sortie(mc.computeBearingSet(s), None, "rlt_ens", s)


@calcul("rlt_ens.apercu")
def ensembleApercu(s):
    return machine_schemas.bearingSet(s)


@calcul("rlt_regle")
def regle(s):
    """Règle de montage : bague serrée ou glissante et ajustement conseillé (aucun calcul numérique)."""
    bague, rotation = s.get("bague", "intérieure"), s.get("rotation", "")
    rotations = list(dict.fromkeys(r for (b, r, _), _ in bearings.AJUSTEMENTS if b == bague))
    if rotation not in rotations:
        rotation = rotations[0]
    charges = [c for (b, r, c), _ in bearings.AJUSTEMENTS if (b, r) == (bague, rotation)]
    charge = s.get("charge") if s.get("charge") in charges else charges[0]
    portee, ajustement_ = bearings.fitRule(bague, rotation, charge)
    if rotation == "indéfinie" and bague == "intérieure":
        status = f"Direction de la charge non définie : bague intérieure rangée avec la tournante, montée serrée. Ajustement conseillé : {portee} {ajustement_}."
    elif rotation == "indéfinie":
        status = "Direction de la charge non définie : le cours conseille un alésage K7 pour une charge normale ou importante."
    else:
        status = f"Bague {bague} montée {bearings.mountingRule(bague, rotation)}. Ajustement conseillé : {portee} {ajustement_}."
    if bearings.needsLargerClearance(portee, ajustement_):
        status += " " + bearings.REMARQUE_JEU
    return {"status": status, "ok": None, "tables": {}, "latex": [], "rapport": [],
            "options": {"rotation": rotations, "charge": charges}, "saisie": {"rotation": rotation, "charge": charge}}


@calcul("eng")
def engrenement(s):
    return sortie(mc.computeGearMesh(s, dm()), None, "eng", s)


@calcul("eng.apercu")
def engrenementApercu(s):
    return machine_schemas.gearMesh(s)


@calcul("trn")
def train(s):
    return sortie(mc.computeGearTrain(s), None, "trn", s)


@calcul("trn.apercu")
def trainApercu(s):
    return machine_schemas.gearTrain(s)


@calcul("epi")
def epicycloidal(s):
    Z = [int(s[k]) for k in ("Z1", "Z21", "Z22", "Z4", "nSat")]
    controles = [{"nom": nom, "valeur": f"{val:g}", "ok": bool(ok)} for nom, val, ok in planetary.assemblyChecks(*Z)]
    return sortie(mc.computePlanetary(s), None, "epi", s) | {"controles": controles, "titre_controles": "Conditions de montage"}


@calcul("epi.apercu")
def epicycloidalApercu(s):
    return machine_schemas.planetaryTrain(s)


@calcul("frn")
def frein(s):
    return sortie(mc.computeBrake(s), _figure(lambda: machine_schemas.brakePressure(s)), "frn", s)


@calcul("frn.apercu")
def freinApercu(s):
    return machine_schemas.brakeDisc(s)


@calcul("emb")
def embrayage(s):
    return sortie(mc.computeClutch(s), None, "emb", s)


@calcul("emb.apercu")
def embrayageApercu(s):
    return machine_schemas.clutchSync(s)


@calcul("mot")
def moteur(s):
    return sortie(mc.computeMotor(s), None, "mot", s)


@calcul("mot.apercu")
def moteurApercu(s):
    return machine_schemas.motorCycle(s)


for _ident in ("aju", "fre", "pal", "rlt", "rlt_ens", "eng", "trn", "epi", "frn", "emb", "mot"):
    exports.declarer(_ident)
