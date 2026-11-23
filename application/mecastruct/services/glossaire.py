"""Glossaire des symboles : le même sur le site (page « Glossaire », calcul « glossaire » du pont) et sur le bureau.

Rien n'est écrit à la main ici : chaque entrée est lue dans ce que l'application affiche déjà.
  1. les champs et les colonnes des formulaires du pont (libellé, unité, aide) : « Couple C », « b, largeur selon z » ;
     pour un symbole seul (« E », « Re »), le nom est le début de l'aide du champ ;
  2. les variables des fiches de formules du « Formulaire rapide » (« σe : limite élastique (Pa) »), pour la fiche
     ouverte par défaut sur chaque page (services/fiches.py, PAR_CALCUL), et pour un symbole sans nom, le nom que toutes
     les fiches lui donnent d'un commun accord.
Un symbole dont aucun de ces textes ne donne le nom n'entre pas dans le glossaire : `sans_nom()` le liste, pour que
l'auteur le définisse. Un même symbole peut avoir deux sens (N : effort normal, ou fréquence de rotation) : une entrée
par sens, avec ses pages.
"""

import re

from mecastruct.core.utils import load_json
from mecastruct.services.fiches import PAR_CALCUL

# calcul du pont → page du site (docs/app.js, PAGES)
PAGE_DU_CALCUL = {
    "aju": "ajustements", "fre": "frettage", "pal": "paliers", "rlt": "roulements", "rlt_ens": "roulements",
    "rlt_regle": "roulements", "eng": "engrenages", "trn": "engrenages", "epi": "engrenages", "frn": "freins",
    "emb": "freins", "mot": "moteur", "beam": "poutres", "ossature": "poutres", "truss": "treillis",
    "sec": "sections-page", "tra": "sollicitations", "cis": "sollicitations", "tor": "sollicitations",
    "fle": "sollicitations", "fla": "flambage", "ten": "tenseurs", "hoo": "hooke", "jau": "hooke",
}  # fmt: skip
ORDRE_PAGES = ("poutres", "treillis", "flambage", "sections-page", "sollicitations", "tenseurs", "hooke", "ajustements",
               "frettage", "paliers", "roulements", "engrenages", "freins", "moteur")  # ordre du menu du site

# lettre grecque → nom de la commande LaTeX
GREC = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "varepsilon", "θ": "theta", "λ": "lambda", "μ": "mu",
    "µ": "mu", "ν": "nu", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "varphi", "ω": "omega", "η": "eta", "π": "pi",
    "Σ": "Sigma", "Ω": "Omega", "Φ": "Phi", "Γ": "Gamma", "Θ": "Theta",
}  # fmt: skip
_LETTRE = "A-Za-zΑ-Ωα-ωµ"
# un symbole : une lettre (ou ΔX), puis indices ou lettres collés (Fa, σxx, γM0, Nb,Rd, L', q(x))
_JETON = rf"Δ?[{_LETTRE}][{_LETTRE}0-9,']{{0,6}}(?:\([a-z]\))?"
_SYMBOLE = rf"{_JETON}(?: = [{_LETTRE}0-9/]+)?"  # « tw = a », « k = b/m » : le symbole et sa définition
_MOT = re.compile(r"[A-ZÉ]?[a-zéèêàùç]{3,}")  # un mot français ordinaire n'est pas un symbole (« Bague », « mat »)
_NON_SYMBOLES = {"id", "Nom", "Cas", "Loi", "Type", "Plan"}  # libellés de colonnes ou de listes, pas des grandeurs
_NON_NOMS = {"bloqué", "utiliser", "nœud", "nom"}  # « Bloqué x », « Utiliser S(x) », « Nœud i » : consignes ou indices
_UNITE = re.compile(r"[^\s=<>≈,;]{1,12}")


def _est_symbole(t: str) -> bool:
    if t in _NON_SYMBOLES or not re.fullmatch(_SYMBOLE, t):
        return False
    return not _MOT.fullmatch(t) or bool(re.search(r"[α-ωΑ-Ω]", t))


def _grandeur(nom: str) -> str:
    nom = " ".join(nom.split()).strip(" .;")
    return nom[:1].upper() + nom[1:]


def _cle(nom: str) -> str:
    return " ".join(nom.casefold().split())


