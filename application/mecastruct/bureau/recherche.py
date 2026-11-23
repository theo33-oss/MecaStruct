# ruff: noqa: E501
"""Recherche globale (Ctrl+K ou « / »), comme celle du site (docs/js/recherche.js) : par page, grandeur, norme ou mot usuel.

La table ci-dessous est celle du site, écrite à la main : une ligne = une page (et un onglet éventuel), une raison courte
affichée sous le résultat, puis les mots qui y mènent (séparés par « | »). Les mots sont comparés sans accents ni
majuscules ; un début de mot, un pluriel ou un morceau de mot suffit. Ajouter un synonyme = ajouter un mot à la bonne ligne.
Les pages portent ici l'identifiant du site ; `CIBLES` les traduit en page et onglet du bureau.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from mecastruct.bureau import state, theme
from mecastruct.bureau.etudes import vers_bureau

# [page, onglet (identifiant du calcul, "" si la page n'en a qu'un), étiquette, raison, mots]
TABLE = [
    # ---- Structures
    ("poutres", "beam", "Poutre 2D", "Flèche, réactions d'appui et efforts d'une poutre",
     "poutre|flèche|flèche maximale|déformée|réaction|réactions d'appui|appui|appuis|charge répartie|charge ponctuelle|console|encastrement|hyperstatique|isostatique|moment fléchissant|effort tranchant|effort normal|diagramme des efforts|contrainte de flexion|contrainte|coefficient de sécurité|limite élastique|rdm|résistance des matériaux"),
    ("poutres", "beam", "Eurocode 3", "Vérification d'une poutre acier selon l'Eurocode 3 (EN 1993-1-1)",
     "eurocode 3|eurocode|ec3|en 1993|en 1993-1-1|nf en 1993|acier de construction|classe de section|profilé|profilé IPE|profilé HEA|ipe|hea|heb|upn"),
    ("poutres", "beam", "Fatigue", "Vérification en fatigue d'une poutre (Kf, catégories de détail)",
     "fatigue|goodman|diagramme de goodman|haigh|endurance|limite d'endurance|contrainte alternée|contrainte moyenne|wöhler|courbe de wöhler|kf|concentration de contrainte|kt|entaille|catégorie de détail|en 1993-1-9"),
    ("poutres", "beam", "Tige filetée", "Vis ou tige filetée : section résistante d'un filetage ISO (ISO 898-1, ISO 68-1)",
     "vis|tige filetée|boulon|filetage|filetage métrique|iso 898-1|iso 898|iso 68-1|iso 68|iso 724|section résistante|pas gros|pas fin|m8|m10|m12|m16"),
    ("poutres", "beam", "Combinaisons", "Combinaisons de charges, enveloppe et charge mobile",
     "combinaison|combinaisons|enveloppe|charge mobile|pont roulant|poids propre"),
    ("poutres", "ossature", "Ossature 3D", "Ossature 3D : barres, nœuds, appuis et efforts internes",
     "ossature|portique|structure 3d|cadre|barres|noeud|nœud|vue 3d|3d"),
    ("treillis", "", "", "Efforts dans les barres et déplacements des nœuds d'un treillis",
     "treillis|barre|barres|noeud|nœud|articulation|ferme|poutre en treillis|effort dans les barres"),
    ("flambage", "", "", "Charge critique d'Euler, courbes de flambement de l'Eurocode 3, élancement et conditions aux limites",
     "flambage|flambement|euler|charge critique|élancement|longueur de flambement|colonne|poteau|buckling|condition aux limites|stabilité|eurocode 3 flambement|flambement eurocode 3|ec3 flambement|courbe de flambement|courbes de flambement|courbe a0|coefficient de réduction|nb,rd|en 1993-1-1 6.3.1|6.3.1"),
    # ---- Sections et contraintes
    ("sections-page", "", "", "Aire, centre de gravité, inerties et modules d'une section",
     "section|sections|aire|centre de gravité|barycentre|inertie|moment quadratique|module de flexion|module de résistance|rayon de giration|section composée|huygens|steiner|profilé|profilé IPE|profilé HEA|ipe|hea|heb|upn|tube|rectangle|cercle"),
    ("sollicitations", "tra", "Traction", "Contrainte et allongement en traction ou compression simple",
     "traction|compression|allongement|contrainte normale|contrainte|contrainte admissible|coefficient de sécurité"),
    ("sollicitations", "cis", "Cisaillement", "Cisaillement : clavette, goupille, rivet, contrainte tangentielle",
     "cisaillement|clavette|goupille|rivet|contrainte tangentielle|jourawski|pression de matage|matage|arbre"),
    ("sollicitations", "tor", "Torsion", "Torsion d'un arbre : contrainte, angle de torsion, couple",
     "torsion|moment de torsion|couple|angle de torsion|arbre|arbre de transmission|contrainte de cisaillement"),
    ("sollicitations", "fle", "Flexion", "Flexion simple : moment fléchissant, contrainte, flèche",
     "flexion|moment fléchissant|moment|contrainte de flexion|flèche|module de flexion|inertie"),
    ("tenseurs", "", "", "Contraintes principales, cercle de Mohr, Von Mises et Tresca",
     "tenseur|tenseurs|contrainte principale|contraintes principales|cercle de mohr|mohr|von mises|tresca|rankine|critère de rankine|contrainte normale maximale|critère|critère de plasticité|contrainte équivalente|état de contrainte|contrainte plane|cisaillement maximal"),
    ("hooke", "hoo", "Hooke", "Loi de Hooke généralisée : contraintes et déformations",
     "hooke|loi de hooke|déformation|module d'young|module de young|coefficient de poisson|poisson|élasticité|contrainte"),
    ("hooke", "jau", "Jauges", "Rosettes de jauges de déformation",
     "jauge|jauges|rosette|rosettes|extensométrie|jauge de déformation|déformation"),
    # ---- Liaisons et guidages
    ("ajustements", "", "", "Ajustement ISO 286 : écarts, cotes limites, jeu ou serrage",
     "ajustement|ajustements|iso 286|iso 286-1|iso 286-2|tolérance|écart|cote limite|cotes limites|jeu|serrage|alésage|arbre|it|qualité|classe de tolérance|ajustement glissant|ajustement serré|zone de tolérance|h7/g6|h7/p6|h7/r6|h7/s6"),
    ("frettage", "", "", "Frettage : serrage nécessaire, contraintes, température de chauffe",
     "frettage|fretté|frette|emmanchement|ajustement serré|serrage|pression de contact|lamé|température de chauffe|chauffage|dilatation|couple transmissible|ajustement|iso 286"),
    ("paliers", "", "", "Palier lisse : pression, vitesse et produit PV",
     "palier lisse|palier|paliers|coussinet|bague|pression|vitesse|produit pv|pv|frottement|glissement"),
    ("roulements", "rlt", "Durée de vie", "Durée de vie L10 d'un roulement (ISO 281)",
     "roulement|roulements|durée de vie|l10|l10h|iso 281|charge dynamique|charge équivalente|charge radiale|charge axiale|fiabilité|capacité de charge|palier"),
    ("roulements", "rlt_ens", "Ensemble", "Ensemble de roulements : réactions et durée de vie de la liaison",
     "ensemble de roulements|liaison pivot|pivot|montage|deux roulements|réactions|arbre"),
    ("roulements", "rlt_regle", "Règles de montage", "Règles de montage d'un roulement selon la bague tournante ou fixe",
     "règles de montage|montage|bague intérieure|bague extérieure|bague tournante|bague fixe"),
    # ---- Transmission
    ("engrenages", "eng", "Engrènement", "Engrenage droit : module, nombre de dents, entraxe, angle de pression, effort en pied de dent",
     "engrenage|engrenages|engrènement|module|nombre de dents|denture|dent|entraxe|angle de pression|rapport de transmission|rapport de réduction|pignon|roue|diamètre primitif|lewis|pied de dent|effort tangentiel|réducteur"),
    ("engrenages", "trn", "Train d'engrenages", "Train d'engrenages simple : rapports et vitesses",
     "train d'engrenages|train simple|rapport de transmission|rapport|réducteur|vitesse de sortie|vitesse"),
    ("engrenages", "epi", "Épicycloïdal", "Train épicycloïdal : planétaire, satellites, porte-satellites",
     "train épicycloïdal|épicycloïdal|planétaire|satellite|satellites|porte-satellite|couronne|solaire|réducteur"),
    ("freins", "frn", "Frein à disque", "Couple de freinage d'un frein à disque",
     "frein|freins|frein à disque|disque|couple de freinage|plaquette|garniture|friction|adhérence"),
    ("freins", "emb", "Embrayage", "Embrayage : synchronisation, énergie dissipée, couple transmissible",
     "embrayage|synchronisation|friction|énergie dissipée|couple transmissible|disque|glissement"),
    ("moteur", "", "", "Choix d'un moteur : couple thermique, couple de pointe, inertie ramenée",
     "moteur|motoréducteur|couple thermique|couple équivalent|couple de pointe|inertie ramenée|inertie|puissance|vitesse|cycle|réducteur|dimensionnement moteur|servomoteur"),
    # ---- Données et aide
    ("convertisseur", "", "", "Conversion entre unités (longueur, force, pression, couple…)",
     "convertisseur|conversion|convertir|unité|unités|pouce|inch|psi|bar|mpa|pascal|newton|kgf|daN|n·m|kw|cv|cheval|température|fahrenheit"),
    ("base", "mat", "Matériaux", "Base de matériaux : module E, limite élastique Re, Rm, masse volumique",
     "matériau|matériaux|acier|inox|aluminium|fonte|titane|bronze|laiton|s235|s355|316l|module d'young|limite élastique|re|rm|masse volumique|densité|coefficient de dilatation"),
    ("base", "pro", "Profilés", "Profilés normalisés : IPE, HEA, HEB, UPN, et ajouts",
     "profilé|profilés|ipe|hea|heb|hem|upn|ipn|cornière|tube|section normalisée|catalogue de profilés"),
    ("base", "mata", "Matage", "Pressions de matage admissibles selon la liaison",
     "pression de matage|matage|pression admissible|clavette|cannelure|liaison"),
    ("base", "kt", "Abaques Kt", "Concentration de contrainte (Peterson) : Kt d'un arbre épaulé ou d'une plaque percée",
     "kt|concentration de contrainte|peterson|arbre épaulé|épaulement|congé|trou|plaque percée|entaille|abaque|abaques"),
    ("base", "fic", "Mes ajouts", "Matériaux et profilés ajoutés, import et export",
     "mes ajouts|ajout|import|export|matériau utilisateur|fichier"),
    ("references", "", "", "Normes, cours et documents cités par l'application",
     "références|norme|normes|bibliographie|cours|eurocode 3|eurocode|iso 286|iso 898-1|iso 68-1|iso 281|en 1993|université de bordeaux|iut|source|document"),
    ("limites", "", "", "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas",
     "limites|limite|vérifications|vérification|validation|tests|précision|matlab|erreur|hypothèses|domaine de validité"),
]  # fmt: skip

# (page du site, calcul) → (page du bureau, onglet) ; onglet = rang (page à sous-onglets), nom (Matériaux et profilés,
# mode de Poutres) ou None. Ce qui n'est pas ici ouvre la page du même nom (id du site traduit par `vers_bureau`).
CIBLES: dict[tuple[str, str], tuple[str, int | str | None]] = {
    ("poutres", "beam"): ("poutres", "Poutre 2D"), ("poutres", "ossature"): ("poutres", "Ossature 3D"),
    ("engrenages", "eng"): ("engrenages", 0), ("engrenages", "trn"): ("engrenages", 1),
    ("engrenages", "epi"): ("epicycloidaux", None),
    ("roulements", "rlt"): ("roulements", 0), ("roulements", "rlt_ens"): ("roulements", 1), ("roulements", "rlt_regle"): ("roulements", 2),
    ("freins", "frn"): ("freins_embrayages", 0), ("freins", "emb"): ("freins_embrayages", 1),
    ("sollicitations", "tra"): ("sollicitations", 0), ("sollicitations", "cis"): ("sollicitations", 1),
    ("sollicitations", "tor"): ("sollicitations", 2), ("sollicitations", "fle"): ("sollicitations", 3),
    ("hooke", "hoo"): ("hooke_jauges", 0), ("hooke", "jau"): ("hooke_jauges", 1),
    ("base", "mat"): ("base_de_donnees", "Matériaux"), ("base", "pro"): ("base_de_donnees", "Profilés"),
    ("base", "mata"): ("base_de_donnees", "Pressions de matage"), ("base", "kt"): ("base_de_donnees", "Abaques Kt"),
    ("base", "fic"): ("base_de_donnees", "Mes données"),
}  # fmt: skip

# Classes de tolérance usuelles (h7, g6, k6…) : générées, pour que « H8 » ou « k6 » mènent aux ajustements.
_CLASSES = {"h": (5, 11), "g": (5, 7), "f": (6, 8), "e": (7, 9), "d": (8, 11), "js": (5, 8), "k": (5, 7), "m": (5, 7),
            "n": (5, 7), "p": (5, 7), "r": (5, 7), "s": (5, 7), "t": (5, 7), "u": (5, 8)}  # fmt: skip
CLASSES = [f"{lettre}{g}" for lettre, (a, b) in _CLASSES.items() for g in range(a, b + 1)]

# Calculs que l'application n'a pas : la recherche le dit (au lieu de ne rien répondre) et propose les pages les plus proches.
# (mots séparés par « | », message, [(page du site, onglet), …])
_ABSENTS = [
    ("ressort|ressorts|raideur de ressort|spire|spires", "Pas de calcul de ressort pour l'instant.", [("hooke", "hoo"), ("poutres", "beam")]),
    ("soudure|soudures|cordon de soudure|soudage|souder", "Pas de calcul de soudure pour l'instant.", [("poutres", "beam"), ("sollicitations", "cis")]),
]  # fmt: skip

LIBELLE = "Rechercher un calcul, une grandeur, une norme"
AIDE = "Exemples : flèche, H7, von mises, roulement, ISO 286, Eurocode 3. Flèches haut et bas pour choisir, Entrée pour ouvrir, Échap pour fermer."


def norme(texte: Any) -> str:
    """Sans accents ni majuscules, ponctuation réduite à une espace (« Wöhler » → « wohler »)."""
    t = unicodedata.normalize("NFD", str(texte))
    t = "".join(c for c in t if not 0x300 <= ord(c) <= 0x36F).lower().replace("œ", "oe")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _termes(liste: list[str]) -> list[dict]:
    out = []
    for t in (norme(x) for x in liste):
        if t:
            out.append({"t": t, "mots": t.split(" "), "compact": t.replace(" ", "")})
    return out


class Index:
    """Entrées cherchables : celles de la table, plus les pages que la table ne cite pas (trouvées par titre et phrase)."""

    def __init__(self, libelles: dict[str, str], famille_de: dict[str, str], intros: dict[str, str]) -> None:
        self.entrees: list[dict] = []
        vues: set[str] = set()
        for ordre, (page_site, calc, etiquette, raison, mots) in enumerate(TABLE):
            cible, onglet = CIBLES.get((page_site, calc), (vers_bureau(page_site), None))
            if cible not in libelles:
                continue
            liste = mots.split("|")
            if page_site == "ajustements":
                liste += CLASSES
            titre = libelles[cible]
            liste += [titre, page_site.replace("-", " ")]
            if famille_de.get(cible):
                liste.append(famille_de[cible])
            vues.add(cible)
            self.entrees.append({"page": cible, "onglet": onglet, "calc": calc, "etiquette": "" if cible == "epicycloidaux" else etiquette,
                                 "raison": raison, "termes": _termes(liste), "ordre": ordre, "titre": titre})  # fmt: skip
        for ident, titre in libelles.items():
            if ident == "accueil" or ident in vues:
                continue
            texte = intros.get(titre, "") or "Version, auteur et licence de l'application"
            self.entrees.append({"page": ident, "onglet": None, "calc": "", "etiquette": "", "raison": texte,
                                 "termes": _termes([titre, texte]), "ordre": 1000 + len(self.entrees), "titre": titre})  # fmt: skip
        self.absents = [
            {"mots": [norme(m) for m in mots.split("|")], "message": msg, "proches": proches}
            for mots, msg, proches in _ABSENTS
        ]

    def absent(self, texte: str) -> dict | None:
        q = norme(texte)
        if len(q) < 4:
            return None
        jetons = q.split(" ")
        for a in self.absents:
            for m in a["mots"]:
                if (
                    q == m
                    or m in q
                    or any(len(j) >= 4 and (j == m or (m.startswith(j) and len(j) >= 5)) for j in jetons)
                ):
                    return a
        return None

    def chercher(self, texte: str) -> list[dict]:
        """Au plus huit résultats, les mieux notés d'abord (puis l'ordre de la table)."""
        q = norme(texte)
        if not q:
            return []
        jetons = q.split(" ")
        notes = []
        for e in self.entrees:
            total, ok = 0, True
            for j in jetons:
                meilleur = 0
                for t in e["termes"]:
                    for m in t["mots"]:
                        meilleur = max(meilleur, _note_mot(j, m))
                    if len(j) >= 4 and j in t["compact"]:
                        meilleur = max(meilleur, 2)  # « vonmises » trouve « von mises »
                if not meilleur:
                    ok = False
                    break
                total += meilleur
            if not ok:
                continue
            bonus = 0  # la phrase entière, telle qu'écrite, compte plus que des mots épars
            for t in e["termes"]:
                bonus = max(bonus, 8 if t["t"] == q else 4 if t["t"].startswith(q) else 2 if q in t["t"] else 0)
            notes.append((total + bonus, e))
        notes.sort(key=lambda x: (-x[0], x[1]["ordre"]))
        vus: set[tuple[str, Any]] = set()
        res = []
        for _, e in notes:
            if (e["page"], e["calc"]) in vus:
                continue
            vus.add((e["page"], e["calc"]))
            res.append(e)
            if len(res) == 8:
                break
        return res

    def resultats(self, texte: str) -> tuple[list[dict], dict | None]:
        """(résultats, calcul absent signalé) : si le calcul cherché n'existe pas, ses pages proches passent devant."""
        res = self.chercher(texte)
        manque = self.absent(texte)
        if manque:
            proches = []
            for p, c in manque["proches"]:
                e = next((x for x in self.entrees if (x["page"], x["calc"]) == (_vers(p, c), c)), None)
                if e is not None and e not in proches:
                    proches.append(e)
            res = [*proches, *[e for e in res if e not in proches]][:8]
        return res, manque


