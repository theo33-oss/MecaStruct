"""Fichiers, exemples, dossier de validation et explications du calcul des pages de calcul."""

import copy
import re
from datetime import datetime

from mecastruct.bureau import exports, state, tache
from mecastruct.bureau.widgets import Zone
from mecastruct.core.errors import MecaStructError
from mecastruct.services import dossier_export, project_io, validation_report
from mecastruct.services.examples import exampleNames, loadExample


def _charge_exemple(tab: str) -> None:
    """Remplace la saisie de l'onglet par l'exemple choisi."""
    state.remplacer_saisie(tab, loadExample(tab, state.v.get(f"{tab}.exemple")))
    if tab == "Beam":
        state.push_beam_history()


def example_picker(z: Zone, tab: str) -> None:
    """Choix d'un exemple d'école (si l'onglet en a plusieurs) et bouton « Charger l'exemple »."""
    noms = exampleNames(tab)
    if noms:
        z.liste("Exemple", noms, f"{tab}.exemple")
    z.bouton("Charger l'exemple", lambda: _charge_exemple(tab))


def _applique(tab: str, saisie: dict) -> None:
    """Remplace la saisie de l'onglet par celle d'un fichier (champs absents : exemple)."""
    state.remplacer_saisie(tab, {**loadExample(tab), **saisie})
    if tab == "Beam":  # resetBeamHistory : l'historique repart du problème ouvert
        state.v.pop("beam_history", None)
        state.push_beam_history()


def _alerte_materiaux(saisies: dict[str, dict]) -> str:
    """Message pour les matériaux des saisies ouvertes absents de la base (matériaux utilisateur non importés)."""
    manquants = project_io.missingMaterials(saisies, state.dm().listMaterials())
    if not manquants:
        return ""
    liste = " ; ".join(f"« {nom} » (onglets {', '.join(tabs)})" for nom, tabs in manquants.items())
    return (
        f"Matériau introuvable dans la base : {liste}. Le fichier ne contient que son nom : importez d'abord vos "
        "données utilisateur (page « Matériaux et profilés », onglet « Mes données », « Recharger mes ajouts »), "
        "puis rouvrez ce fichier."
    )


def _ouvre(cle: str, fichiers: list[tuple[str, bytes]], lecture) -> None:
    """Lit le fichier choisi ; `lecture(texte)` applique la saisie et renvoie le message de succès (ou d'alerte)."""
    try:
        msg = lecture(fichiers[0][1].decode("utf-8-sig"))
    except (MecaStructError, UnicodeDecodeError) as err:
        state.v[f"fichier.{cle}.msg"] = ("error", getattr(err, "message", "Ce fichier n'est pas un fichier texte JSON."))
        return
    state.v[f"fichier.{cle}.msg"] = ("info" if msg in ("Problème ouvert.", "Projet ouvert.") else "avertissement", msg)


def file_bar(z: Zone, tab: str) -> None:
    """Bloc « Fichiers » (fermé) de l'onglet `tab` : enregistrer, ouvrir, exporter en tableau."""

    def corps(c: Zone) -> None:
        c.telecharger(
            "Enregistrer mon problème (.json)",
            lambda: project_io.problemToJson(tab, state.saisie(tab)),
            f"Probleme_{tab}.json",
        )

        def lecture(texte: str) -> str:
            saisie = project_io.problemFromJson(texte, tab)[1]
            _applique(tab, saisie)
            return _alerte_materiaux({tab: saisie}) or "Problème ouvert."

        def ouvrir(fichiers: list[tuple[str, bytes]]) -> None:
            _ouvre(f"{tab}.problème", fichiers, lecture)
            z.page.rafraichirTout()

        c.ouvrirFichier("Ouvrir un problème (.json)", "Problème (*.json)", ouvrir)
        res = state.result(tab)
        feuilles = project_io.resultSheets(tab, res) if res else {}
        fmt = c.radio("Format d'export", ["xlsx", "csv"], f"fichier.{tab}.format", apres=z.page.rafraichirSaisie)
        c.telecharger(
            "Exporter en tableau",
            (lambda: project_io.toXlsx(feuilles)) if fmt == "xlsx" else (lambda: project_io.toCsvZip(feuilles)),
            f"MecaStruct_{tab}.{'xlsx' if fmt == 'xlsx' else 'zip'}",
            actif=bool(feuilles),
            aide=None if feuilles else "Aucun résultat à exporter : cliquez d'abord sur « Calculer ».",
        )

    z.repliable("Fichiers", rendu=corps, cle=f"fichiers.{tab}")
    z.messageGarde(f"fichier.{tab}.problème.msg")


