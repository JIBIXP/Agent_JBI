# -*- coding: utf-8 -*-
"""Section 13 — laboratoire (bac à sable, integrité) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 13. Laboratoire (bac à sable, risque, intégrité, changelog)
from jibi2 import labo  # noqa: E402

CODE_RISQUE_FAIBLE = "from outils import outil\n@outil('a', 'A.', {}, categorie='divers')\ndef a():\n    return 1\n"
verif("évaluation de risque (faible)",
      labo.evaluer_risque(CODE_RISQUE_FAIBLE)[0] == "faible", str(labo.evaluer_risque(CODE_RISQUE_FAIBLE)))
verif("évaluation de risque (élevé)",
      labo.evaluer_risque("import subprocess\nx = 1\n")[0] == "eleve")
CODE_AUTONOME_SUR = ("from outils import outil\n"
                    "@outil('autonome_sur', 'A.', {}, categorie='divers')\n"
                    "def autonome_sur():\n    return 1\n")
verif("autonomie : code pur accepté par la politique",
      labo.analyser_code_autonome(CODE_AUTONOME_SUR, "autonome_sur")[0])
verif("autonomie : import fichier/réseau refusé",
      not labo.analyser_code_autonome(
          "from pathlib import Path\n" + CODE_AUTONOME_SUR, "autonome_sur")[0])
verif("autonomie : eval/exec refusés",
      not labo.analyser_code_autonome(
          "from outils import outil\n@outil('autonome_sur', 'A.', {})\n"
          "def autonome_sur():\n    return eval('1')\n", "autonome_sur")[0])
CODE_SYNTAX_CASSÉE = ("from outils import outil\n"
                      "@outil('outil_casse', 'Cassé.', {}, categorie='divers')\n"
                      "def outil_casse(:\n    return 1\n")
retour = evolution.proposer_outil("outil_casse", CODE_SYNTAX_CASSÉE)
verif("proposition à erreur de syntaxe acceptée au dépôt", "enregistrée" in retour, retour)
verdict = labo.tester_proposition("outil_casse")
verif("bac à sable rejette l'erreur de syntaxe",
      not verdict["ok"] and "SYNTAXE" in verdict["resume"], verdict["resume"])
BON = ("from outils import outil\n"
       "@outil('ajoute_deux', 'Ajoute 2.', "
       "{'nombre': {'type': 'int', 'obligatoire': True}}, categorie='calcul')\n"
       "def ajoute_deux(nombre):\n    return nombre + 2\n")
retour = evolution.proposer_outil("ajoute_deux", BON)
verif("bonne proposition enregistrée avec risque", "risque faible" in retour, retour)
verdict = labo.tester_proposition("ajoute_deux")
verif("bac à sable valide le bon outil",
      verdict["ok"] and "risque faible" in verdict["resume"], verdict["resume"])
# intégrité : on trafique le fichier après test → validation refusée
chemin = config.DOSSIER_PROPOSITIONS / "ajoute_deux.py"
chemin.write_text(chemin.read_text(encoding="utf-8") + "\n# trafiqué\n", encoding="utf-8")
retour = evolution.valider("ajoute_deux")
verif("fichier trafiqué → validation refusée (SHA-256)", "CHANGÉ" in retour, retour)
# version propre re-testée puis validée → outil actif + changelog
evolution.proposer_outil("ajoute_deux", BON)
labo.tester_proposition("ajoute_deux")
retour = evolution.valider("ajoute_deux")
verif("validation après test OK", "activé" in retour and "Test bac à sable" in retour, retour)
r = executer("ajoute_deux", {"nombre": 5}, Garde(lambda n, d: False))
verif("outil validé fonctionne", r["ok"] and "7" in r["texte"], r["texte"])
changelog = evolution.CHANGELOG
verif("CHANGELOG tenu à jour", changelog.exists() and "ajoute_deux" in changelog.read_text(encoding="utf-8"))
perso_aj = Path(__file__).resolve().parent.parent / "outils" / "perso" / "ajoute_deux.py"
perso_aj.unlink(missing_ok=True)
OUTILS.pop("ajoute_deux", None)
# risque élevé refusé dès la proposition
MAUVAIS = "import subprocess\n" + ("x = 1\n" * 50)
retour = evolution.proposer_outil("trop_lourd", MAUVAIS)
verif("risque élevé refusé à la proposition", "refusée" in retour, retour)
# lancement de la suite interne (sur un mini-script, pas récursif)
evolution_ch = Path(tempfile.gettempdir()) / "mini_verif.py"
evolution_ch.write_text("print('1/1 OK')\n", encoding="utf-8")
import subprocess as _sub  # noqa: E402

fait = _sub.run([sys.executable, str(evolution_ch)], capture_output=True, text=True)
verif("lancer_verification : sous-processus OK", fait.returncode == 0 and "1/1" in fait.stdout)
