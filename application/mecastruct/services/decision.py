"""Bloc « Décision » en tête d'un résultat : verdict, coefficient de sécurité minimal, mode dimensionnant, action conseillée.

Logique pure (sans Qt), commune au bureau ; le site la fait en JavaScript (docs/js/machine.js : CAUSES, AVERTISSEMENTS,
decision). Les deux doivent dire la même chose : le site est la référence.

- `CAUSES` : pour chaque calcul, le champ à corriger en premier pour un critère (le levier de conception : section,
  longueur, diamètre…, pas la charge imposée). « g:Titre » désigne un groupe de champs. Un critère absent n'a pas de lien.
- `AVERTISSEMENTS` : limites du modèle que la saisie franchit (angle de pression ≠ 20°, appui hors de la longueur L).
- `construire` : tout ce que le bloc affiche, sous forme de données.
"""

import math
import re
from dataclasses import dataclass, field

from mecastruct.services.export_texte import nombre

VERDICTS = {
    "ok": ("✓", "Conforme"),
    "neutre": ("⚠", "À vérifier"),
    "ko": ("✗", "Non conforme"),
    "info": ("ℹ", "Information"),
    "ancien": ("↻", "Résultat ancien — à recalculer"),
}

# Le premier motif qui correspond à « groupe|mode » l'emporte (dans `pal`, « Collerette » reste avant « Pression »).
CAUSES: dict[str, list[tuple[re.Pattern, list[str]]]] = {
    cle: [(re.compile(motif), cibles) for motif, cibles in entrees]
    for cle, entrees in {
        "beam": [(r".", ["g:Section"])],
        "beam.ec3": [(r"Déversement", ["Lcr"]), (r".", ["g:Section"])],
        "beam.fatigue": [(r".", ["g:Fatigue (Goodman)"])],
        "ossature": [(r".", ["g:Nœuds et pièces"])],
        "truss": [(r"Résistance", ["S"]), (r"Flambage", ["Imin"])],
        "tra": [(r".", ["S0"])],
        "cis": [(r"^Matage\|", ["Sm"]), (r"^Clavette\|", ["Lk"]), (r"^Goupille\|", ["dp"]),
                (r"\|Jourawski", ["g:Section pour Jourawski"]), (r"\|Cisaillement : τ max", ["S"])],
        "tor": [(r".", ["D"])],
        "fle": [(r".", ["g:Reprendre la section et les efforts"])],
        "fla": [(r".", ["g:Section"])],
        "ten": [(r".", ["sig"])],
        "fre": [(r"Adhérence", ["L"]), (r".", ["g:Tolérances et montage"])],
        "pal": [(r"Collerette", ["Dfl"]), (r"Vitesse", ["materiau"]), (r"Pression", ["L"])],
        "rlt": [(r".", ["C"])],
        "eng": [(r".", ["m"])],
        "emb": [(r".", ["ts"])],
        "mot": [(r"Couple nominal", ["Cn"]), (r"Couple maxi", ["Cmax"]), (r"Vitesse maxi", ["Nmax"])],
    }.items()
}  # fmt: skip

# Onglet du bureau (clé de saisie) ↔ identifiant de calcul du site, pour les pages construites sur un onglet de projet.
# Les pages de machines ont la même clé des deux côtés (« eng », « fre »… : saisie rangée sous « eng.m »).
ONGLET_BUREAU = {"beam": "Beam", "tra": "Tra", "cis": "Cis", "tor": "Tor", "fle": "Fle", "fla": "Fla", "ten": "Ten", "truss": "Tr"}
IDENT_DE_ONGLET = {v: k for k, v in ONGLET_BUREAU.items()}

# Groupe du site → titres des volets du bureau qui jouent le même rôle (le titre identique est essayé en premier).
GROUPES_BUREAU = {
    "Reprendre la section et les efforts": ("Efforts dans la section étudiée", "Reprendre les efforts de la poutre"),
    "Section pour Jourawski": ("Cisaillement simple, Jourawski et matage",),
}


