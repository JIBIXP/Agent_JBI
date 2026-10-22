# -*- coding: utf-8 -*-
"""Section 3bis — secrets refusés — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 3bis. Secrets : .env, clés privées, coffres, dossier interne -> refusés
_dossier_secret = Path(tempfile.mkdtemp(prefix="jibi_verif_secrets_"))
(_dossier_secret / "id_rsa_banane").write_text("-----BEGIN", encoding="utf-8")
(_dossier_secret / "coffre.kdbx").write_bytes(b"\x03\x00")
(_dossier_secret / "note_publique.txt").write_text("données publiques", encoding="utf-8")
r = executer("lire_fichier_pc", {"chemin": str(_dossier_secret / "id_rsa_banane")},
             Garde(lambda n, d: True))
verif("lire_fichier_pc : clé SSH refusée", not r["ok"] and "Refusé" in r["texte"], r["texte"])
r = executer("lire_fichier_pc", {"chemin": str(_dossier_secret / "coffre.kdbx")},
             Garde(lambda n, d: True))
verif("lire_fichier_pc : coffre .kdbx refusé", not r["ok"] and "Refusé" in r["texte"], r["texte"])
_env_pc = Path.home() / ".env"
r = executer("lire_fichier_pc", {"chemin": str(_env_pc)}, Garde(lambda n, d: True))
verif("lire_fichier_pc : .env refusé (selon chemin)",
      not r["ok"] and "Refusé" in r["texte"], r["texte"])
_donnes_pc = Path(_fichiers.__file__).resolve().parents[1] / "donnees"
r = executer("lire_fichier_pc", {"chemin": str(_donnes_pc / "essai.txt")},
             Garde(lambda n, d: True))
verif("lire_fichier_pc : donnees/ interne refusé", not r["ok"] and "donn" in r["texte"], r["texte"])
r = executer("lire_fichier_pc", {"chemin": str(_dossier_secret / "note_publique.txt")},
             Garde(lambda n, d: True))
verif("lire_fichier_pc : fichier ordinaire toujours lu",
      r["ok"] and "publiques" in r["texte"], r["texte"])
r = executer("ecrire_fichier", {"nom": ".env", "contenu": "CLE=valeur"}, Garde(lambda n, d: False))
verif("ecrire_fichier : .env dans l'espace refusé", not r["ok"], r["texte"])
r = executer("ecrire_fichier", {"nom": "cert.pem", "contenu": "-----"}, Garde(lambda n, d: False))
verif("ecrire_fichier : .pem refusé", not r["ok"], r["texte"])
_racine_donnees = _fichiers._racine_donnees()
verif("_racine_donnees pointe le projet", _racine_donnees.name == "donnees"
      and (_racine_donnees.parent / "jibi2").is_dir(), str(_racine_donnees))
(_dossier_secret / "id_rsa_banane").unlink()
(_dossier_secret / "coffre.kdbx").unlink()
(_dossier_secret / "note_publique.txt").unlink()
_dossier_secret.rmdir()