def project_bar(z: Zone) -> None:
    """Accueil : « Enregistrer tout le projet » et « Ouvrir un projet » (les onglets non relus sont signalés)."""
    z.telecharger(
        "Enregistrer tout le projet (.json)",
        lambda: project_io.projectToJson(state.v["saisie"]),
        "Projet_MecaStruct.json",
    )

    def lecture(texte: str) -> str:
        saisies, echecs = project_io.projectFromJson(texte)
        for tab, saisie in saisies.items():
            _applique(tab, saisie)
        non_lus = ", ".join(echecs)
        alertes = [
            non_lus and f"Onglets non restaurés (absents, version différente ou contenu invalide) : {non_lus}",
            _alerte_materiaux(saisies),
        ]
        return "\n\n".join(a for a in alertes if a) or "Projet ouvert."

    def ouvrir(fichiers: list[tuple[str, bytes]]) -> None:
        _ouvre("projet", fichiers, lecture)
        z.page.rafraichirTout()

    z.ouvrirFichier("Ouvrir un projet (.json)", "Projet (*.json)", ouvrir)
    z.messageGarde("fichier.projet.msg")


def _extras_precedents(tab: str) -> dict | None:
    """Résultats facultatifs déjà calculés (Poutres : combinaisons, Eurocode 3, fatigue, profilé)."""
    if tab != "Beam":
        return None
    cles = {"combos": "BeamCombo", "ec3": "BeamEC3", "fatigue": "BeamFat", "profiles": "BeamProf"}
    return {nom: state.result(cle) for nom, cle in cles.items()}


def _genere_validation(z: Zone, tab: str) -> None:
    """Recalcule la page `tab` avec la saisie actuelle et garde le dossier de validation HTML."""
    saisie = copy.deepcopy(state.saisie(tab))
    dm, extras = state.dm(), _extras_precedents(tab)

    def travail() -> tuple:
        res = validation_report.recompute(tab, saisie, dm, extras)
        html = validation_report.generate(tab, saisie, res, dm)
        return validation_report.fileName(tab), html, datetime.now().strftime("%H:%M:%S")

    def fin(dossier: tuple) -> None:
        state.v.pop(f"validation.{tab}.erreur", None)
        state.v[f"validation.{tab}"] = dossier
        z.page.surSaisie()

    def echec(err: Exception) -> None:
        state.v[f"validation.{tab}.erreur"] = err
        state.v.pop(f"validation.{tab}", None)
        z.page.surSaisie()

    tache.lancer(travail, fin, echec)


def validation_button(z: Zone, tab: str) -> None:
    """« Dossier de validation de ce problème » : recalcule la page, puis propose le dossier en HTML, PDF ou Word.

    Actif seulement s'il y a un résultat à jour pour l'onglet `tab`. Suivent le bloc-notes (.txt) et l'Excel de validation.
    """
    if tab in exports.TAB_IDENT:
        exports.boutons(z, exports.TAB_IDENT[tab], state.saisie(tab), validation_report.meta(tab)["title"])
    res = state.result(tab)
    if res is not None and not state.is_current(tab):  # signal commun à toutes les pages de calcul
        z.avertissement(
            "Saisie modifiée depuis le dernier calcul : les résultats affichés datent de l'ancienne saisie. "
            "Cliquez sur « Calculer » pour les actualiser."
        )
    z.bouton(
        "Dossier de validation de ce problème",
        lambda: _genere_validation(z, tab),
        actif=res is not None and state.is_current(tab),
        aide=(
            "Cliquez d'abord sur « Calculer »."
            if res is None
            else None
            if state.is_current(tab)
            else "Saisie modifiée depuis le dernier calcul : cliquez sur « Calculer » pour que le dossier la reprenne."
        ),
    )
    err = state.v.get(f"validation.{tab}.erreur")
    if err is not None:
        z.erreurCalcul(err)
    dossier_download(z, f"validation.{tab}", state.v.get(f"validation.{tab}"))


