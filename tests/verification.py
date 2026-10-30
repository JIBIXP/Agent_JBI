#!/usr/bin/env python3
"""Vérification hors-ligne de JIBI 2 : tout ce qui ne demande ni Ollama ni micro.

  python tests/verification.py    → compte les ✅ et les ❌ (exit 1 si ❌)

La suite est découpée en modules tests/mNN_*.py — chaque module est aussi
lancable tout seul (python -X utf8 tests/m13_streaming.py). Le préludé
(environnement, importations, verif/stats) vit dans tests/moteur.py. Ce
fichier n'est plus que le fil d'exécution : les modules sont importés ici
dans l'ordre historique et chaque section affiche ses résultats à
l'importation, exactement comme le grand script unique d'avant.
"""
from __future__ import annotations

import moteur

import m01_outils_enregistres
import m02_calcul
import m03_fichiers_espace
import m04_secrets
import m05_risque_eleve
import m06_niveaux_n
import m07_memoire_sqlite
import m08_protocole_json
import m09_assistant_repli
import m10_amelioration_outils
import m11_auto_amelioration
import m12_workflows
import m13_streaming
import m14_protocole_non_diffuse
import m15_laboratoire
import m16_workflows_horaires
import m17_analyse_code_projet
import m18_wake_repli
import m19_reprise_session
import m20_dictee
import m21_wake_officiel
import m22_documents
import m23_chrome_binaires
import m24_notifications
import m25_keep_alive
import m26_outils_adaptatifs
import m27_chrome_amaran
import m28_web_ssr
import m29_panneau_jeux_souris
import m30_attaques_http_mcp
import m31_suite_jeux_souris
import m32_voie_rapide
import m33_version_maj
import m34_design_autonomie
import m35_voix
import m36_vitesse_cpu
import m37_bench_env
import m38_chaine_web_amelioration
import m39_outillage
import m40_fuites

print("────────────────────────────────────────────────")
print(f"{moteur.stats['ok']}/{moteur.stats['ok'] + moteur.stats['ko']} OK")


if __name__ == "__main__":
    raise SystemExit(1 if moteur.stats["ko"] else 0)


def test_complet():
    """Compatibilité pytest : la suite ne doit compter aucun échec."""
    assert moteur.stats["ko"] == 0, f"{moteur.stats['ko']} contrôle(s) en échec"
