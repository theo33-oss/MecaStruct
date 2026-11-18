"""Les scripts et feuilles de style tiers de docs/ (CDN, version figée) ont toujours l'empreinte `integrity` écrite dans la page.

Lit docs/index.html et docs/app.js, télécharge chaque adresse https qui porte un attribut integrity, recalcule sa
somme sha384 et signale tout écart (fichier modifié sur le CDN, ou empreinte périmée après un changement de version).
Internet nécessaire. Usage : python application/tools/verifier_sri.py ; code de sortie 1 s'il y a un écart.
"""

import base64
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
# adresse puis empreinte, dans une balise HTML (src|href …) ou dans un objet JS (src: "…", integrity: "…")
MOTIF = re.compile(r"""(?:src|href)\s*[=:]\s*["'](https://[^"']+)["'][^>]*?integrity\s*[=:]\s*["'](sha384-[^"']+)["']""", re.S)


def somme(adresse: str) -> str:
    with urllib.request.urlopen(adresse, timeout=60) as r:  # noqa: S310 : adresses https écrites dans la page
        return "sha384-" + base64.b64encode(hashlib.sha384(r.read()).digest()).decode()


def main() -> int:
    trouvees = []
    for nom in ("index.html", "app.js"):
        trouvees += MOTIF.findall((DOCS / nom).read_text(encoding="utf-8"))
    if not trouvees:
        print("Aucune empreinte integrity trouvée : la page n'est plus protégée.")
        return 1
    ecarts = 0
    for adresse, attendue in trouvees:
        obtenue = somme(adresse)
        etat = "ok" if obtenue == attendue else "ÉCART"
        ecarts += obtenue != attendue
        print(f"{etat:6s} {adresse}")
    # toute adresse de CDN de la page doit être protégée
    nues = [u for nom in ("index.html",) for u in re.findall(r'<script[^>]+src="(https://[^"]+)"[^>]*>', (DOCS / nom).read_text(encoding="utf-8"))
            if u not in {a for a, _ in trouvees}]
    for u in nues:
        print(f"SANS EMPREINTE {u}")
    return 1 if ecarts or nues else 0


if __name__ == "__main__":
    sys.exit(main())
