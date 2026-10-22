# -*- coding: utf-8 -*-
"""Section 18 — dictée en continu — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 18. Dictée en continu (segments simulés, mot final « envoie »)
from audio import ecoute  # noqa: E402

SEGMENTS = iter(["écris un petit mot pour demain", "n'oublie pas le pain",
                 "envoie"])
ecoute.ecouter_phrase = lambda **params: next(SEGMENTS)
recus_partiels: list[str] = []
texte_dicte = ecoute.dicter(mot_fin="envoie", on_partiel=recus_partiels.append)
verif("dictée : texte cumulé sans le mot final",
      texte_dicte == "écris un petit mot pour demain n'oublie pas le pain",
      repr(texte_dicte))
verif("dictée : partiels diffusés", len(recus_partiels) == 2, str(recus_partiels))
SEGMENTS = iter(["juste ça", "envoie"])
verif("dictée courte", ecoute.dicter() == "juste ça")