def latex(symbole: str) -> str:
    """Écriture LaTeX d'un symbole : lettre grecque en commande, le reste en indice (Mfz → M_{fz}, σxx → \\sigma_{xx})."""

    def jeton(t: str) -> str:
        delta = ""
        if t.startswith("Δ") and len(t) > 1:
            delta, t = r"\Delta ", t[1:]
        tete, reste = t[0], t[1:]
        arg = prime = ""
        if m := re.fullmatch(r"(.*)\(([a-z])\)", reste):
            reste, arg = m.group(1), f"({m.group(2)})"
        if reste.endswith("'"):
            reste, prime = reste[:-1], "'"
        tete = "\\" + GREC[tete] if tete in GREC else tete
        if reste:
            sous = "".join("\\" + GREC[c] + " " if c in GREC else c for c in reste).strip()
            mot = len(reste) >= 3 and reste.isalpha() and reste.islower() and reste.isascii()
            tete += f"_{{\\mathrm{{{reste}}}}}" if mot else f"_{{{sous}}}"
        elif tete.startswith("\\") and (prime or arg):
            tete += " "
        return delta + tete + prime + arg

    return " = ".join("/".join(jeton(x) for x in partie.split("/")) for partie in symbole.split(" = "))


# ------------------------------------------------------------------------------------------------ lecture des textes


def _nom_de_l_aide(aide: str) -> tuple[str, str]:
    """(nom, reste de l'aide) pour un champ dont le libellé est un symbole seul. « Module d'Young : rigidité… » → nom
    « Module d'Young » ; « Limite élastique. » → nom « Limite élastique ». Rien si l'aide ne commence pas par un nom court."""
    phrase = " ".join(aide.split())
    if not phrase:
        return "", ""
    premiere = re.split(r"(?<=[.!?])\s+(?=[A-ZÉÀ])", phrase, maxsplit=1)[0]
    if " : " in premiere:
        avant, _, apres = phrase.partition(" : ")
        reste = _grandeur(apres)
    else:
        court = re.match(r"[^(]*\([^()]{1,8}\)", premiere)  # « … dans le plan (x,y) » : cette précision fait partie du nom
        avant = court.group(0) if court and "," not in court.group(0).split("(")[0] else premiere.split(" (")[0].split(",")[0]
        avant = avant.rstrip(".")
        reste = "" if avant == premiere.rstrip(".") and premiere == phrase else phrase
    if len(avant) > 60 or re.search(r"[=≤≥<>\d;]", avant) or avant.startswith(("Remplit", "Recopie")):
        return "", phrase
    return avant, reste


_GENERIQUES = {"largeur", "hauteur", "épaisseur", "longueur", "diamètre", "rayon", "force", "couple", "pression", "vitesse"}


def _nom_du_descripteur(texte: str) -> str:
    """Nom lu dans ce que le libellé écrit après le symbole : deux mots au moins (ou une grandeur courante), sans signe ni
    condition ; la précision finale entre parenthèses reste si c'est un mot (« moment équivalent (flambement) »)."""
    texte = " ".join(texte.split())
    sans_parentheses = re.sub(r"\s*\([^()]*\)", "", texte).strip()
    mots = sans_parentheses.split()
    if not mots or re.search(r"[=≤≥<>]|^\d", sans_parentheses):
        return ""
    if len(mots) < 2 and sans_parentheses.casefold() not in _GENERIQUES:
        return ""
    precision = re.search(r"\(([^()]*)\)$", texte)
    garde = texte if precision and not re.search(r"[=≤≥<>\d,]", precision.group(1)) and len(precision.group(1)) > 3 else sans_parentheses
    return _grandeur(garde)


