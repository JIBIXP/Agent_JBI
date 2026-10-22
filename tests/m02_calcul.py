# -*- coding: utf-8 -*-
"""Section 2 — calcul sécurisé — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 2. Calcul
r = executer("calculer", {"expression": "(12*7)/3 + sqrt(16)"}, Garde(lambda n, d: False))
verif("calculer", r["ok"] and "32" in r["texte"], r["texte"])
r = executer("calculer", {"expression": "__import__('os').system('x')"}, Garde(lambda n, d: False))
verif("calculer refuse l'injection", "impossible" in r["texte"], r["texte"])
