"""Modes de ruine d'un calcul, sous une seule forme : valeur, limite, coefficient de sécurité obtenu et demandé.

Lecture seule des résultats des services (aucun calcul n'est refait ni modifié). Le site en tire le diagramme des modes
de ruine, l'export bloc-notes et la feuille « Critères » de l'Excel de validation.

Une ligne = {"mode", "valeur", "limite", "unite", "s_demande", "s_obtenu", "taux", "ok", "sens"} :
- sens « max » : la valeur doit rester sous la limite (contrainte, pression) ; « min » : au-dessus (durée de vie) ;
- limite : valeur admissible, coefficient de sécurité demandé déjà compris (σadm = Re/s) ;
- s_obtenu : coefficient de sécurité réel (Re/σ) ; le critère est admissible quand s_obtenu ≥ s_demande ;
- taux : part de l'admissible utilisée (1 = à la limite) ;
- genre : « resistance » (contrainte face à la limite du matériau : on parle de coefficient de sécurité) ou
  « limite » (durée, rigidité, vitesse, pression admissible, couple : on parle de marge) ;
- groupe : étude à laquelle la ligne appartient quand la page en réunit plusieurs (cisaillement, matage, clavette…).
Pour ajouter un critère : une ligne de plus dans la fonction du calcul, rien d'autre à toucher.
"""

import math
import re

_UNITE = re.compile(r"\s*\(([^()]*)\)\s*$")
_NOMS_LONGS = {"P": "Pression P", "V": "Vitesse de glissement V"}


def ligne(mode: str, valeur, limite, unite: str = "", s_demande: float = 1.0, sens: str = "max", ok=None,
          genre: str = "resistance", groupe: str = "") -> dict | None:
    """Une ligne de critère, ou None si la valeur ou la limite manque (NaN, zéro, absente)."""
    try:
        valeur, limite, s_demande = abs(float(valeur)), abs(float(limite)), float(s_demande)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(valeur) and math.isfinite(limite)) or limite <= 0 or s_demande <= 0:
        return None
    if sens == "max":
        taux = valeur / limite
        obtenu = limite * s_demande / valeur if valeur > 0 else math.inf
    else:
        taux = limite / valeur if valeur > 0 else math.inf
        obtenu = valeur * s_demande / limite
    admissible = bool(taux <= 1.0 + 1e-12) if ok is None else bool(ok)
    return {"mode": mode, "valeur": valeur, "limite": limite, "unite": unite, "s_demande": s_demande,
            "s_obtenu": obtenu, "taux": taux, "ok": admissible, "sens": sens, "genre": genre, "groupe": groupe}  # fmt: skip


def verdict(status: str):
    """Verdict lu dans la ligne d'état d'un calcul : « NON vérifié » → False, « vérifié » → True, sinon None."""
    if re.search(r"NON vérifi", status):
        return False
    return True if re.search(r"vérifi", status) else None


def ossature(contraintes: dict, limites: dict) -> list[dict]:
    """Ossature 3D : contrainte de la pièce la plus sollicitée (Pa) face à Re (Pa), sans coefficient de sécurité."""
    lignes = [ligne(f"Contrainte σ max, pièce {i}", c["sigma_max"] / 1e6, (limites.get(i) or 0) / 1e6, "MPa")
              for i, c in contraintes.items() if c["sigma_max"] is not None]  # fmt: skip
    return trier(_garde(lignes))[:1]


def completer_cisaillement(status: str, ok, crit: list[dict]) -> tuple[str, object]:
    """Ligne d'état et verdict du Cisaillement, complétés par tous les modes de ruine de la page.

    Le calcul ne juge que τ max et la pression de matage : Jourawski, la clavette et la goupille n'étaient dans
    le verdict ni en toutes lettres ni dans « vérifié » (un mode rouge dans le diagramme laissait « vérifié »).
    Chaque étude (Jourawski, Clavette, Goupille) est ajoutée à la ligne d'état, et un seul mode non admissible rend
    le calcul « NON vérifié ».
    """
    for nom, repere in (("Jourawski", lambda c: c["mode"].startswith("Jourawski")),
                        ("Clavette", lambda c: c.get("groupe") == "Clavette"),
                        ("Goupille", lambda c: c.get("groupe") == "Goupille")):  # fmt: skip
        modes = [c for c in crit if repere(c)]
        if modes:
            status += f" — {nom} : {'vérifié' if all(c['ok'] for c in modes) else 'NON vérifié'}"
    if any(not c["ok"] for c in crit):
        ok = False
    return status, ok


def _garde(lignes) -> list[dict]:
    return [x for x in lignes if x is not None]


