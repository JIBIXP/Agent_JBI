# -*- coding: utf-8 -*-
"""Section 19 — wake-word : modèle officiel — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 19. Wake-word : modèle officiel référencé, repli propre sans paquet
from audio import wake  # noqa: E402

verif("modèle wake officiel déclaré", "hey_jarvis" in wake.MODELES_OFFICIELS.get("jarvis", ""))
verif("wake inconnu refusé", "inconnu" in wake.telecharger("jibi_inexistant"))