def _lire_libelle(libelle: str, aide: str) -> tuple[str, str, str, str, str]:
    """(symbole, nom, unité lue dans le libellé, aide, origine du nom) ; symbole vide si le libellé n'en a pas."""
    lib = " ".join(str(libelle).split())

    def tete(sym: str, aide_: str = aide) -> tuple[str, str]:
        """« tw = a » : symbole tw, la définition passe en tête de l'aide."""
        if " = " in sym:
            gauche = sym.split(" = ")[0]
            return gauche, (sym + (". " + aide_ if aide_ else "")).strip()
        return sym, aide_

    # « σ (MPa) », « Fx (kN) » : symbole puis unité
    if m := re.fullmatch(rf"({_SYMBOLE}) \(([^()]*)\)", lib):
        if _est_symbole(m.group(1)) and _UNITE.fullmatch(m.group(2)):
            sym, a = tete(m.group(1))
            nom, reste = _nom_de_l_aide(a)
            return sym, nom, m.group(2), reste, "aide"
    # « b, largeur selon z », « tw = a, âme » : le nom suit la virgule ; « N : traction > 0 » : ce qui suit précise souvent
    # la convention, pas le nom (un seul mot, une condition ou un signe : refusé)
    for motif, refus in ((rf"({_SYMBOLE}), (.+)", "refus"), (rf"({_SYMBOLE}) : (.+)", "")):
        if (m := re.fullmatch(motif, lib)) and _est_symbole(m.group(1)):
            sym, a = tete(m.group(1))
            nom = _nom_du_descripteur(m.group(2))
            if not nom:
                nom, _ = _nom_de_l_aide(a)  # le descripteur ne suffit pas : l'aide du champ peut donner le nom
                return sym, nom, "", a, "aide" if nom else refus
            return sym, nom, "", a, "libelle"
    # symbole seul, ou suivi d'une précision entre parenthèses : « E », « Re », « N (> 0 traction) », « Kf (0 = Kf = Kt) »
    if m := re.fullmatch(rf"({_SYMBOLE})(?: \(.*\))?", lib):
        if _est_symbole(m.group(1)):
            sym, a = tete(m.group(1))
            nom, reste = _nom_de_l_aide(a)
            return sym, nom, "", reste, "aide"
    # « Couple C », « Coefficient de sécurité s » : le nom précède le symbole
    if m := re.fullmatch(rf"(.+?) ({_SYMBOLE})", lib):
        nom = m.group(1)
        if _est_symbole(m.group(2)) and not re.search(r"\b(de|du|des|la|le|à|au)$", nom) and _cle(nom) not in _NON_NOMS:
            sym, a = tete(m.group(2))
            return sym, _grandeur(nom), "", a, "libelle"
    return "", "", "", aide, ""


def _premiere_phrase(texte: str) -> str:
    texte = " ".join(str(texte).split())
    court = re.split(r"(?<!\bp\.)(?<=[.!?])\s+(?=[A-ZÉÀ])", texte, maxsplit=1)[0]
    if len(court) > 200:
        court = court.split(" ; ")[0]
        court = court if len(court) <= 200 else ""
        court = court + "." if court and not court.endswith((".", ")")) else court
    return court


def _unite_de_fiche(texte: str) -> str:
    """« Pa » ; « N, > 0 en traction » → « N » ; « – » → « »."""
    unite = texte.split(",")[0].strip()
    return unite if _UNITE.fullmatch(unite) and unite not in {"–", "-"} and unite[0] not in "≈<>=" else ""


def _variables_des_fiches() -> dict[str, dict[str, list[tuple[str, str]]]]:
    """fiche → symbole → [(nom, unité)] : segments « σe : limite élastique (Pa) » des variables des fiches de formules."""
    sortie: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for cle, feuille in load_json("formula_sheets.json")["sheets"].items():
        for f in feuille:
            for segment in re.split(r"\s;\s", str(f.get("vars") or "")):
                m = re.fullmatch(rf"({_JETON}) : (.+?)(?: \(([^()]*)\))?\.?", segment.strip())
                if not m or not _est_symbole(m.group(1)):
                    continue
                nom = m.group(2).strip()
                if re.search(r"[=<>(),;]", nom):
                    continue
                sortie.setdefault(cle, {}).setdefault(m.group(1), []).append((_grandeur(nom), _unite_de_fiche(m.group(3) or "")))
    return sortie


def _champs(formulaires: dict) -> list[dict]:
    """Champs et colonnes de tableau de tous les formulaires : {calcul, libelle, unite, aide}."""
    sortie = []
    for calcul, f in formulaires.items():
        for g in f["groupes"]:
            for c in g["champs"]:
                if c["type"] == "tableau":
                    sortie += [{"calcul": calcul, "libelle": k["libelle"], "unite": "", "aide": ""} for k in c["colonnes"]]
                elif c["type"] in ("nombre", "liste", "case", "texte"):
                    sortie.append({"calcul": calcul, "libelle": c["libelle"], "unite": c.get("unite", ""), "aide": c.get("aide", "")})
    return sortie


def _formulaires() -> dict:
    from mecastruct.pont import noyau

    noyau._assurer()
    try:
        noyau.charger("structures")  # scipy, shapely et jinja2 : sans eux, seuls les formulaires des machines sont lus
    except ImportError:
        pass
    return noyau.tous_formulaires()


def _cle_tri(symbole: str) -> tuple:
    tete = symbole.lstrip("Δ")[:1]
    return (tete in GREC, GREC.get(tete, tete).casefold(), tete.islower(), symbole)