def cle_champ(cle: str, champ: str):
    """Clé de saisie du bureau d'un champ du site : (onglet, champ) pour un onglet de projet, sinon « page.champ »."""
    return (ONGLET_BUREAU[cle], champ) if cle in ONGLET_BUREAU else f"{cle}.{champ}"


def _nombre_ou_none(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _avert_engrenage(s: dict) -> str | None:
    alpha = _nombre_ou_none(s.get("alpha"))
    if alpha is not None and alpha != 20:
        return "α ≠ 20° : la contrainte en pied de dent reste calculée pour un profil à 20°."
    return None


def _avert_poutre(s: dict) -> str | None:
    """Dernier appui (colonne « pos » du tableau « sup ») loin de l'extrémité L : porte-à-faux ou appui hors de la poutre."""
    L = _nombre_ou_none(s.get("L"))
    sup = s.get("sup")
    appuis = [p for a in sup if isinstance(a, dict) and (p := _nombre_ou_none(a.get("pos"))) is not None] if isinstance(sup, list) else []
    if L is None or L <= 0 or len(appuis) < 2:  # un seul appui : console, pas un oubli
        return None
    dernier = max(appuis)
    if L - dernier > 0.01 * L:
        return f"La longueur L ({nombre(L, 4)} m) dépasse le dernier appui ({nombre(dernier, 4)} m) : la poutre a un porte-à-faux."
    if dernier - L > 0.01 * L:
        return f"Un appui ({nombre(dernier, 4)} m) est au-delà de la longueur L ({nombre(L, 4)} m) : vérifiez les positions."
    return None


# Une ligne par réserve connue : fonction (saisie du calcul) → texte, ou None s'il n'y a rien à dire.
AVERTISSEMENTS = {"eng": _avert_engrenage, "beam": _avert_poutre}


def avertissement(cle: str, saisie: dict | None) -> str | None:
    f = AVERTISSEMENTS.get(cle)
    return f(saisie) if f and isinstance(saisie, dict) else None


def _taux(c: dict) -> float:
    t = c.get("taux")
    return t if isinstance(t, (int, float)) and math.isfinite(t) else math.inf


def libelle_mode(c: dict, criteres: list[dict]) -> str:
    """Nom du mode ; l'étude le précise quand le même nom existe dans plusieurs études (matage : matage, clavette, goupille)."""
    if c.get("groupe") and sum(1 for x in criteres if x["mode"] == c["mode"]) > 1:
        return f"{c['mode']} ({c['groupe']})"
    return c["mode"]


def causes(cle: str, c: dict) -> list[str]:
    """Cibles (champs ou « g:groupe ») du critère `c` du calcul `cle` ; liste vide s'il n'y a pas de champ sûr."""
    cible = f"{c.get('groupe') or ''}|{c['mode']}"
    for motif, cibles in CAUSES.get(cle, []):
        if motif.search(cible):
            return list(cibles)
    return []


def nf(x, chiffres: int = 3) -> str:
    """Nombre à `chiffres` chiffres significatifs, virgule décimale, sans notation scientifique pour les valeurs courantes."""
    if not isinstance(x, (int, float)) or not math.isfinite(x):
        return "∞"
    v = float(f"{x:.{chiffres}g}")
    return (str(int(v)) if v == int(v) and abs(v) < 1e15 else repr(v)).replace(".", ",")


def reserve(taux: float) -> str:
    """Réserve 1 − taux en % ; un taux non nul arrondi à « 100 » s'écrit « > 99,9 » (100 % ferait croire à une charge nulle)."""
    r = nf(100 * (1 - taux))
    return "> 99,9" if taux > 0 and r == "100" else r


@dataclass
class Fait:
    """Une ligne du bloc : titre, valeur en gras, précision, et le champ désigné (« Paramètre le plus influent »)."""

    titre: str
    valeur: str
    sous: str = ""
    champ: str | None = None


@dataclass
class Decision:
    niveau: str  # « ok », « ko », « neutre », « info » ou « ancien »
    icone: str
    mot: str
    faits: list[Fait] = field(default_factory=list)
    avertissement: str | None = None
    action: str = ""
    cause: list[str] = field(default_factory=list)  # cibles du lien « Aller à la cause » (mode non conforme le plus chargé)
    nom_cause: str = ""
    court: str = ""  # phrase brève (verdict et coefficient minimal), pour une barre résumé


def niveau_de(criteres: list[dict], ok: bool | None) -> str:
    if any(not c["ok"] for c in criteres) or ok is False:
        return "ko"
    return "ok" if ok is True else "neutre" if criteres else "info"


def ancienne() -> Decision:
    """Bloc d'un résultat qui ne correspond plus à la saisie : le verdict ne vaut plus."""
    icone, mot = VERDICTS["ancien"]
    return Decision("ancien", icone, mot, action="La saisie a changé depuis le dernier calcul : cliquez sur « Calculer ».")


def construire(cle: str, criteres: list[dict], ok: bool | None, saisie: dict | None = None, en_marge: bool = False) -> Decision:
    """Ce que dit le bloc « Décision » pour le calcul `cle`, ses critères (services/criteres.py) et son verdict `ok`."""
    niveau = niveau_de(criteres, ok)
    icone, mot = VERDICTS[niveau]
    ko = [c for c in criteres if not c["ok"]]
    pire = max(criteres, key=_taux, default=None)
    pire_ko = max(ko, key=_taux, default=None)
    finis = [c for c in criteres if c.get("genre") == "resistance" and _nombre_ou_none(c.get("s_obtenu")) is not None]
    smin = min(finis, key=lambda c: c["s_obtenu"], default=None)
    d = Decision(niveau, icone, mot)
    if smin:
        d.court = f"marge min {nf(100 * (smin['s_obtenu'] - 1))} %" if en_marge else f"s min {nf(smin['s_obtenu'])}"
        d.faits.append(Fait(
            "Marge de sécurité minimale" if en_marge else "Coefficient de sécurité minimal",
            f"{nf(100 * (smin['s_obtenu'] - 1))} %" if en_marge else f"s = {nf(smin['s_obtenu'])}",
            f"demandée {nf(100 * (smin['s_demande'] - 1))} %" if en_marge else f"demandé {nf(smin['s_demande'])}"))  # fmt: skip
    elif pire:
        d.court = f"réserve {reserve(pire['taux'])} %" if _taux(pire) <= 1 else f"dépassement {nf(100 * (_taux(pire) - 1))} %"
        d.faits.append(Fait("Réserve minimale" if _taux(pire) <= 1 else "Dépassement",
                            f"{reserve(pire['taux'])} %" if _taux(pire) <= 1 else f"{nf(100 * (_taux(pire) - 1))} %"))  # fmt: skip
    if d.court:
        d.court = f"{mot} · {d.court}"
    if pire:
        d.faits.append(Fait("Mode dimensionnant", libelle_mode(pire, criteres), f"taux {nf(100 * _taux(pire))} %"))
        cibles = causes(cle, pire)
        if cibles and not cibles[0].startswith("g:"):  # un groupe de champs n'est pas un paramètre
            d.faits.append(Fait("Paramètre le plus influent", "", champ=cibles[0]))
    action = "Vérifiez les hypothèses."
    if niveau == "ko" and pire_ko:
        nom = libelle_mode(pire_ko, criteres)
        action = (f"Réduire la charge ou augmenter la section pour « {nom} »." if pire_ko.get("genre") == "resistance"
                  else f"Revoir la charge ou les dimensions pour « {nom} ».")  # fmt: skip
        d.cause, d.nom_cause = causes(cle, pire_ko), nom
    elif niveau == "ok":
        action = "Aucune action requise : tous les critères sont admissibles."
    elif niveau == "info":
        action = "Ce calcul donne des valeurs, sans critère de conformité."
    d.action = action
    d.avertissement = avertissement(cle, saisie)
    return d
