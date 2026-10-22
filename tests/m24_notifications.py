# -*- coding: utf-8 -*-
"""Section 22 — notifications — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 22. Notifications : outil enregistré, canal terminal fonctionnel ici
from outils import notifications  # noqa: E402

retour = notifications.notifier("JIBI test", "coucou du test")
verif("notifier répond", "notification" in retour.lower(), retour)
verif("dernière notification mémorisée", notifications.derniere == ["JIBI test", "coucou du test"])
