"""Parcours et études du bureau, comme « Mes études » du site (docs/js/etudes.js) : pages récentes, favoris, copies
nommées d'une saisie, dernière page visitée de chaque famille, export et import JSON.

Tout reste sur cet ordinateur, dans un fichier JSON du dossier de l'utilisateur (`chemin()`, que MECASTRUCT_ETUDES peut
remplacer). Le fichier a la forme de l'export du site : { format: "mecastruct-etudes", version: 1, favoris, recents,
copies, saisies } ; les pages et les calculs y portent les identifiants du site (`ID_SITE`), pour qu'un export du site
s'importe ici et inversement. Les saisies des onglets de projet (Beam, Tr, Sec…) sont celles des fichiers de projet, donc
lisibles dans les deux versions.
"""

from __future__ import annotations

import copy
import inspect
import json
import math
import os
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QWidget

from mecastruct.bureau import exports, state
from mecastruct.bureau.widgets import differer
from mecastruct.core.errors import MecaStructError
from mecastruct.services import project_io

FORMAT = "mecastruct-etudes"
MAX_RECENTS, MAX_COPIES, MAX_FAVORIS, MAX_SAISIES, MAX_TAILLE = 5, 30, 30, 60, 100_000

# pages du bureau → calculs du site (même identifiant que le pont) ; l'ordre est celui des onglets de la page
CALCULS: dict[str, list[str]] = {
    "poutres": ["beam"], "treillis": ["truss"], "flambage": ["fla"], "sections": ["sec"],
    "sollicitations": ["tra", "cis", "tor", "fle"], "tenseurs": ["ten"], "hooke_jauges": ["hoo", "jau"],
    "ajustements": ["aju"], "frettage": ["fre"], "paliers_lisses": ["pal"], "roulements": ["rlt", "rlt_ens"],
    "engrenages": ["eng", "trn"], "epicycloidaux": ["epi"], "freins_embrayages": ["frn", "emb"],
    "dimensionnement_moteur": ["mot"],
}  # fmt: skip
# identifiants de page qui diffèrent entre le bureau et le site (docs/app.js, PAGES) ; les autres sont communs
ID_SITE = {"sections": "sections-page", "hooke_jauges": "hooke", "paliers_lisses": "paliers", "freins_embrayages": "freins",
           "dimensionnement_moteur": "moteur", "base_de_donnees": "base"}  # fmt: skip
ID_BUREAU = {v: k for k, v in ID_SITE.items()}
_TAB_DE = {calc: tab for tab, calc in exports.TAB_IDENT.items()}  # « beam » → « Beam »

_pages: dict[str, str] = {}  # page du bureau → famille (donné par la fenêtre)
_cache: dict[str, Any] = {"chemin": "?", "donnees": None}
_muet = [False]


def vers_site(ident: str) -> str:
    return ID_SITE.get(ident, ident)


def vers_bureau(ident: str) -> str:
    return ID_BUREAU.get(ident, ident)


def definir_pages(famille_de: dict[str, str]) -> None:
    """Pages que la fenêtre propose, avec leur famille (celles d'un favori ou d'une dernière page possibles)."""
    _pages.clear()
    _pages.update({p: f for p, f in famille_de.items() if p != "apropos"})


# ------------------------------------------------------------------------------------------------------ stockage


def chemin() -> Path:
    """Fichier des études : MECASTRUCT_ETUDES s'il est défini, sinon %APPDATA%/MecaStruct/etudes.json."""
    env = os.environ.get("MECASTRUCT_ETUDES")
    if env:
        return Path(env)
    return Path(os.environ.get("APPDATA") or Path.home() / ".config") / "MecaStruct" / "etudes.json"


def suspendre(oui: bool = True) -> None:
    """Sans fichier : les études ne sont ni lues ni écrites (vérification et captures automatiques)."""
    _muet[0] = oui
    _cache.update(chemin="?", donnees=None)


