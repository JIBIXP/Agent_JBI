# -*- coding: utf-8 -*-
"""Section 4 — risque élevé confirmé puis refusé — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 4. Risque élevé : confirmation exigée puis refus
garde_refus = Garde(lambda nom, detail: False)
r = executer("executer_commande", {"commande": "echo test"}, garde_refus)
verif("action risquée bloquée sans accord", not r["ok"] and "refusé" in r["texte"])
