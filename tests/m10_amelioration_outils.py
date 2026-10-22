# -*- coding: utf-8 -*-
"""Section 8 — amélioration : propositions — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 8. Amélioration : proposition refusée si dangereuse, validée sinon
retour = evolution.proposer_outil("outil_mechant", "import os\nos.system('dir')")
verif("proposition dangereuse refusée", "refusée" in retour, retour)
BON_CODE = ("from outils import outil\n"
            "@outil('compteur_lettres_test', 'Compte les lettres.', "
            "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
            "def compteur_lettres_test(texte):\n    return f'{len(texte)} lettres'\n")
retour = evolution.proposer_outil("compteur_lettres_test", BON_CODE)
verif("proposition saine enregistrée", "enregistrée" in retour, retour)
retour = evolution.valider("compteur_lettres_test")
verif("validation → perso", "validée" in retour, retour)
r = executer("compteur_lettres_test", {"texte": "abc"}, Garde(lambda n, d: False))
verif("outil perso exécutable", r["ok"] and "3" in r["texte"], r["texte"])
# nettoie l'outil de test
perso = Path(__file__).resolve().parent.parent / "outils" / "perso" / "compteur_lettres_test.py"
perso.unlink(missing_ok=True)
OUTILS.pop("compteur_lettres_test", None)
