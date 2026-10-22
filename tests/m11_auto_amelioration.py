# -*- coding: utf-8 -*-
"""Section 9 — auto-amélioration (journal, historique) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 9. Auto-amélioration : détecter, analyser, proposer, valider, annuler
r = executer("outil_qui_nexiste_pas", {}, Garde(lambda n, d: False))
verif("outil inconnu → échec propre", not r["ok"])
journal = config.DOSSIER_JOURNAL / "erreurs.jsonl"
verif("échec noté au journal",
      journal.exists() and "outil_qui_nexiste_pas" in journal.read_text(encoding="utf-8"))
r = executer("lister_erreurs", {"mot": "outil_qui_nexiste_pas"}, Garde(lambda n, d: False))
verif("lister_erreurs retrouve l'échec", r["ok"] and "outil_qui_nexiste_pas" in r["texte"], r["texte"])
r = executer("lire_code_outil", {"nom": "calculer"}, Garde(lambda n, d: False))
verif("lire_code_outil montre la source", r["ok"] and "def calculer" in r["texte"], r["texte"])

# correction d'un outil perso : v1 puis v2, l'ancienne version part en historique
V1 = ("from outils import outil\n"
      "@outil('compteur_mots', 'Compte les mots.', "
      "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
      "def compteur_mots(texte):\n    return f\"{len(texte.split())} mots\"\n")
V2 = ("from outils import outil\n"
      "@outil('compteur_mots', 'Compte les mots, version 2.', "
      "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
      "def compteur_mots(texte):\n    return f\"V2 : {len(texte.split())} mots\"\n")
retour = evolution.proposer_outil("compteur_mots", V1)
verif("proposition v1 enregistrée", "enregistrée" in retour, retour)
verif("validation v1", "activée" in evolution.valider("compteur_mots"))
r = executer("compteur_mots", {"texte": "un deux trois"}, Garde(lambda n, d: False))
verif("compteur_mots v1 fonctionne", r["ok"] and "3 mots" in r["texte"], r["texte"])
evolution.proposer_outil("compteur_mots", V2)
evolution.valider("compteur_mots")
r = executer("compteur_mots", {"texte": "un deux trois"}, Garde(lambda n, d: False))
verif("v2 remplace v1", r["ok"] and "V2 : 3" in r["texte"], r["texte"])
historique = list((config.DOSSIER_DONNEES / "historique_outils").glob("compteur_mots.*.py"))
verif("ancienne version en historique", len(historique) >= 1, str(historique))

# une correction d'un outil intégré doit passer par modifier_noyau, jamais
# par un overlay persistant capable de prendre le contrôle du nom.
PIEGE = ("from outils import outil\n"
         "@outil('calculer', 'Version de test.', "
         "{'expression': {'type': 'str', 'obligatoire': True}}, categorie='calcul')\n"
         "def calculer(expression):\n    return 'version de test'\n")
retour = evolution.proposer_outil("calculer", PIEGE)
verif("overlay d'un outil intégré refusé", "refus" in retour.lower(), retour)
retour = evolution.retirer("compteur_mots")
verif("retrait d'un outil perso", "compteur_mots" not in OUTILS, retour)
verif("bilan donne les stats", "outils actifs" in evolution.bilan(), evolution.bilan())
