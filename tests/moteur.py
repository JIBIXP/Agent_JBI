#!/usr/bin/env python3
"""Vérification hors-ligne de JIBI 2 : tout ce qui ne demande ni Ollama ni micro.

  python tests/verification.py    → compte les ✅ et les ❌ (exit 1 si ❌)
"""
from __future__ import annotations

import json as _json
import sys
import tempfile
from pathlib import Path

for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

os.environ["CONFIRMER_RISQUES"] = "1"
os.environ["JIBI_MODIFICATION_AUTO"] = "1"  # autonomie explicitement accordée par l'utilisateur
os.environ["JIBI_AUTONOMIE_NOYAU"] = "0"     # le noyau reste soumis à confirmation
os.environ["JIBI_GEOLOCATION"] = "1"

from jibi2 import config, evolution, llm, memoire

config.preparer_dossiers()

# Les tests n'ecrivent jamais dans le vrai CHANGELOG du projet :
# le journal des evolutions est redirige vers un fichier temporaire.
_dossier_changelog = tempfile.mkdtemp(prefix="jibi_changelog_")
evolution.CHANGELOG = Path(_dossier_changelog) / "CHANGELOG.md"
from jibi2.assistant import (Assistant, _demande_cours, _demande_dessin,
                             _demande_tableau, _extraire_json)
from jibi2.securite import Garde
from outils import OUTILS, executer

stats = {"ok": 0, "ko": 0}


def verif(nom: str, condition: bool, detail: str = "") -> None:
    if condition:
        stats["ok"] += 1
        print(f"  ✅ {nom}")
    else:
        stats["ko"] += 1
        print(f"  ❌ {nom} {detail}")


print("── JIBI 2, vérification hors-ligne ─────────────")


# ── Partages entre sections ─────────────────────────────────────────────
# Ces noms sont définis ou importés dans une section et réutilisés dans une
# autre : ils sont centralisés ici pour le découpage. Quand une section
# ré-importe elle-même l'objet, elle lie exactement le même objet :
# aucun changement de comportement. Les deux classes factices servent aux
# sections panneau/jeux (m29) et attaques HTTP/MCP (m30).
from outils import fichiers as _fichiers          # m04 (§3bis)
from outils import regler_services, workflows     # m12 (§10), m16 (§14)
from outils.jeux import (                         # m29 (§27), m31 (suite jeux)
    lancer_un_de,
    nombre_mystere,
    pierre_feuille_ciseaux,
    pile_ou_face,
)
from outils.souris import (                       # m29 (§27), m31 (suite jeux)
    _bornes,
    cliquer_souris,
    deplacer_souris,
)
import json as _json26                            # m29 (§27), m30 (§35)
import urllib.error as _uerr26                    # m29 (§27), m30 (§35)
import urllib.request as _ureq26                  # m29 (§27), m30 (§35)
from interface import panneau as module_panneau   # m29 (§27), m30 (§35)


class _ClientFaux:
    modele = "faux-1b"

    def disponible(self):
        return True


class _AssistantFaux:
    client = _ClientFaux()

    class memoire:
        @staticmethod
        def session_courante():
            return 7

    def repondre(self, texte, **options):
        return {"reponse": "écho:" + texte, "actions": []}


# Pont d'état : l'assistant de test est créé par m09 (section 7), réutilisé
# par m14 (section 12) et m36 (section 31) qui publient leur instance
# (`_moteur.assistant = assistant`) et le récupèrent avec ce nom.
assistant = None


def _supprimer_tolerant(chemin: Path) -> None:
    """Supprime un fichier de test, verrou passager inclus.

    Sur les runners CI, l'antivirus tient parfois un fichier (xlsx
    particulièrement) quelques centaines de ms après sa création :
    PermissionError au unlink. On réessaie brièvement ; en dernier
    recours on laisse le fichier (de test, recréé au prochain passage).
    """
    import time as module_temps  # là, pour ne pas alourdir le préludé

    for _essai in range(6):
        try:
            chemin.unlink(missing_ok=True)
            return
        except PermissionError:
            module_temps.sleep(0.3)


__all__ = list(n for n in globals() if not n.startswith("__"))
