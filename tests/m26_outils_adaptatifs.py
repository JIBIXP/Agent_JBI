# -*- coding: utf-8 -*-
"""Section 24 — jeu d'outils adaptatif — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 24. Jeu d'outils adaptatif (leçon Jarvis : petit modèle + 47 outils = noyade)
from outils import NOYAU, catalogue_pour_llm, outils_pour_message  # noqa: E402

base = outils_pour_message("bonjour")
verif("noyau du quotidien toujours montré", set(base) >= NOYAU and len(base) < 25, f"{len(base)} outils")
etendu = outils_pour_message("éteins le PC et regarde mon écran")
verif("extension par mots-clés", {"eteindre_pc", "voir_ecran"} <= set(etendu))
complet = catalogue_pour_llm()
filtre = catalogue_pour_llm(outils_pour_message("quelle heure est-il ?"))
verif("catalogue filtré ~2× plus court", 0 < len(filtre) < len(complet) // 2, f"{len(filtre)}/{len(complet)} car.")
verif("filtrage respecté", "voir_ecran" not in filtre and "heure_actuelle" in filtre)
