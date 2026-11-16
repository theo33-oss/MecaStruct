"""Page « Limites et vérifications » : le texte de LIMITES.md, comme sur le site."""

from pathlib import Path

from mecastruct.bureau.widgets import Page, Zone
from mecastruct.services.pages_texte import INTROS


def chemin_limites() -> Path | None:
    """LIMITES.md : à la racine du dépôt (code source) ou à côté des données (application empaquetée)."""
    ici = Path(__file__).resolve()
    return next((p for p in (ici.parents[3] / "LIMITES.md", ici.parents[4] / "LIMITES.md") if p.is_file()), None)


class PageLimites(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Limites et vérifications")
        z.intro(INTROS["Limites et vérifications"])
        chemin = chemin_limites()
        if chemin is None:
            z.avertissement("LIMITES.md est introuvable. Il est aussi sur GitHub : github.com/theo33-oss/MecaStruct")
            return
        texte = chemin.read_text(encoding="utf-8")
        z.texte(texte.split("\n", 1)[1] if texte.startswith("# ") else texte)  # sans le titre, déjà affiché
