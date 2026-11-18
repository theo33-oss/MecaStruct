"""Fabrique docs/mecastruct.zip : le calcul de l'application (sans Qt) que le site charge dans le navigateur.

À relancer après toute modification de application/mecastruct (core, services, plots, pont), de application/data,
ou des fichiers du site (docs/*.js, docs/js/*.js, style.css). Il met aussi une empreinte dans l'adresse de chaque
script de docs/index.html (?v=…) : GitHub Pages fait garder les fichiers 10 minutes, et sans cela un visiteur
recevrait de nouveaux scripts avec d'anciens. Usage : python construire_web.py
"""

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

racine = Path(__file__).resolve().parent
appli = racine / "application"
docs = racine / "docs"
sortie = docs / "mecastruct.zip"
EXCLUS = {"bureau", "__pycache__"}  # l'interface Qt et les caches
EXTENSIONS = {".py", ".json", ".j2"}
DATE_FIXE = (2026, 1, 1, 0, 0, 0)  # même contenu → même zip, octet pour octet (pas de faux changement dans git)


def fichiers():
    for dossier in ("mecastruct", "data"):
        for f in sorted((appli / dossier).rglob("*")):
            if f.is_file() and not EXCLUS & set(f.relative_to(appli).parts) and f.suffix in EXTENSIONS:
                yield f


with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in fichiers():
        info = zipfile.ZipInfo(f.relative_to(appli).as_posix(), DATE_FIXE)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, f.read_bytes().replace(b"\r\n", b"\n"))
print(f"{sortie.relative_to(racine)} : {sortie.stat().st_size / 1024:.0f} Ko")

# une seule source : l'icône vient de application/data, les limites de LIMITES.md, les captures de application/captures
shutil.copyfile(appli / "data" / "icone.svg", docs / "icone.svg")
shutil.copyfile(racine / "LIMITES.md", docs / "LIMITES.md")
CAPTURES = {"poutres": "poutres_calcul", "treillis": "treillis_calcul", "flambage": "flambage_calcul",
            "sections": "sections_calcul", "sollicitations_0": "sollicitations_0_calcul", "tenseurs": "tenseurs_calcul",
            "hooke_jauges_0": "hooke_jauges_0_calcul", "base_de_donnees": "base_de_donnees_calcul",
            "references": "references_calcul"}  # fmt: skip
try:
    from PIL import Image

    (docs / "captures").mkdir(exist_ok=True)
    for nom, source in CAPTURES.items():
        cible = docs / "captures" / f"{nom}.jpg"
        png = appli / "captures" / f"{source}.png"
        if not cible.exists() or cible.stat().st_mtime < png.stat().st_mtime:
            im = Image.open(png).convert("RGB")
            im.thumbnail((1400, 1400))
            im.save(cible, "JPEG", quality=80, optimize=True, progressive=True)
    print(f"captures : {len(CAPTURES)} images")
except ImportError:
    print("captures : Pillow absent, images non refaites")

# numéro de version : une seule source, mecastruct/__init__.py
version = re.search(r'__version__ = "([^"]+)"', (appli / "mecastruct" / "__init__.py").read_text(encoding="utf-8")).group(1)
app_js = docs / "app.js"
texte_app = app_js.read_text(encoding="utf-8")
nouveau_app = re.sub(r'const VERSION = "[^"]*";', f'const VERSION = "{version}";', texte_app)
if nouveau_app != texte_app:
    app_js.write_text(nouveau_app, encoding="utf-8", newline="\n")
print(f"version {version}")

def empreinte(chemin: str) -> str:
    return hashlib.sha1((docs / chemin).read_bytes()).hexdigest()[:8]


# service worker : un nom de cache par version du site, les anciennes copies sont effacées
sw = docs / "sw.js"
texte_sw = sw.read_text(encoding="utf-8")
cle = hashlib.sha1(b"".join((docs / f).read_bytes() for f in ("mecastruct.zip", "app.js", "style.css"))).hexdigest()[:8]
nouveau_sw = re.sub(r'const VERSION = "[^"]*";', f'const VERSION = "mecastruct-{version}-{cle}";', texte_sw)
if nouveau_sw != texte_sw:
    sw.write_text(nouveau_sw, encoding="utf-8", newline="\n")

# numéro de build : change dès qu'un fichier du site change (le site affiche le sien et le compare à celui en ligne)
build = hashlib.sha1(b"".join((docs / f).read_bytes() for f in sorted(
    ["mecastruct.zip", "app.js", "style.css", *[str(p.relative_to(docs)).replace("\\", "/") for p in (docs / "js").glob("*.js")]]))).hexdigest()[:8]

index = docs / "index.html"
page = index.read_text(encoding="utf-8")


def versionner(m: re.Match) -> str:
    return f'{m.group(1)}="{m.group(2)}?v={empreinte(m.group(2))}"'


motif = r'(src|href)="((?:app\.js|style\.css|mecastruct\.zip|js/[a-z0-9_]+\.js))(?:\?v=[0-9a-f]+)?"'
nouvelle = re.sub(motif, versionner, page)
# le zip est lu par app.js : son empreinte est posée dans une balise <meta> que le script relit
nouvelle = re.sub(r'(<meta name="zip" content=")[^"]*(")', rf'\g<1>{empreinte("mecastruct.zip")}\g<2>', nouvelle)
nouvelle = re.sub(r'(<meta name="build" content=")[^"]*(")', rf'\g<1>{build}\g<2>', nouvelle)
# texte de départ du pied de page (app.js le complète avec le build) : pas de « · · » vide si le script ne charge pas
nouvelle = re.sub(r'(<span id="version">)[^<]*(</span>)', rf'\g<1>version {version}\g<2>', nouvelle)
if nouvelle != page:
    index.write_text(nouvelle, encoding="utf-8", newline="\n")
print(f"index.html : {len(re.findall(r'[?]v=[0-9a-f]+', nouvelle))} adresses versionnées")