def _donnees() -> dict:
    cible = None if _muet[0] else str(chemin())
    if _cache["donnees"] is None or _cache["chemin"] != cible:
        d: Any = {}
        if cible is not None:
            try:
                d = json.loads(Path(cible).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
        _cache.update(chemin=cible, donnees=d if isinstance(d, dict) else {})
    return _cache["donnees"]


def _sauver() -> None:
    if _muet[0]:
        return
    fichier = chemin()
    d = _donnees()
    contenu = {
        "format": FORMAT,
        "version": 1,
        **{k: d[k] for k in ("favoris", "recents", "copies", "derniere") if k in d},
    }
    try:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        tmp = fichier.with_suffix(".tmp")
        tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(fichier)
    except OSError:  # dossier en lecture seule : les études restent valables jusqu'à la fermeture
        pass


# ------------------------------------------------------------------------------------------------ listes


def _objet(x: Any) -> bool:
    return isinstance(x, dict)


def _liste(cle: str) -> list:
    v = _donnees().get(cle)
    return v if isinstance(v, list) else []


def _datee(r: Any) -> bool:
    return _objet(r) and isinstance(r.get("t"), (int, float)) and math.isfinite(r["t"]) and isinstance(r.get("id"), str)


def _page_favorite(ident_site: Any) -> str | None:
    ident = vers_bureau(ident_site) if isinstance(ident_site, str) else None
    return ident if ident in _pages else None


def _page_calcul(ident_site: Any) -> str | None:
    ident = vers_bureau(ident_site) if isinstance(ident_site, str) else None
    return ident if ident in CALCULS else None


def _copie_valide(c: Any) -> bool:
    if not (_objet(c) and isinstance(c.get("id"), str) and isinstance(c.get("nom"), str) and _objet(c.get("saisie"))):
        return False
    page = _page_calcul(c.get("page"))
    return bool(page) and c.get("calcul") in CALCULS[page]


def recents() -> list[dict]:
    """Cinq dernières pages de calcul visitées, la plus récente d'abord : [{id (page du bureau), t (ms)}]."""
    return [
        {"id": _page_calcul(r["id"]), "t": r["t"]} for r in _liste("recents") if _datee(r) and _page_calcul(r["id"])
    ][:MAX_RECENTS]


def favoris() -> list[dict]:
    """Pages marquées d'une étoile : [{id (page du bureau), t (ms)}]."""
    return [
        {"id": _page_favorite(r["id"]), "t": r["t"]} for r in _liste("favoris") if _datee(r) and _page_favorite(r["id"])
    ]


def copies() -> list[dict]:
    """Copies nommées : [{id, nom, page (page du bureau), calcul, cree (ISO), saisie}], la plus récente d'abord."""
    return [{**c, "page": _page_calcul(c["page"])} for c in _liste("copies") if _copie_valide(c)]


def est_favori(ident: str) -> bool:
    return any(f["id"] == ident for f in favoris())


def peut_etre_favori(ident: str) -> bool:
    return ident in _pages


def basculer_favori(ident: str) -> bool:
    """Ajoute ou retire la page des favoris ; renvoie vrai si elle en est maintenant."""
    sans = [{"id": vers_site(f["id"]), "t": f["t"]} for f in favoris() if f["id"] != ident]
    oui = len(sans) == len(favoris())  # elle n'y était pas
    if oui:
        sans = [{"id": vers_site(ident), "t": _maintenant()}, *sans][:MAX_FAVORIS]
    _donnees()["favoris"] = sans
    _sauver()
    return oui


def _maintenant() -> int:
    return int(time.time() * 1000)


def noter_visite(ident: str) -> None:
    """Appelée à chaque ouverture de page : récents (pages de calcul) et dernière page de la famille."""
    if ident in CALCULS:
        autres = [{"id": vers_site(r["id"]), "t": r["t"]} for r in recents() if r["id"] != ident]
        _donnees()["recents"] = [{"id": vers_site(ident), "t": _maintenant()}, *autres][:MAX_RECENTS]
    famille = _pages.get(ident)
    if famille:
        derniere = _donnees().setdefault("derniere", {})
        if not isinstance(derniere, dict):
            derniere = _donnees()["derniere"] = {}
        derniere[famille] = ident
    _sauver()


def derniere_page(famille: str, defaut: str) -> str:
    """Dernière page ouverte dans la famille, sinon `defaut` (sa première page)."""
    d = _donnees().get("derniere")
    ident = d.get(famille) if isinstance(d, dict) else None
    return ident if isinstance(ident, str) and _pages.get(ident) == famille else defaut


def vider_historique() -> None:
    _donnees()["recents"] = []
    _sauver()


def supprimer_copie(identifiant: str) -> None:
    _donnees()["copies"] = [c for c in _liste("copies") if not (_objet(c) and c.get("id") == identifiant)]
    _sauver()


# ------------------------------------------------------------------------------------------------ saisies


def _defaut_machine(calcul: str) -> dict:
    """Valeurs de départ d'un calcul « éléments de machines » (la page qui le porte)."""
    import importlib

    for module in ("ajustements", "frettage", "paliers_lisses", "roulements", "engrenages", "epicycloidaux",
                   "freins_embrayages", "dimensionnement_moteur"):  # fmt: skip
        mod = importlib.import_module(f"mecastruct.bureau.pages.{module}")
        for _, classe in inspect.getmembers(mod, inspect.isclass):
            if getattr(classe, "P", None) == calcul and getattr(classe, "DEFAUT", None):
                return classe.DEFAUT
    raise KeyError(calcul)


def _meme_genre(v: Any, defaut: Any) -> bool:
    if isinstance(defaut, bool) or isinstance(v, bool):
        return isinstance(defaut, bool) and isinstance(v, bool)
    if isinstance(defaut, (int, float)):
        return isinstance(v, (int, float)) and math.isfinite(v)
    return type(v) is type(defaut)


def lire_saisie(calcul: str) -> dict:
    """Saisie courante du calcul (copie)."""
    tab = _TAB_DE.get(calcul)
    if tab:
        return copy.deepcopy(state.saisie(tab))
    return {k: copy.deepcopy(state.v.get(f"{calcul}.{k}", v)) for k, v in _defaut_machine(calcul).items()}


def controler_saisie(calcul: str, saisie: dict) -> None:
    """Refuse (MecaStructError) une saisie que le calcul ne comprend pas ; sans effet sur la saisie courante."""
    tab = _TAB_DE.get(calcul)
    if tab:
        project_io.problemFromJson(project_io.problemToJson(tab, saisie), tab)
        return
    defaut = _defaut_machine(calcul)
    for k, v in saisie.items():
        if k in defaut and not _meme_genre(v, defaut[k]):
            raise MecaStructError("MecaStruct:App:badProblemFile", f"Le champ « {k} » n'a pas la forme attendue.")


def ecrire_saisie(calcul: str, saisie: dict) -> None:
    """Remplace la saisie du calcul (champs absents : valeurs de départ). L'appelant a contrôlé la saisie."""
    tab = _TAB_DE.get(calcul)
    if tab:
        from mecastruct.bureau import dossier

        dossier._applique(tab, copy.deepcopy(saisie))
        return
    for k, v in _defaut_machine(calcul).items():
        state.v[f"{calcul}.{k}"] = copy.deepcopy(saisie.get(k, v))
        state.v.pop(f"{calcul}.res", None)  # un résultat d'une autre saisie ne vaut plus


def calcul_actif(fenetre: Any, ident: str) -> str | None:
    """Calcul affiché par la page : son onglet courant si elle en a plusieurs."""
    calculs = CALCULS.get(ident)
    if not calculs:
        return None
    page = fenetre.page(ident)
    if getattr(page, "bati", False) and hasattr(page, "onglets"):
        i = page.onglets.currentIndex()
    else:
        i = state.v.get(f"onglet.{type(page).__name__}", 0)
    return calculs[i] if isinstance(i, int) and 0 <= i < len(calculs) else calculs[0]


def ajouter_copie(ident: str, calcul: str, nom: str) -> dict | None:
    """Garde la saisie courante du calcul sous `nom` ; None s'il y a déjà 30 copies."""
    if len(copies()) >= MAX_COPIES:
        return None
    c = {"id": "c" + uuid.uuid4().hex[:10], "nom": " ".join(nom.split())[:60] or "Copie", "page": vers_site(ident),
         "calcul": calcul, "cree": datetime.now().astimezone().isoformat(timespec="seconds"), "saisie": lire_saisie(calcul)}  # fmt: skip
    _donnees()["copies"] = [c, *[x for x in _liste("copies") if _copie_valide(x)]]
    _sauver()
    return c


def ouvrir_copie(c: dict) -> str:
    """Remplace la saisie du calcul de la copie par celle de la copie ; renvoie la page du bureau à ouvrir."""
    controler_saisie(c["calcul"], c["saisie"])
    ecrire_saisie(c["calcul"], c["saisie"])
    return c["page"]


# ---------------------------------------------------------------------------------------- export et import


def exporter() -> dict:
    """Toutes les études : favoris, récents, copies et saisies courantes de chaque calcul (fichier de la forme du site)."""
    from mecastruct import __version__

    saisies = {}
    for calculs in CALCULS.values():
        for calcul in calculs:
            try:
                s = json.loads(project_io._json(lire_saisie(calcul)))
            except (TypeError, ValueError, KeyError):
                continue
            if len(json.dumps(s)) <= MAX_TAILLE:
                saisies[calcul] = s
    return {"format": FORMAT, "version": 1, "outil": f"MecaStruct RdM {__version__}",
            "exporte": datetime.now().astimezone().isoformat(timespec="seconds"),
            "favoris": [{"id": vers_site(f["id"]), "t": f["t"]} for f in favoris()],
            "recents": [{"id": vers_site(r["id"]), "t": r["t"]} for r in recents()],
            "copies": [{**c, "page": vers_site(c["page"])} for c in copies()], "saisies": saisies}  # fmt: skip


def lire_import(texte: str) -> dict:
    """Contrôle d'un fichier d'export : {ok: True, donnees} ou {ok: False, erreur}. Les entrées inconnues sont écartées."""
    try:
        d = json.loads(texte)
    except ValueError:
        return {"ok": False, "erreur": "Ce fichier n'est pas du JSON valide."}
    if not _objet(d) or d.get("format") != FORMAT:
        return {"ok": False, "erreur": "Ce fichier n'est pas un export d'études MecaStruct."}
    if d.get("version") != 1:
        return {
            "ok": False,
            "erreur": f"Ce fichier vient d'une autre version du format ({str(d.get('version'))[:10]}).",
        }

    def liste(x: Any) -> list:
        return x if isinstance(x, list) else []

    fav = [{"id": r["id"], "t": r["t"]} for r in liste(d.get("favoris")) if _datee(r) and _page_favorite(r["id"])]
    rec = [{"id": r["id"], "t": r["t"]} for r in liste(d.get("recents")) if _datee(r) and _page_calcul(r["id"])]
    cop = []
    for c in liste(d.get("copies")):
        if _copie_valide(c) and len(str(c["id"])) <= 40 and len(json.dumps(c["saisie"])) <= MAX_TAILLE:
            cop.append({"id": c["id"], "nom": " ".join(c["nom"].split())[:60] or "Copie", "page": c["page"],
                        "calcul": c["calcul"], "cree": c["cree"][:40] if isinstance(c.get("cree"), str) else "", "saisie": c["saisie"]})  # fmt: skip
    brut = d.get("saisies")
    sai = [(k, v) for k, v in (brut.items() if _objet(brut) else []) if _objet(v) and len(json.dumps(v)) <= MAX_TAILLE]
    if len(sai) > MAX_SAISIES:
        return {"ok": False, "erreur": f"Trop de saisies dans ce fichier ({len(sai)})."}
    connus = {c for cs in CALCULS.values() for c in cs}
    sai = [(k, v) for k, v in sai if k in connus]  # « ossature » et les calculs que le bureau n'a pas sont écartés
    if not (fav or rec or cop or sai):
        return {"ok": False, "erreur": "Ce fichier ne contient aucune étude."}
    return {"ok": True, "donnees": {"favoris": fav, "recents": rec, "copies": cop, "saisies": sai}}


def appliquer_import(d: dict) -> int:
    """Fusionne un import contrôlé : favoris et copies s'ajoutent, les saisies du fichier remplacent celles de la fenêtre.

    Renvoie le nombre de saisies refusées par leur calcul (forme inattendue) : elles sont laissées de côté."""

    def par_id(a: list, b: list) -> list:
        m: dict[str, dict] = {}
        for x in [*a, *b]:
            if x["id"] not in m or m[x["id"]]["t"] < x["t"]:
                m[x["id"]] = x
        return sorted(m.values(), key=lambda x: -x["t"])

    site = lambda lst: [{"id": vers_site(x["id"]), "t": x["t"]} for x in lst]  # noqa: E731
    _donnees()["favoris"] = par_id(site(favoris()), d["favoris"])[:MAX_FAVORIS]
    _donnees()["recents"] = par_id(site(recents()), d["recents"])[:MAX_RECENTS]
    deja = {c["id"] for c in copies()}
    anciennes = [{**c, "page": vers_site(c["page"])} for c in copies()]
    _donnees()["copies"] = [*anciennes, *[c for c in d["copies"] if c["id"] not in deja]][:MAX_COPIES]
    _sauver()
    refusees = 0
    for calcul, saisie in d["saisies"]:
        try:
            controler_saisie(calcul, saisie)
            ecrire_saisie(calcul, saisie)
        except MecaStructError:
            refusees += 1
    return refusees


# -------------------------------------------------------------------------------------------------- interface


def relatif(t_ms: float) -> str:
    s = max(0.0, time.time() - t_ms / 1000)
    if s < 60:
        return "à l'instant"
    if s < 3600:
        return f"il y a {int(s // 60)} min"
    if s < 86400:
        return f"il y a {int(s // 3600)} h"
    j = int(s // 86400)
    if j == 1:
        return "hier"
    if j < 30:
        return f"il y a {j} jours"
    return datetime.fromtimestamp(t_ms / 1000).strftime("%d/%m/%Y")


def confirmer(parent: Any, texte: str) -> bool:
    """Question oui / non (remplaçable dans les tests)."""
    return QMessageBox.question(parent, "Mes études", texte) == QMessageBox.StandardButton.Yes


def demander_nom(parent: Any, defaut: str) -> str | None:
    """Nom d'une copie, ou None si l'utilisateur annule (remplaçable dans les tests)."""
    nom, ok = QInputDialog.getText(parent, "Dupliquer l'étude", "Nom de la copie :", text=defaut)
    return nom if ok else None


def section(z: Any, fenetre: Any) -> None:
    """Bloc « Mes études » de l'accueil : favoris, récents, copies, puis sauvegarde et import."""
    libelles = {i: lib for _, pages in fenetre.familles.items() for i, lib in pages}
    message: list[tuple[str, str]] = []

    def ligne(
        c: Any, ident: str, quand: str, actions: list[tuple[str, str, Callable[[], None]]], titre: str | None = None
    ) -> None:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        lien = QPushButton(titre or libelles.get(ident, ident))
        lien.setObjectName("lien")
        lien.setCursor(Qt.CursorShape.PointingHandCursor)
        lien.clicked.connect(lambda: differer(lambda: fenetre.aller(ident)))
        legende = QLabel(quand)
        legende.setObjectName("legende")
        h.addWidget(lien)
        h.addWidget(legende)
        h.addStretch(1)
        for libelle, nom_objet, action in actions:
            b = QPushButton(libelle)
            b.setObjectName(nom_objet)
            b.setToolTip(libelle)
            b.clicked.connect(lambda _=False, a=action: differer(a))
            h.addWidget(b)
        c._ajouter(w)

    def dupliquer(ident: str, rafraichir: Callable[[], None]) -> None:
        calcul = calcul_actif(fenetre, ident)
        nom = demander_nom(fenetre, f"{libelles.get(ident, ident)} (copie)")
        if nom is None:
            return
        if not nom.strip():
            message[:] = [("avertissement", "Donnez un nom à la copie.")]
        elif ajouter_copie(ident, calcul, nom) is None:
            message[:] = [("avertissement", f"Au plus {MAX_COPIES} copies : supprimez-en une d'abord.")]
        else:
            message[:] = [("succes", f"Copie enregistrée : {' '.join(nom.split())[:60]}")]
        rafraichir()

    def ouvrir(c: dict, rafraichir: Callable[[], None]) -> None:
        if not confirmer(
            fenetre,
            f"Remplacer la saisie actuelle de « {libelles.get(c['page'], c['page'])} » par la copie "
            f"« {c['nom']} » ? La saisie actuelle sera perdue ; dupliquez-la d'abord pour la garder.",
        ):
            return
        try:
            ident = ouvrir_copie(c)
        except MecaStructError as err:
            message[:] = [("erreur", getattr(err, "message", str(err)))]
            rafraichir()
            return
        page = fenetre.page(ident)
        i = CALCULS[ident].index(c["calcul"])
        if len(CALCULS[ident]) > 1:
            state.v[f"onglet.{type(page).__name__}"] = i
            if getattr(page, "bati", False) and hasattr(page, "onglets"):
                page.onglets.setCurrentIndex(i)
        fenetre.aller(ident)

    def importer(fichiers: list[tuple[str, bytes]], rafraichir: Callable[[], None]) -> None:
        nom, octets = fichiers[0]
        if len(octets) > 3_000_000:
            message[:] = [("erreur", "Fichier trop gros pour un export d'études MecaStruct. Rien n'a été importé.")]
        else:
            v = lire_import(octets.decode("utf-8-sig", errors="replace"))
            if not v["ok"]:
                message[:] = [("erreur", v["erreur"] + " Rien n'a été importé.")]
            else:
                d = v["donnees"]
                if confirmer(
                    fenetre,
                    f"Importer « {nom} » : {len(d['favoris'])} favori(s), {len(d['copies'])} copie(s) et "
                    f"{len(d['saisies'])} saisie(s) de calcul ? Les favoris et les copies s'ajoutent aux vôtres ; "
                    "les saisies du fichier remplacent celles de la fenêtre pour les mêmes calculs.",
                ):
                    refusees = appliquer_import(d)
                    reste = (
                        f" {refusees} saisie(s) n'ont pas la forme attendue et ont été laissées de côté."
                        if refusees
                        else ""
                    )
                    message[:] = [
                        ("succes" if not refusees else "avertissement", f"Études importées depuis « {nom} ».{reste}")
                    ]
        rafraichir()

    def corps(c: Any) -> None:
        def rafraichir() -> None:
            s.rafraichir()

        fav, rec, cop = favoris(), recents(), copies()
        c.legende("Conservé uniquement sur cet ordinateur (rien n'est envoyé sur Internet). Ouvrir une page d'ici ne modifie "
                  "aucune donnée et ne lance aucun calcul.")  # fmt: skip
        if message:
            c.message(*message[0])
        if not (fav or rec or cop):
            c.texte("Vos cinq dernières pages de calcul et vos favoris apparaîtront ici. Pour ajouter un favori, utilisez "
                    "le bouton « Favori » de la barre du haut.")  # fmt: skip
        if fav:
            c.texte("**Favoris**")
            for f in fav:
                acts = (
                    [("Dupliquer", "bouton", lambda i=f["id"]: dupliquer(i, rafraichir))] if f["id"] in CALCULS else []
                )
                acts.append(("Retirer", "bouton", lambda i=f["id"]: (basculer_favori(i), rafraichir())))
                ligne(c, f["id"], "ajouté " + relatif(f["t"]), acts)
        if rec:
            c.texte("**Récemment utilisés**")
            for r in rec:
                ligne(
                    c, r["id"], relatif(r["t"]), [("Dupliquer", "bouton", lambda i=r["id"]: dupliquer(i, rafraichir))]
                )
            c.bouton("Vider l'historique", lambda: (vider_historique(), rafraichir()))
        if cop:
            c.texte("**Copies enregistrées**")
            for k in cop:
                try:
                    quand = "enregistrée " + relatif(datetime.fromisoformat(k["cree"]).timestamp() * 1000)
                except ValueError:
                    quand = "enregistrée"
                ligne(c, k["page"], f"{libelles.get(k['page'], k['page'])} · {quand}",
                      [("Ouvrir", "bouton", lambda k=k: ouvrir(k, rafraichir)),
                       ("Supprimer", "bouton", lambda k=k: (supprimer_copie(k["id"]), rafraichir()))],
                      titre=k["nom"])  # fmt: skip
        c.texte("**Sauvegarder ou changer d'appareil**")
        c.legende("Le fichier JSON exporté garde vos études ailleurs ; il s'ouvre aussi dans la version en ligne.")
        c.telecharger(
            "Exporter mes études (JSON)",
            lambda: json.dumps(exporter(), ensure_ascii=False, indent=2),
            "mecastruct-etudes.json",
        )
        c.ouvrirFichier(
            "Importer un fichier d'études", "Études (*.json)", lambda fichiers: importer(fichiers, rafraichir)
        )

    def rendu(z2: Any) -> None:
        nonlocal s
        s = z2.section(corps)

    s: Any = None
    z.repliable("Mes études", ouvert=True, rendu=rendu, cle="mes_etudes")