def depuis_table(table, prefixe: str = "") -> list[dict]:
    """Critères d'un tableau « Contrôle / Valeur / Limite / Résultat » (paliers, moteur) : valeur ≤ limite."""
    if table is None or not {"Contrôle", "Valeur", "Limite"} <= set(table.columns):
        return []
    lignes = []
    for r in table.to_dict("records"):
        nom = str(r["Contrôle"])
        m = _UNITE.search(nom)
        unite = m.group(1) if m else ""
        ok = None if "Résultat" not in r else str(r["Résultat"]).strip().upper() == "OK"
        nom = _UNITE.sub("", nom)
        for court, long in _NOMS_LONGS.items():  # « P », « V » seuls ne disent rien dans le diagramme
            nom = re.sub(rf"(^|: ){re.escape(court)}( |$)", rf"\g<1>{long}\g<2>", nom, count=1)
        lignes.append(ligne(prefixe + nom, r["Valeur"], r["Limite"], unite, ok=ok, genre="limite"))
    return _garde(lignes)


# ------------------------------------------------------------------------------------------------- structures (RdM)


def _beam(s, calc):
    c = calc["check"]
    b, sh = c["bend"], c.get("shear")
    lignes = [ligne("Flexion composée : Kt·σ max", b["sigmaMaxKt"] / 1e6, b["sigmaAdm"] / 1e6, "MPa", s["s"])]
    if sh:
        if sh.get("mode") == "jourawski":  # section quelconque : τ max de Jourawski contre Re/(2·s), sécurité s comme la flexion
            lignes.append(ligne("Cisaillement : τ max (Jourawski)", sh["tauMax"] / 1e6, sh["tauAdm"] / 1e6, "MPa", s["s"]))
        else:
            lignes.append(ligne("Effort tranchant : VEd / Vpl,Rd", sh["VEd"] / 1e3, sh["Vpl"] / 1e3, "kN", ok=sh["ok"], genre="limite"))
    return lignes


def _tra(s, calc):
    r = calc["result"]
    lignes = [ligne("Résistance : σ max", r["sigmaMax"] / 1e6, r["sigmaAdm"] / 1e6, "MPa", s["s"])]
    if s.get("dLmax", 0) > 0:
        lignes.append(ligne("Rigidité : allongement ΔL", r["dL"]["analytique"] * 1e3, s["dLmax"], "mm", genre="limite"))
    return lignes


def _cis(s, calc):
    r, ex = calc["result"], calc.get("extras") or {}
    adm = r["shear"]["tauAdm"] / 1e6
    g = "Cisaillement simple et Jourawski"
    lignes = [ligne("Cisaillement : τ max", r["shear"]["tauMax"] / 1e6, adm, "MPa", s["s"], groupe=g),
              ligne("Jourawski : τ max dans la section", r["jour"]["tauMax"] / 1e6, adm, "MPa", s["s"], groupe=g),
              ligne("Pression de matage P", r["bearing"]["P"] / 1e6, s["Padm"], "MPa", genre="limite", groupe="Matage")]  # fmt: skip
    for cle, nom in (("key", "Clavette"), ("pin", "Goupille")):
        e = (ex.get(cle) or {}).get("result") or {}
        if "okP" in e:
            lignes.append(ligne("Pression de matage P", e["P"] / 1e6, s["Padm"], "MPa", genre="limite", groupe=nom))
        if "okTau" in e:
            lignes.append(ligne("Cisaillement τ", e["tau"] / 1e6, e["tauAdm"] / 1e6, "MPa", s["s"], groupe=nom))
    return lignes


def _tor(s, calc):
    r = calc["result"]
    lignes = [ligne("Résistance : τ max", r["tauMax"] / 1e6, r["tauAdm"] / 1e6, "MPa", s["s"])]
    if s.get("thetaAdm", 0) > 0:
        lignes.append(ligne("Rigidité : angle unitaire θ", math.degrees(r["theta"]), s["thetaAdm"], "°/m", genre="limite"))
    return lignes


def _fle(s, calc):
    b = calc["result"]["bend"]
    return [ligne("Flexion composée : Kt·σ max", b["sigmaMaxKt"] / 1e6, b["sigmaAdm"] / 1e6, "MPa", s["s"])]


def _fla(s, calc):
    a = calc["result"]["analysis"]
    return [ligne("Flambage : charge P", a["P"] / 1e3, a["Padm"] / 1e3, "kN", a["s"])]


def _ten(s, calc):
    c = calc["result"]["criteria"]
    return [ligne("Von Mises : σ équivalente", c["sigmaEqVM"] / 1e6, c["sigmaAdm"] / 1e6, "MPa", s["s"]),
            ligne("Tresca : σ équivalente", c["sigmaEqTresca"] / 1e6, c["sigmaAdm"] / 1e6, "MPa", s["s"]),
            ligne("Rankine : σ normale max (fragiles)", c["sigmaMaxNormal"] / 1e6, c["sigmaRAdm"] / 1e6, "MPa", s["s"])]  # fmt: skip


# -------------------------------------------------------------------------------------------- éléments de machines


def _fre(s, res):
    r = res["result"]
    lignes = []
    for nom, sig, coef in (("Arbre", r.get("sigmaArbre"), r.get("sArbre")), ("Moyeu", r.get("sigmaMoyeu"), r.get("sMoyeu"))):
        if sig and coef:
            lignes.append(ligne(f"{nom} : σ équivalente au serrage maxi", sig, sig * coef, "MPa"))
    lignes.append(ligne("Adhérence : couple transmissible au serrage mini", r.get("couple"), s["C"] * s["s"], "N·m",
                        sens="min", genre="limite") if s.get("C", 0) > 0 and not s.get("Fa") else None)  # fmt: skip
    return lignes