def _vers(page_site: str, calc: str) -> str:
    return CIBLES.get((page_site, calc), (vers_bureau(page_site), None))[0]


def _note_mot(q: str, m: str) -> int:
    """6 identique, 4 début de mot, 3 pluriel (« roulements » → « roulement »), 2 morceau (4 lettres au moins)."""
    if m == q:
        return 6
    if m.startswith(q):
        return 4
    if len(m) >= 4 and q.startswith(m) and len(q) - len(m) <= 2:
        return 3
    if len(q) >= 4 and q in m:
        return 2
    return 0


def ouvrir_cible(fenetre: Any, r: dict) -> None:
    """Ouvre la page du résultat, sur l'onglet du calcul cherché (réglage d'affichage seulement : aucune donnée ne change)."""
    ident, onglet = r["page"], r["onglet"]
    page = fenetre.page(ident)
    if isinstance(onglet, int):
        state.v[f"onglet.{type(page).__name__}"] = onglet
        if getattr(page, "bati", False) and hasattr(page, "onglets"):
            page.onglets.setCurrentIndex(onglet)
    elif isinstance(onglet, str) and ident == "base_de_donnees":
        state.v["onglet.base_de_donnees"] = onglet
    elif isinstance(onglet, str) and ident == "poutres":
        state.v["poutres.mode"] = onglet
        if getattr(page, "bati", False) and hasattr(page, "basculer"):
            page.basculer()
    fenetre.aller(ident)


