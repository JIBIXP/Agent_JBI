# -*- coding: utf-8 -*-
"""Section 23 — keep_alive du LLM — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 23. keep_alive : lecture du réglage
from jibi2.llm import _keep_alive  # noqa: E402

_valeur_keep = _keep_alive()
verif("keep_alive lu du .env", _valeur_keep == -1 or
      (isinstance(_valeur_keep, str) and _valeur_keep.endswith(("m", "h"))),
      str(_valeur_keep))
