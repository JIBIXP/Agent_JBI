# -*- coding: utf-8 -*-
"""Section 16 — wake-word : repli propre — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 16. Wake-word : repli propre sans openwakeword
from audio import wake  # noqa: E402

verif("wake neuronal : repli propre (non installé)", wake.disponible() is False
      and wake.ecouter_mot() is False)