def dossier_download(z: Zone, cle: str, dossier: tuple | None) -> None:
    """Choix du format (HTML, PDF, Word) et enregistrement d'un dossier de validation déjà généré.

    Entrées : `cle` (préfixe des clés de champs) ; `dossier` = (nom du fichier .html, HTML, heure de génération, …),
    ou None s'il n'y a rien à enregistrer.
    """
    if dossier is None:
        return
    fichier, html, heure = dossier[:3]
    fmt = z.radio("Format du dossier", list(dossier_export.FORMATS), f"{cle}.format")
    ext, _mime = dossier_export.FORMATS[fmt]
    nom = fichier.removesuffix(".html") + ext
    z.telecharger(f"Enregistrer le dossier ({nom})", lambda: dossier_export.export(html, fmt), nom)
    legende = (
        "Formules affichées par MathJax (connexion Internet requise) ; pour un PDF avec les diagrammes : ouvrir le "
        "fichier, Imprimer → Enregistrer en PDF."
        if fmt == "HTML"
        else "Formules en images, lisibles hors connexion ; les diagrammes interactifs ne sont que dans le HTML."
    )
    z.legende(f"Dossier généré à {heure} avec la saisie de ce moment. {legende}")


def explanation_panel(z: Zone, tab: str) -> None:
    """Panneau « Explications du calcul » : équations appliquées aux données de l'utilisateur, avec les valeurs."""
    if not z.case("Explications du calcul", f"explication.{tab}.visible", defaut=True):
        return
    res = state.result(tab)
    if res is None:
        z.info("Cliquez sur « Calculer » pour voir les équations appliquées à vos données.")
        return
    if not state.is_current(tab):  # le recalcul partirait de la saisie modifiée, pas de celle du résultat
        z.info("Saisie modifiée depuis le dernier calcul : cliquez sur « Calculer » pour mettre à jour les équations.")
        return
    try:
        cache = state.v.get(f"explication.{tab}.cache")
        if cache is None or cache[0] is not res:  # l'objet lui-même : un id() peut être réutilisé par Python
            # copie : le panneau ne modifie pas la saisie de la page ; la section de Cis et Fle est celle du calcul
            saisie = copy.deepcopy(state.saisie(tab))
            # calcul principal seul : refaire combinaisons, Eurocode 3, profilés… coûte 5 s et plus ; leurs contrôles
            # restent dans le dossier de validation
            calc = validation_report.recompute(tab, saisie, state.dm(), None)
            rows = validation_report.explanationRows(tab, saisie, calc, state.dm())
            cache = (res, rows, validation_report.solverEquations(tab, calc))
            state.v[f"explication.{tab}.cache"] = cache
        _, rows, blocks = cache
        cadre = z.cadre()
        cadre.texte("**Équations appliquées à vos données**")
        for row in rows:
            if row["hand"] is None:  # titre de groupe
                cadre.texte(f"**{row['label']}**")
                continue
            cadre.texte(re.sub(r"([<>*_`])", r"\\\1", row["label"]))
            cadre.formule(row["latex"])
            ecart, ok = validation_report.explanationVerdict(row)
            if ok:
                legende = f"Concorde avec le solveur : {row['solver']:.6g} {row['unit']}"
            else:
                legende = f"Écart avec le solveur : {ecart:.3g} {row['unit']} (solveur : {row['solver']:.6g})"
            cadre.legende(legende)

        def solveur(c: Zone) -> None:
            for nom, formules in blocks:
                c.texte(f"**{nom}**")
                c.formules(formules)

        z.repliable("Équations écrites par le solveur", rendu=solveur, cle=f"solveur.{tab}")
    except Exception as err:  # noqa: BLE001 : l'explication ne doit jamais bloquer la page
        z.avertissement(f"Explications indisponibles pour ce calcul : {err}")
