"""Parité site / bureau : les 24 calculs, avec leurs valeurs de départ, donnent les mêmes résultats dans le navigateur.

Le site calcule avec les bibliothèques de Pyodide (numpy, pandas, scipy…), le bureau et la CI avec requirements.lock :
ce ne sont pas les mêmes versions. Le script calcule chaque exemple avec le moteur local, puis dans un vrai Chromium qui
charge docs/ (Pyodide compris, Internet nécessaire), et compare statut, tableaux, critères et valeurs clés. Les nombres
sont comparés avec une tolérance (1e-6 relatif, 1e-9 absolu) : seul un vrai écart est signalé.

Usage (depuis application/) : python tools/parite_site.py
Chromium : celui de Playwright (playwright install chromium), ou CHROMIUM_PATH=/chemin/vers/chromium.
Code de sortie : 0 si tout concorde, 1 sinon.
"""

import functools
import http.server
import json
import math
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOCS = RACINE.parent / "docs"
sys.path.insert(0, str(RACINE))

from mecastruct import pont  # noqa: E402

NOMBRE = re.compile(r"[−-]?\d+(?:[.,]\d+)?(?:e[−+-]?\d+)?", re.IGNORECASE)
CLES = ("status", "tables", "criteres", "valeurs", "ok")


def calculs_locaux() -> dict:
    pont.charger("structures")
    formulaires = json.loads(pont.appeler("formulaires", "{}"))["sortie"]
    sortie = {}
    for ident, f in formulaires.items():
        r = json.loads(pont.appeler(ident, json.dumps(f["defaut"])))
        s = r.get("sortie") or {}
        sortie[ident] = {"ok_appel": r.get("ok"), **{k: s.get(k) for k in CLES}} if r.get("ok") else {"ok_appel": False, "erreur": r.get("erreur")}
    return sortie


def nombre(t: str) -> float:
    return float(t.replace("−", "-").replace(",", "."))


def egaux(a, b, chemin: str, ecarts: list) -> None:
    """Comparaison récursive : textes identiques, nombres (y compris ceux écrits dans un texte) égaux à la tolérance."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            ecarts.append(f"{chemin} : clés {sorted(a)} / {sorted(b)}")
            return
        for k in a:
            egaux(a[k], b[k], f"{chemin}.{k}", ecarts)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            ecarts.append(f"{chemin} : {len(a)} éléments / {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            egaux(x, y, f"{chemin}[{i}]", ecarts)
    elif isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        if a != b:
            ecarts.append(f"{chemin} : {a!r} / {b!r}")
    elif isinstance(a, int | float) and isinstance(b, int | float):
        if not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9):
            ecarts.append(f"{chemin} : {a} / {b}")
    elif isinstance(a, str) and isinstance(b, str):
        if NOMBRE.sub("#", a) != NOMBRE.sub("#", b):
            ecarts.append(f"{chemin} : « {a[:80]} » / « {b[:80]} »")
            return
        for x, y in zip(NOMBRE.findall(a), NOMBRE.findall(b), strict=True):
            if not math.isclose(nombre(x), nombre(y), rel_tol=1e-6, abs_tol=1e-9):
                ecarts.append(f"{chemin} : {x} / {y} dans « {a[:60]} »")
    elif a != b:
        ecarts.append(f"{chemin} : {a!r} / {b!r}")


def calculs_navigateur() -> dict:
    from playwright.sync_api import sync_playwright

    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    gestionnaire = functools.partial(Silencieux, directory=str(DOCS))
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), gestionnaire) as serveur:
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{serveur.server_address[1]}/"
        with sync_playwright() as p:
            options = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
            navigateur = p.chromium.launch(args=["--no-sandbox"], **options)
            page = navigateur.new_page()
            erreurs = []
            page.on("pageerror", lambda e: erreurs.append(str(e)))
            page.goto(url + "#/accueil")
            page.wait_for_function("typeof App !== 'undefined' && App.pret", timeout=420_000)
            page.evaluate("async () => { for (const pg of App.PAGES.filter(x => x.pont)) await App.preparer(pg); }")
            res = page.evaluate(
                """() => {
                  const F = App.calculer('formulaires', {}).sortie, out = {};
                  for (const [i, f] of Object.entries(F)) {
                    const r = App.calculer(i, f.defaut), s = r.sortie || {};
                    out[i] = r.ok ? { ok_appel: true, status: s.status ?? null, tables: s.tables ?? null, criteres: s.criteres ?? null,
                                      valeurs: s.valeurs ?? null, ok: s.ok ?? null } : { ok_appel: false, erreur: r.erreur };
                  }
                  return out;
                }"""
            )
            navigateur.close()
    if erreurs:
        print("Erreurs JavaScript :", *erreurs, sep="\n  ")
        sys.exit(1)
    return res


def main() -> int:
    local = calculs_locaux()
    web = calculs_navigateur()
    ecarts: list[str] = []
    if local.keys() != web.keys():
        ecarts.append(f"calculs : {sorted(local)} / {sorted(web)}")
    for ident in sorted(local.keys() & web.keys()):
        avant = len(ecarts)
        egaux(local[ident], web[ident], ident, ecarts)
        print(f"{ident:10s} {'identique' if len(ecarts) == avant else 'DIFFÉRENT'}")
    print(f"\n{len(local)} calculs comparés, {len(ecarts)} écart(s)")
    for e in ecarts[:60]:
        print("  ", e)
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
