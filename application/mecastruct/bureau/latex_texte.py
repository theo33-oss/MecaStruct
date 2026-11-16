"""LaTeX → texte Unicode copiable : les formules de l'interface sont du vrai texte, pas des images.

Couvre les commandes utilisées par l'application (fractions, racines, indices et exposants, lettres grecques, opérateurs,
vecteurs). Une commande inconnue est écrite par son nom : le résultat reste lisible et copiable.
"""

import re

_SUP = dict(zip("0123456789+-=()nixyabcdefghjklmoprstuvwz", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱˣʸᵃᵇᶜᵈᵉᶠᵍʰʲᵏˡᵐᵒᵖʳˢᵗᵘᵛʷᶻ", strict=True))
_SUB = dict(zip("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ", strict=True))

_SYMBOLES = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ",
    "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω", "cdot": "·", "times": "×", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "sim": "∼", "equiv": "≡",
    "infty": "∞", "sum": "∑", "prod": "∏", "int": "∫", "partial": "∂", "nabla": "∇", "rightarrow": "→", "to": "→",
    "leftarrow": "←", "Rightarrow": "⇒", "Leftrightarrow": "⇔", "leftrightarrow": "↔", "circ": "°", "degree": "°",
    "cdots": "⋯", "ldots": "…", "dots": "…", "perp": "⊥", "parallel": "∥", "angle": "∠", "ell": "ℓ", "hbar": "ℏ",
    "min": "min", "max": "max", "sin": "sin", "cos": "cos", "tan": "tan", "arctan": "arctan", "arcsin": "arcsin",
    "arccos": "arccos", "ln": "ln", "log": "log", "exp": "exp", "lim": "lim", "det": "det", "sup": "sup", "inf": "inf",
    "in": "∈", "forall": "∀", "quad": "  ", "qquad": "    ", "mid": "|", "lvert": "|", "rvert": "|", "langle": "⟨",
    "rangle": "⟩", "lceil": "⌈", "rceil": "⌉", "lfloor": "⌊", "rfloor": "⌋", "bullet": "•", "ast": "∗",
    "%": "%", "&": "&", "_": "_", "#": "#", "{": "{", "}": "}", "|": "‖", ",": " ", ";": " ", ":": " ", "!": "",
    " ": " ", ">": " ",
}
_ACCENTS = {"vec": "⃗", "bar": "̄", "overline": "̄", "hat": "̂", "dot": "̇", "ddot": "̈",
            "tilde": "̃"}  # fmt: skip
_TEXTE = {"mathrm", "text", "mbox", "mathbf", "boldsymbol", "operatorname", "textbf", "mathit", "textit", "mathcal",
          "displaystyle", "textrm", "bf", "rm"}  # fmt: skip


def _groupe(s: str, i: int) -> tuple[str, int]:
    """Argument LaTeX commençant en i : contenu d'un groupe {…}, ou un seul symbole / une seule commande."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        niveau, j = 1, i + 1
        while j < len(s) and niveau:
            niveau += {"{": 1, "}": -1}.get(s[j], 0) if s[j - 1] != "\\" else 0
            j += 1
        return s[i + 1 : j - 1], j
    if s[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        return m.group(0), i + m.end()
    return s[i], i + 1


def _atomique(t: str) -> bool:
    return bool(re.fullmatch(r"[\w.,°′]+|\(.*\)|[\w.]+\([^()]*\)", t)) and not re.search(r"[+−\-×·/= ]", re.sub(r"\(.*\)", "", t))


def _entre(t: str) -> str:
    return t if _atomique(t) else f"({t})"


def _script(t: str, table: dict, marque: str) -> str:
    if all(c in table for c in t):
        return "".join(table[c] for c in t)
    return marque + (t if re.fullmatch(r"[\w.]+", t) else f"({t})")


def _converti(s: str) -> str:
    out, i = "", 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            nom, i = m.group(1), i + m.end()
            if nom in ("frac", "dfrac", "tfrac"):
                a, i = _groupe(s, i)
                b, i = _groupe(s, i)
                out += f"{_entre(_converti(a))}/{_entre(_converti(b))}"
            elif nom == "sqrt":
                if s[i : i + 1] == "[":
                    fin = s.index("]", i)
                    n, i = s[i + 1 : fin], fin + 1
                    a, i = _groupe(s, i)
                    out += _script(_converti(n), _SUP, "") + "√" + _entre(_converti(a))
                else:
                    a, i = _groupe(s, i)
                    t = _converti(a)
                    out += "√" + (t if _atomique(t) and "(" not in t else f"({t})")
            elif nom in _ACCENTS:
                a, i = _groupe(s, i)
                t = _converti(a)
                out += (t[:-1] + t[-1] + _ACCENTS[nom]) if len(t) == 1 else "".join(ch + _ACCENTS[nom] for ch in t)
            elif nom in _TEXTE:
                a, i = _groupe(s, i)
                out += _converti(a)
            elif nom == "underbrace":
                a, i = _groupe(s, i)
                legende = ""
                if s[i : i + 1] == "_":
                    legende, i = _groupe(s, i + 1)
                out += _converti(a) + (f" [{_converti(legende)}]" if legende else "")
            elif nom in ("left", "right"):
                d, i = _groupe(s, i)
                out += "" if d == "." else _converti(d)
            elif nom == "begin" or nom == "end":
                _, i = _groupe(s, i)
            elif nom == "\\":
                out += " ; "
            elif nom in ("'", '"', "`", "^", "~", "="):
                out += ""
            else:
                out += _SYMBOLES.get(nom, nom)
        elif c in "^_":
            a, i = _groupe(s, i + 1)
            t = _converti(a)
            out += _script(t, _SUP, "^") if c == "^" else _script(t, _SUB, "_")
        elif c in "{}":
            i += 1
        elif c == "~":
            out += " "
            i += 1
        elif c == "'":
            out += "′"
            i += 1
        elif c == "-":
            out += "−"
            i += 1
        else:
            out += c
            i += 1
    return out


def versTexte(tex: str) -> str:
    """Texte Unicode d'une formule LaTeX (sans les $ de début et de fin), prêt à copier-coller."""
    t = tex.strip().strip("$").strip()
    return re.sub(r" {2,}", "  ", _converti(t)).strip()
