# -*- coding: utf-8 -*-
"""Section 15 — analyse du code du projet — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 15. Analyse du code du projet (auto-contrôle)
from jibi2.labo import verifier_code_projet  # noqa: E402

bilan_code = verifier_code_projet()
verif("analyse du code de JIBI", "tout compile" in bilan_code and "fichiers" in bilan_code,
      bilan_code[:120])
