# -*- coding: utf-8 -*-
"""Section 21 — recherche du binaire Chrome — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 21. Chrome : recherche de binaire (sans lancer de navigateur)
from outils.applications import _trouver_chrome  # noqa: E402

verif("recherche Chrome/Edge renvoie une chaîne ou None",
      _trouver_chrome() is None or Path(_trouver_chrome()).exists())
