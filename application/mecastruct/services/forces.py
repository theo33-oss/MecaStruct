"""Force inclinée : une norme F et un angle α dans un plan (xy, xz ou yz) donnent les composantes Fx, Fy, Fz.

Dans le plan choisi, l'angle part du premier axe vers le second (sens trigonométrique) :
xy : Fx = F·cos α, Fy = F·sin α ; xz : Fx = F·cos α, Fz = F·sin α ; yz : Fy = F·cos α, Fz = F·sin α.
La composante hors du plan vaut 0. Le solveur ne lit jamais F ni α : seulement Fx, Fy, Fz.
"""

import math

AXES = {"xy": ("Fx", "Fy"), "xz": ("Fx", "Fz"), "yz": ("Fy", "Fz")}


def composantes(F: float, angle_deg: float, plan: str = "xy") -> dict:
    """{Fx, Fy, Fz} d'une force F (même unité que la sortie) inclinée de `angle_deg` degrés dans `plan`.

    Erreur : ValueError si le plan n'est ni xy, ni xz, ni yz."""
    if plan not in AXES:
        raise ValueError(f"Plan de la force inclinée « {plan} » inconnu : xy, xz ou yz.")
    a = math.radians(float(angle_deg))
    premier, second = AXES[plan]
    sortie = {"Fx": 0.0, "Fy": 0.0, "Fz": 0.0}
    for nom, v in ((premier, F * math.cos(a)), (second, F * math.sin(a))):
        sortie[nom] = 0.0 if abs(v) < 1e-12 * abs(F) else v  # cos 90° ≈ 6e-17 : ramené à 0
    return sortie


def _reel(v) -> float:
    """Nombre d'une cellule : 0 si elle est absente, vide ou NaN (colonne manquante d'un tableau pandas)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) else x


def appliquer_polaire(ligne: dict, plan_defaut: str = "xy") -> dict:
    """Copie de `ligne` où Fx, Fy, Fz viennent de F, α et du plan si F ≠ 0 ; inchangée sinon."""
    F = _reel(ligne.get("F"))
    if F == 0:
        return dict(ligne)
    plan = ligne.get("plan")
    plan = plan if isinstance(plan, str) and plan else plan_defaut
    return {**ligne, **composantes(F, _reel(ligne.get("ang")), plan)}
