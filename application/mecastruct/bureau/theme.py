"""Thème de l'application de bureau : les mêmes couleurs que le site (docs/style.css), en clair et en sombre.

`actuel()` donne la palette en cours ; `definir("clair" | "sombre")` la change. Les widgets lisent la palette quand ils
sont construits : après un changement de thème, la fenêtre reconstruit ses pages (main.py, Fenetre.changer_theme).
"""

import json
import re

CLAIR = {
    "nom": "clair", "fond": "#F6F4FA", "carte": "#FFFFFF", "encre": "#2A1B4A", "discret": "#5E5577", "bord": "#C9C1E0",
    "bordFort": "#5C4B99", "accent": "#5C4B99", "surAccent": "#FFFFFF", "bandeau": "#3D246C", "alt": "#F1EEF8",
    "lien": "#4A3A8C", "info": ("#E7E3F4", "#2A1B4A"), "succes": ("#D3F2DC", "#0B3D1A"),
    "avertissement": ("#FFE8B8", "#5A3A00"), "erreur": ("#FFD3D3", "#6B0A12"), "jaugeOk": "#1E8E4A",
    "jaugeKo": "#C62B36", "selection": "#DAD3F0",
}  # fmt: skip
SOMBRE = {
    "nom": "sombre", "fond": "#0F0C18", "carte": "#1A1626", "encre": "#EDE6F7", "discret": "#B7ABD8", "bord": "#3A3254",
    "bordFort": "#9F91CC", "accent": "#7A68C0", "surAccent": "#FFFFFF", "bandeau": "#2C2348", "alt": "#211C30",
    "lien": "#C8BDF0", "info": ("#2A2342", "#E4DDF7"), "succes": ("#123522", "#BFEBCC"),
    "avertissement": ("#3E2F0B", "#FFE0A3"), "erreur": ("#431419", "#FFCBCF"), "jaugeOk": "#45B872",
    "jaugeKo": "#F0707A", "selection": "#3A3254",
}  # fmt: skip

_courant = {"palette": CLAIR}


def actuel() -> dict:
    return _courant["palette"]


def sombre() -> bool:
    return _courant["palette"] is SOMBRE


def definir(nom: str) -> dict:
    """Choisit le thème « clair » ou « sombre » (tout autre mot : clair)."""
    _courant["palette"] = SOMBRE if nom == "sombre" else CLAIR
    return _courant["palette"]


def couleur_message(niveau: str) -> tuple[str, str]:
    """(fond, texte) d'un bandeau « info », « succes », « avertissement » ou « erreur »."""
    return actuel().get(niveau, actuel()["info"])


# figures du calcul (plots/_common.py) : noir et blanc du thème clair → couleurs du thème sombre, comme sur le site
_COULEURS_SOMBRES = {"rgba(0,0,0,1)": "#EDE6F7", "black": "#EDE6F7", "#000000": "#EDE6F7", "white": "#1A1626",
                     "#FFFFFF": "#1A1626", "#ffffff": "#1A1626", "rgba(255,255,255,1)": "#1A1626"}  # fmt: skip
_MOTIF = re.compile(r'"(rgba\(0,0,0,1\)|black|white|#000000|#FFFFFF|#ffffff|rgba\(255,255,255,1\))"')


def figure_sombre(fig):
    """Copie de la figure Plotly aux couleurs du thème sombre (fond, textes, traits noirs ou blancs)."""
    import plotly.graph_objects as go

    texte = _MOTIF.sub(lambda m: f'"{_COULEURS_SOMBRES[m.group(1)]}"', fig.to_json())
    sombre_ = go.Figure(json.loads(texte))
    p = SOMBRE
    sombre_.update_layout(paper_bgcolor=p["carte"], plot_bgcolor=p["carte"], font_color=p["encre"])
    sombre_.update_xaxes(gridcolor=p["bord"], zerolinecolor=p["bordFort"])
    sombre_.update_yaxes(gridcolor=p["bord"], zerolinecolor=p["bordFort"])
    return sombre_


