"""Outil calcul de JIBI 2 : évaluation sûre d'expressions mathématiques (AST)."""
from __future__ import annotations

import ast
import math

from outils import outil

_OPERATIONS = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
_FONCTIONS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "min": min, "max": max,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
    "exp": math.exp, "pi": None, "e": None,
}


@outil("calculer", "Calcule une expression mathématique : nombres, + - * / // % **, parenthèses, "
                   "sqrt, sin, cos, tan, log, min, max, round, pi.",
       {"expression": {"type": "str", "obligatoire": True, "description": "ex. (12*7)/3 + sqrt(16)"}},
       categorie="calcul", exemple='{"outil": "calculer", "parametres": {"expression": "144/12 + sqrt(81)"}}')
def calculer(expression: str) -> str:
    try:
        valeur = _evaluer(ast.parse(expression, mode="eval"))
        if isinstance(valeur, float) and valeur.is_integer():
            valeur = int(valeur)
        return f"{expression} = {valeur}"
    except Exception as e:
        return f"Calcul impossible ({e}). Utilise seulement des nombres et + - * / // % ** et les fonctions sqrt, sin, cos…"


def _evaluer(noeud):
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATIONS:
        return _OPERATIONS[type(noeud.op)](_evaluer(noeud.left), _evaluer(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.UAdd, ast.USub)):
        v = _evaluer(noeud.operand)
        return v if isinstance(noeud.op, ast.UAdd) else -v
    if isinstance(noeud, ast.Name) and noeud.id in ("pi", "e"):
        return getattr(math, noeud.id)
    if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
            and noeud.func.id in _FONCTIONS and not noeud.keywords):
        return _FONCTIONS[noeud.func.id](*[_evaluer(a) for a in noeud.args])
    raise ValueError("expression non autorisée")