def _rlt(s, res):
    return [ligne("Durée de vie Lnh", res["result"]["Lnh"], s["Lh"], "h", sens="min", genre="limite")]


def _eng(s, res):
    r = res["result"]
    return [ligne("Flexion en pied de dent : σ", r["sigma"], r["Rpe"], "MPa", s["s"])]


def _emb(s, res):
    return [ligne("Couple d'embrayage CT face au couple moteur", res["result"]["CT"], s["CM"], "N·m", genre="limite")]


def _table(_s, res):
    return depuis_table(res.get("tables", {}).get("Synthèse"))


def _truss(s, calc):
    r = calc["result"]
    c, nm, B = r["check"], r["truss"]["names"], r["truss"]["bars"]

    def barre(k):
        return f"barre {k + 1} ({nm[int(B[k][0]) - 1]}–{nm[int(B[k][1]) - 1]})"

    lignes = []
    if c["iSigma"] is not None:
        k = c["iSigma"]
        lignes.append(ligne(f"Résistance : σ max, {barre(k)}", c["sigma"][k] / 1e6, c["sigmaAdm"] / 1e6, "MPa", s["s"]))
    if c["iFlambage"] is not None:
        k = c["iFlambage"]
        N = abs(r["tsol"]["N"][k])
        lignes.append(ligne(f"Flambage d'Euler : {barre(k)} comprimée", N / 1e3, c["Pcr"][k] / s["s"] / 1e3, "kN", s["s"]))
    return lignes


_PAR_CALCUL = {"truss": _truss, "Tr": _truss, "beam": _beam, "Beam": _beam, "tra": _tra, "Tra": _tra, "cis": _cis, "Cis": _cis, "tor": _tor, "Tor": _tor,
               "fle": _fle, "Fle": _fle, "fla": _fla, "Fla": _fla, "ten": _ten, "Ten": _ten,
               "fre": _fre, "pal": _table, "mot": _table, "rlt": _rlt, "eng": _eng, "emb": _emb}  # fmt: skip


def criteres(ident: str, saisie: dict, res: dict) -> list[dict]:
    """Critères du calcul `ident` (identifiant du pont ou onglet du bureau), le plus défavorable en premier.

    Entrées : saisie (unités d'affichage) et résultat du service. Sortie : liste vide si le calcul n'a pas de critère
    (treillis, ossature, sections, Hooke, jauges, ajustements, trains) ou si le résultat est incomplet.
    """
    f = _PAR_CALCUL.get(ident)
    if f is None:
        return []
    try:
        lignes = _garde(f(saisie, res))
    except (KeyError, TypeError, ValueError, AttributeError):
        return []
    return trier(lignes)


def trier(lignes: list[dict]) -> list[dict]:
    """Études dans l'ordre de la page ; dans une étude, le mode le plus sollicité en premier."""
    ordre = {g: i for i, g in enumerate(dict.fromkeys(x["groupe"] for x in lignes))}
    return sorted(lignes, key=lambda x: (ordre[x["groupe"]], -x["taux"]))


def eurocode(e: dict) -> list[dict]:
    """Critères de la vérification Eurocode 3 : chaque taux (effort / résistance) doit rester sous 1."""
    def taux(d, cle="ratio"):
        return None if not d else d.get(cle)

    inter = e.get("inter") or {}
    paires = [("Résistance en flexion : MEd / MRd", e.get("ratioM")), ("Effort tranchant : VEd / Vpl,Rd", e.get("ratioV")),
              ("Déversement : MEd / Mb,Rd", taux(e.get("ltb"))), ("Effort normal et flexion", taux(e.get("axial"))),
              ("Flambement : NEd / Nb,Rd", taux(e.get("buck"))), ("Interaction N + M (6.61)", inter.get("ratio61")),
              ("Interaction N + M (6.62)", inter.get("ratio62")), ("Voilement de l'âme : VEd / Vb,Rd", taux(e.get("web")))]  # fmt: skip
    lignes = _garde(ligne(nom, t, 1.0, "", genre="limite") for nom, t in paires if t is not None)
    return sorted(lignes, key=lambda x: -x["taux"])


def fatigue(r: dict, s: float) -> list[dict]:
    """Critère de Goodman : coefficient de sécurité en fatigue n face au coefficient demandé s."""
    n = float(r["n"])
    if not math.isfinite(n) or n <= 0 or s <= 0:
        return []
    return [{"mode": "Fatigue (Goodman) : coefficient n", "valeur": n, "limite": float(s), "unite": "", "s_demande": float(s),
             "s_obtenu": n, "taux": s / n, "ok": bool(n >= s), "sens": "min", "genre": "resistance", "groupe": ""}]  # fmt: skip
