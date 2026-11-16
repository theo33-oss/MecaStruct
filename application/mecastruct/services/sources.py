"""Sources des cours citées sous les pages de calcul : une seule rédaction, lue par le bureau et par le site.

La clé est l'identifiant du calcul (celui des pages de bureau et du pont web). Le détail bibliographique (auteur,
établissement, année) est dans data/references.json, page « Références ».
"""

_ROULEMENTS = "cours « Calcul sur les roulements » (IUT de Bordeaux, GMP)"

SOURCES: dict[str, str] = {
    "rlt": (
        f"Source : {_ROULEMENTS}, p. 11 à 19. L'exemple du cours (p. 19) prend Y = 1,31, borne de la table, et annonce "
        "L10 = 185,3 M tours : ce résultat est celui d'un roulement de C = 61,8 kN, pas de C = 35,8 kN (36,0 M tours). "
        "Le cours écrit aussi e = 0,0265 pour 0,2657 et Y = 1,59 pour 1,66 (p. 18) : coquilles du cours, ici e et Y sont "
        "interpolés correctement."
    ),
    "rlt_ens": f"Source : {_ROULEMENTS}, p. 12. La formule imprimée de l'ensemble iso-fiable contient une coquille (25000 au lieu de 15000).",
    "rlt_regle": "Source : cours « Liaison pivot par roulements » (R3.05 ICM S3, IUT de Bordeaux), p. 24 à 26.",
    "eng": (
        "Source : cours « Engrenages droits, relations » (IUT de Bordeaux), p. 14 à 26. Les efforts « Fn12 » et « F12 » du "
        "cours sont le Fr et le Fn de l'application."
    ),
    "trn": "Source : cours « Engrenages droits, relations » (IUT de Bordeaux), p. 12 et 17 ; exemple du train à trois étages p. 24.",
    "epi": (
        "Source : cours R4.05 ICM S4 « Train épicycloïdal » (IUT de Bordeaux), p. 12 à 19. La règle du haricot "
        "(Z1 + Z4)/n_sat entier ne vaut que pour le type I du cours (p. 14)."
    ),
    "frn": "Source : cours R5.05 ICM S5 « Frein – Embrayage » (IUT de Bordeaux), p. 8 à 10.",
    "emb": "Source : cours R5.05 ICM S5 « Frein – Embrayage » (IUT de Bordeaux), p. 15 à 20.",
    "mot": (
        "Source : cours « Chaînes de transmission de puissance » (ICM S4, IUT de Bordeaux), p. 17 et 18 : "
        "accélération de 0,5 s (vmax/γmax) ; la durée du régime établi (4,32 s) est déduite pour retrouver 61 N·m."
    ),
    "fre": (
        "Source : « Abaque de frettage » (cours ICM, IUT de Bordeaux) et classeur NF E22-620 de l'auteur. Pour la "
        "rugosité, le cours retire 4(Ra arbre + Ra alésage), soit 6,4 µm pour Ra 0,8 et 12,8 µm pour Ra 1,6, la norme 5 "
        "et 10 µm (valeurs conseillées). Arbre plein : l'abaque donne σ équivalente = p ; l'application garde 2p pour "
        "le coefficient de sécurité (classeur, prudent)."
    ),
    "ten": (
        "Source : cours Continuum Mechanics (Université de Bordeaux, 2025), lectures 4 et 9. L'invariant I2 de "
        "l'application est la somme des mineurs principaux, de signe opposé au I2 du cours (lecture 4, diapo 14) : les "
        "contraintes principales sont identiques."
    ),
    "hoo": (
        "Source : cours Continuum Mechanics (Université de Bordeaux, 2025), lecture 6. Ordre des cisaillements de la "
        "matrice : xx, yy, zz, yz, xz, xy ; le cours range 11, 22, 33, 12, 13, 23 (diapos 18-19), donc son C44 est la "
        "case xy ici. Jauges et rosettes : formules classiques de l'extensométrie, sans cours de référence."
    ),
    "jau": "Formules classiques de l'extensométrie (jauge de Bridgman, pont de Wheatstone, rosettes) : aucun cours du dossier de référence ne les traite.",
    "beam": (
        "Fatigue : cours Éléments de dimensionnement en fatigue (M2 Génie mécanique, Université de Bordeaux), "
        "p. 44, 52 à 63 et 95 (Goodman, σD, Kf)."
    ),
}


def source(ident: str) -> str:
    """Phrase de source du calcul `ident` (texte vide s'il n'y en a pas)."""
    return SOURCES.get(ident, "")


def avec_sources(formulaires: dict) -> dict:
    """Ajoute la source de chaque calcul à la note de son formulaire (pont web) ; renvoie le même dictionnaire."""
    for ident, f in formulaires.items():
        if source(ident):
            f["note"] = (f.get("note", "") + " " + source(ident)).strip()
    return formulaires