def feuille_de_style() -> str:
    """Feuille de style Qt de toute l'application, d'après la palette en cours (même allure que le site)."""
    p = actuel()
    fond, carte, encre, discret, bord, fort, accent = (p[k] for k in ("fond", "carte", "encre", "discret", "bord", "bordFort", "accent"))
    return f"""
    QWidget {{ background:{fond}; color:{encre}; font-size:11pt; }}
    QLabel {{ background:transparent; }}
    QToolTip {{ background:{carte}; color:{encre}; border:1px solid {fort}; }}
    #titre {{ font-size:21pt; font-weight:bold; }}
    #intro {{ color:{discret}; font-size:11.5pt; }}
    #sousTitre {{ font-size:13pt; font-weight:bold; margin-top:10px; border-bottom:2px solid {bord}; padding-bottom:2px; }}
    #legende {{ font-size:9.5pt; color:{discret}; }}
    #brut {{ font-family:Consolas,monospace; font-size:9.5pt; }}
    #formule {{ background:{carte}; border:1px solid {bord}; border-left:3px solid {accent}; padding:6px 10px;
                font-size:12pt; }}
    #etiquette {{ font-size:10pt; margin-top:3px; }}
    #metrique, #cadre {{ background:{carte}; border:1px solid {bord}; border-radius:6px; }}
    #metrique QLabel, #cadre QLabel, #cadre QWidget {{ background:transparent; }}
    #metriqueLibelle {{ font-size:9pt; color:{discret}; }}
    #metriqueValeur {{ font-size:14pt; font-weight:bold; }}
    #metriqueDelta {{ font-size:9pt; }}
    QRadioButton::indicator, QCheckBox::indicator, QListWidget::indicator {{ width:14px; height:14px;
        background:{carte}; border:1px solid {fort}; }}
    QRadioButton::indicator {{ border-radius:8px; }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked, QListWidget::indicator:checked {{
        background:{accent}; }}
    QLineEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {{
        background:{carte}; border:1px solid {fort}; border-radius:5px; padding:4px; }}
    QComboBox QAbstractItemView {{ background:{carte}; color:{encre}; selection-background-color:{accent};
        selection-color:{p['surAccent']}; }}
    QTableWidget {{ gridline-color:{bord}; }}
    QTableWidget::item:selected {{ background:{p['selection']}; color:{encre}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color:{discret}; }}
    QHeaderView::section {{ background:{p['bandeau']}; color:#FFFFFF; padding:4px; border:none; }}
    #bouton {{ background:{carte}; border:1px solid {fort}; border-radius:5px; padding:7px 14px; }}
    #bouton:hover {{ border-color:{encre}; }}
    #bouton:disabled, #primaire:disabled {{ color:{discret}; }}
    #primaire {{ background:{accent}; color:{p['surAccent']}; border:1px solid {accent}; border-radius:5px;
                 padding:8px 24px; font-weight:bold; }}
    #lien {{ background:transparent; border:none; color:{p['lien']}; text-decoration:underline; text-align:left;
             padding:2px; }}
    #repli {{ background:{carte}; border:1px solid {bord}; border-radius:8px; }}
    #repli QLabel {{ background:transparent; }}
    #bandeau {{ background:{fond}; }}
    #marque {{ font-size:16pt; font-weight:bold; }}
    #confiance {{ font-size:9.5pt; color:{discret}; }}
    #barreMenu {{ background:{fond}; border-bottom:2px solid {fort}; }}
    #famille, #sousmenu {{ background:transparent; color:{encre}; border:1px solid transparent; border-radius:6px;
                           padding:6px 14px; }}
    #famille {{ font-weight:bold; font-size:11.5pt; }}
    #sousmenu {{ font-size:10.5pt; padding:4px 14px; }}
    #famille:hover, #sousmenu:hover {{ border-color:{fort}; }}
    #famille:checked, #sousmenu:checked {{ background:{accent}; color:{p['surAccent']}; }}
    QTabWidget::pane {{ border:1px solid {fort}; border-radius:0 6px 6px 6px; }}
    QTabBar::tab {{ background:{carte}; border:1px solid {fort}; border-bottom:none; border-radius:6px 6px 0 0;
                    padding:6px 12px; margin-right:4px; }}
    QTabBar::tab:selected {{ background:{accent}; color:{p['surAccent']}; }}
    QScrollBar:vertical {{ background:{fond}; width:12px; }}
    QScrollBar::handle:vertical {{ background:{bord}; border-radius:5px; min-height:24px; }}
    QScrollBar:horizontal {{ background:{fond}; height:12px; }}
    QScrollBar::handle:horizontal {{ background:{bord}; border-radius:5px; min-width:24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
    QSplitter::handle {{ background:{bord}; }}
    """
