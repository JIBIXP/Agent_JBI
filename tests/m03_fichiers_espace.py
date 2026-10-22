# -*- coding: utf-8 -*-
"""Section 3 — fichiers (espace de travail) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 3. Fichiers (espace de travail)
r = executer("ecrire_fichier", {"nom": "essai.txt", "contenu": "bonjour JIBI"}, Garde(lambda n, d: False))
verif("ecrire_fichier", r["ok"], r["texte"])
r = executer("lire_fichier", {"nom": "essai.txt"}, Garde(lambda n, d: False))
verif("lire_fichier", r["ok"] and "bonjour JIBI" in r["texte"], r["texte"])
r = executer("ecrire_fichier", {"nom": "../sortie.txt", "contenu": "x"}, Garde(lambda n, d: False))
verif("évasion de dossier refusée", not r["ok"], r["texte"])
r = executer("chercher_fichier", {"mot": "essai"}, Garde(lambda n, d: False))
verif("chercher_fichier", r["ok"] and "essai" in r["texte"])
r = executer("supprimer_fichier", {"nom": "essai.txt"}, Garde(lambda n, d: False))
verif("supprimer_fichier → corbeille", r["ok"] and "corbeille" in r["texte"])

# export contrôlé vers un dossier externe temporaire
from outils import fichiers as _fichiers  # noqa: E402
_source_export = config.DOSSIER_FICHIERS / "export_test.txt"
_source_export.write_text("JIBI", encoding="utf-8")
_destination_export = Path(tempfile.gettempdir()) / "jibi_export_verification"
_destination_export.mkdir(exist_ok=True)
_garde_export = Garde(lambda _n, _d: True)
r = executer("copier_document", {"nom": _source_export.name,
                                  "destination": str(_destination_export)}, _garde_export)
verif("copier document vers un dossier choisi", r["ok"]
      and (_destination_export / _source_export.name).is_file(), r["texte"])
r = executer("copier_document", {"nom": _source_export.name,
                                  "destination": str(_destination_export)}, _garde_export)
verif("copie export sans écrasement", r["ok"]
      and (_destination_export / "export_test (1).txt").is_file(), r["texte"])
r = executer("copier_document", {"nom": _source_export.name,
                                  "destination": str(config.DOSSIER_FICHIERS)}, _garde_export)
verif("destination protégée refusée", not r["ok"], r["texte"])
_source_export.unlink(missing_ok=True)
for _nom in ("export_test.txt", "export_test (1).txt"):
    (_destination_export / _nom).unlink(missing_ok=True)
_destination_export.rmdir()