_CACHE: dict[int, tuple] = {}  # nombre de formulaires lus → résultat (la famille « structures » peut arriver après)


def _construire() -> tuple[tuple[dict, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    formulaires = _formulaires()
    if len(formulaires) not in _CACHE:
        _CACHE[len(formulaires)] = _calculer(formulaires)
    return _CACHE[len(formulaires)]


def _calculer(formulaires: dict) -> tuple[tuple[dict, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    fiches = _variables_des_fiches()
    entrees: dict[tuple[str, str], dict] = {}
    nus: dict[str, set[str]] = {}  # symbole → pages où aucun nom n'a été trouvé

    def nom_de_fiche(symbole: str, calcul: str, autres: bool) -> tuple[str, str]:
        """Nom (et unité) de la fiche ouverte par défaut sur la page du calcul ; avec `autres`, à défaut, le nom que deux
        fiches au moins donnent d'un commun accord (l'une peut préciser l'autre : « limite élastique en traction »)."""
        propres = fiches.get(PAR_CALCUL.get(calcul, ""), {}).get(symbole, [])
        if propres:
            return propres[0]
        if not autres:
            return "", ""
        par_fiche = [d for f in fiches.values() if (d := f.get(symbole))]
        noms = sorted({(_cle(n), n, u) for d in par_fiche for n, u in d}, key=lambda t: len(t[0]))
        if len(par_fiche) >= 2 and noms and all(t[0].startswith(noms[0][0]) for t in noms):
            return noms[0][1], noms[0][2]
        return "", ""

    def ajouter(symbole: str, nom: str, unite: str, aide: str, page: str, source: str) -> None:
        e = entrees.setdefault((symbole, _cle(nom)), {"symbole": symbole, "latex": latex(symbole), "nom": nom, "unite": [],
                                                      "pages": [], "aide": "", "source": source})  # fmt: skip
        if unite and unite not in e["unite"]:
            e["unite"].append(unite)
        if page not in e["pages"]:
            e["pages"].append(page)
        if aide and not e["aide"] and _cle(aide) != _cle(nom):
            e["aide"] = aide

    for ch in _champs(formulaires):
        calcul = ch["calcul"]
        page = PAGE_DU_CALCUL[calcul]
        symbole, nom, unite_lib, aide, source = _lire_libelle(ch["libelle"], ch["aide"])
        if not symbole:
            continue
        nom_fiche, unite_fiche = nom_de_fiche(symbole, calcul, autres=source != "refus")
        if not nom:
            nom, source = nom_fiche, "fiche"
        if not nom:
            nus.setdefault(symbole, set()).add(page)
            continue
        unite = ch["unite"] or unite_lib or (unite_fiche if _cle(nom) == _cle(nom_fiche) else "")
        ajouter(symbole, nom, unite, _premiere_phrase(aide), page, source)

    # variables des fiches : les pages dont la fiche ouverte par défaut les contient
    for calcul, cle_fiche in PAR_CALCUL.items():
        for symbole, defs in fiches.get(cle_fiche, {}).items():
            ajouter(symbole, defs[0][0], defs[0][1], "", PAGE_DU_CALCUL[calcul], "fiche")

    rang = {p: i for i, p in enumerate(ORDRE_PAGES)}
    liste = sorted(entrees.values(), key=lambda e: (_cle_tri(e["symbole"]), e["nom"]))
    for e in liste:
        e["unite"] = " ; ".join(e["unite"])
        e["pages"] = sorted(e["pages"], key=lambda p: rang[p])
    avec_nom = {(e["symbole"], p) for e in liste for p in e["pages"]}
    manque = []
    for symbole, pages in nus.items():
        reste = sorted((p for p in pages if (symbole, p) not in avec_nom), key=lambda p: rang[p])
        if reste:
            manque.append((symbole, tuple(reste)))
    return tuple(liste), tuple(sorted(manque, key=lambda x: _cle_tri(x[0])))


def entrees() -> list[dict]:
    """Entrées du glossaire : {symbole, latex, nom, unite, pages (identifiants du site), aide, source}."""
    return [dict(e, pages=list(e["pages"])) for e in _construire()[0]]


def sans_nom() -> list[tuple[str, tuple[str, ...]]]:
    """(symbole, pages) des champs de formulaire dont aucun libellé, aide ni fiche ne donne le nom : à définir par l'auteur."""
    return list(_construire()[1])
