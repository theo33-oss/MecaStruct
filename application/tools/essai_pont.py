"""Lance chaque calcul du pont avec ses valeurs de départ et affiche verdict, durée et présence des graphiques.

Usage (depuis application/) : python tools/essai_pont.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mecastruct import pont  # noqa: E402


def appel(ident: str, saisie: dict | None = None) -> dict:
    return json.loads(pont.appeler(ident, json.dumps(saisie or {})))


def main() -> int:
    print("Calculs :", ", ".join(json.loads(pont.catalogue())))
    echecs = 0
    for ident, f in appel("formulaires")["sortie"].items():
        t = time.perf_counter()
        r = appel(ident, f["defaut"])
        dt = (time.perf_counter() - t) * 1000
        a = appel(ident + ".apercu", f["defaut"]) if f.get("apercu") else {"ok": None}
        if a["ok"] and not (a["sortie"] or {}).get("data"):
            a["ok"] = False
        s = r.get("sortie") or {}
        texte = s.get("status") or r.get("erreur", "")
        echecs += (not r["ok"]) + (a["ok"] is False)
        print(f"{ident:10s} calcul={'ok' if r['ok'] else 'ÉCHEC'} schéma={a['ok']} graphique={bool(s.get('figure'))} "
              f"{dt:6.0f} ms  {texte[:80]}")  # fmt: skip
    print("Frettage, norme Ø100 :", appel("fre.norme", {"d": 100})["sortie"])
    g = appel("conv.catalogue")["sortie"]["grandeurs"][0]
    c = appel("conv", {"grandeur": g["nom"], "valeur": 1, "de": g["unites"][g["de"]], "vers": g["unites"][g["vers"]]})
    print(f"Convertisseur : 1 {g['unites'][g['de']]} = {c['sortie']['texte']} {g['unites'][g['vers']]}")
    print("Saisie fausse :", appel("aju", {"d": -5, "alesage": "H", "qa": 7, "arbre": "r", "qb": 6}))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