class Recherche(QDialog):
    """Boîte de recherche : un champ, une liste de résultats ; Entrée ouvre la page choisie, Échap ferme."""

    def __init__(self, fenetre: Any, index: Index) -> None:
        super().__init__(fenetre)
        self.fenetre, self.index = fenetre, index
        self.resultats: list[dict] = []
        self.setWindowTitle("Rechercher")
        self.setModal(True)
        self.resize(600, 460)
        v = QVBoxLayout(self)
        self.champ = QLineEdit()
        self.champ.setPlaceholderText(LIBELLE)
        self.champ.setAccessibleName(LIBELLE)
        self.champ.setClearButtonEnabled(True)
        self.champ.setMaxLength(80)
        self.aide = QLabel(AIDE)
        self.aide.setObjectName("legende")
        self.aide.setWordWrap(True)
        self.liste = QListWidget()
        self.liste.setAccessibleName("Résultats de la recherche")
        self.liste.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # le focus reste dans le champ : on choisit aux flèches
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.setStyleSheet(f"QListWidget::item:selected{{background:{theme.actuel()['selection']};}}")
        v.addWidget(self.champ)
        v.addWidget(self.aide)
        v.addWidget(self.liste, 1)
        self.champ.textChanged.connect(self.maj)
        self.champ.returnPressed.connect(lambda: self.choisir(self.liste.currentRow()))
        self.liste.itemActivated.connect(lambda it: self.choisir(self.liste.row(it)))
        self.liste.itemClicked.connect(lambda it: self.choisir(self.liste.row(it)))
        self.champ.setFocus()
        self.maj("")

    def maj(self, texte: str) -> None:
        self.resultats, manque = self.index.resultats(texte)
        self.liste.clear()
        gris = theme.actuel()["discret"]
        for r in self.resultats:
            titre = r["titre"] + (" › " + r["etiquette"] if r["etiquette"] else "")
            etiquette = QLabel(
                f"<b>{_html(titre)}</b><br><span style='color:{gris};font-size:9.5pt'>{_html(r['raison'])}</span>"
            )
            etiquette.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            etiquette.setStyleSheet("background:transparent;padding:3px 4px;")
            etiquette.setWordWrap(True)
            etiquette.setFixedWidth(540)
            item = QListWidgetItem()
            item.setSizeHint(QSize(540, etiquette.heightForWidth(540) + 8))
            item.setToolTip(r["raison"])
            self.liste.addItem(item)
            self.liste.setItemWidget(item, etiquette)
        if self.resultats:
            self.liste.setCurrentRow(0)
        if manque:
            self.aide.setText(manque["message"] + (" Pages les plus proches ci-dessous." if self.resultats else ""))
        elif not norme(texte):
            self.aide.setText(AIDE)
        elif not self.resultats:
            self.aide.setText(
                f"Aucun résultat pour « {texte.strip()} ». Essayez un seul mot : flèche, H7, roulement, module, Eurocode 3…"
            )
        else:
            n = len(self.resultats)
            self.aide.setText(
                f"{n} résultat{'s' if n > 1 else ''}. Flèches haut et bas pour choisir, Entrée pour ouvrir, Échap pour fermer."
            )

    def keyPressEvent(self, e: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.resultats:
            pas = 1 if e.key() == Qt.Key.Key_Down else -1
            self.liste.setCurrentRow((self.liste.currentRow() + pas) % len(self.resultats))
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choisir(self.liste.currentRow())
        else:
            super().keyPressEvent(e)

    def choisir(self, i: int) -> None:
        if not 0 <= i < len(self.resultats):
            return
        r = self.resultats[i]
        self.accept()
        ouvrir_cible(self.fenetre, r)


def _html(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
