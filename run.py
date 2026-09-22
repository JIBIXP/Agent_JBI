#!/usr/bin/env python3
"""JIBI 2 — point d'entrée unique.

  python run.py                 → fenêtre de bureau (Tkinter)
  python run.py --console       → console
  python run.py --console --voix          → console + JIBI parle
  python run.py --mains-libres            → « jibi, … » au micro
  python run.py --sans-confirmation       → ne jamais demander confirmation (dangereux)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jibi2 import config


def principal() -> int:
    parseur = argparse.ArgumentParser(description="JIBI 2 — assistant local (Ollama + voix).")
    parseur.add_argument("--console", action="store_true", help="console au lieu de la fenêtre")
    parseur.add_argument("--voix", action="store_true", help="JIBI parle ses réponses")
    parseur.add_argument("--mains-libres", action="store_true", help="boucle micro « jibi, … »")
    parseur.add_argument("--sans-confirmation", action="store_true",
                         help="exécute les actions risquées sans demander (déconseillé)")
    arguments = parseur.parse_args()

    config.preparer_dossiers()

    from jibi2.assistant import Assistant
    from jibi2.memoire import Memoire
    from jibi2.securite import Garde
    from outils import charger_perso

    charger_perso()
    memoire = Memoire()
    garde = Garde()
    if arguments.sans_confirmation:
        print("⚠️  --sans-confirmation : JIBI exécutera les commandes risquées sans te demander.")
        garde.confirmer = lambda nom, detail: True

    assistant = Assistant(memoire, garde)  # les rappels passent par la file « annonces »
    # services partagés : garde, assistant, file d'annonces (rappels, workflows programmés)
    import queue as module_file

    from outils import regler_services
    annonces = module_file.Queue()
    regler_services(assistant=assistant, garde=garde, annonces=annonces)

    # panneau web local (page HTML discutée au clavier, 127.0.0.1 uniquement)
    try:
        from interface import panneau as module_panneau
        numero = module_panneau.demarrer(assistant)
        print(f"🌐 Panneau local : http://127.0.0.1:{numero}")
    except Exception as echec:
        print(f"(panneau web indisponible : {echec})")
    from jibi2.planificateur import demarrer as demarrer_planificateur
    demarrer_planificateur()
    voix_on = arguments.voix or config.valeur_bool("JIBI_VOIX_ACTIVE")

    if arguments.mains_libres:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, mains_libres=True,
               annonces=annonces)
    elif arguments.console:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    else:
        try:
            from interface.bureau import lancer as lancer_fenetre
            lancer_fenetre(assistant, garde, voix_on=voix_on, annonces=annonces)
        except Exception as e:  # pas d'écran / Tkinter cassé → repli console
            print(f"(fenêtre indisponible : {e} — passage en console)")
            from interface.terminal import lancer
            lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
