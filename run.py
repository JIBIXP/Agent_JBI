#!/usr/bin/env python3
"""JIBI 2 — point d'entrée unique.

  python run.py            → mode Jarvis : grand tableau de bord plein écran
                             dans Chrome (kiosque), plus de fenêtre Tkinter
  python run.py --bureau   → ancienne fenêtre de bureau (Tkinter)
  python run.py --console  → console (les confirmations se font au clavier)
  python run.py --console --voix       → console + JIBI parle
  python run.py --mains-libres         → « jibi, … » au micro
  python run.py --sans-confirmation    → ne jamais demander confirmation (dangereux)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jibi2 import config


def lancer_mcp() -> None:
    """Lance le serveur MCP de JIBI en arrière-plan.

    Le serveur écoute sur 127.0.0.1:8080.
    Tout agent compatible MCP (Hermes, etc.) peut s'y connecter.
    Zéro accès internet requis.
    """
    try:
        from mcp_server import MCPServer
        import json
        import asyncio

        port = 8080
        import http.server

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/tools"):
                    s = MCPServer(port)
                    tools = s.get_tools()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tools": tools}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                request = json.loads(body)
                s = MCPServer(port)
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(s.handle_request(request))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def log_message(self, format, *args):
                # Volontairement vide (SonarQube S1186) : on écrase le logging
                # par défaut de http.server — un serveur MCP local qui reçoit
                # des requêtes de polling ne doit pas noyer la console JIBI.
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        print(f"🔌 MCP JIBI actif sur http://127.0.0.1:{port}")
    except Exception as e:
        print(f"(MCP serveur non démarré : {e})")


def _mode_jarvis(port_panneau: int) -> None:
    """Mode Jarvis (défaut) : le grand tableau de bord s'ouvre plein écran
    (kiosque) dans Chrome/Edge ; la fenêtre Tkinter ne s'ouvre plus.

    JIBI continue de tout faire (assistant web, planificateur, autonomie)
    jusqu'à Ctrl+C. Sortir du kiosque : Alt+F4 ferme l'écran ; Ctrl+C arrête
    JIBI. JIBI_JARVIS_FENETRE=1 dans le .env → fenêtre normale (F11 pour
    le plein écran) au lieu du kiosque."""
    import webbrowser
    url = f"http://127.0.0.1:{port_panneau}"
    navigateur = None
    try:
        from outils.applications import _trouver_chrome
        navigateur = _trouver_chrome()
    except Exception:
        navigateur = None
    ouvert = False
    if navigateur:
        commande = [navigateur]
        if not config.valeur_bool("JIBI_JARVIS_FENETRE"):
            commande.append("--kiosk")   # plein écran, sans barre ni onglets
        commande.append(url)
        try:
            subprocess.Popen(commande)
            ouvert = True
        except OSError:
            ouvert = False
    if not ouvert:
        webbrowser.open(url)
        print("(Chrome/Edge introuvables — navigateur par défaut en fenêtre ; "
              "F11 pour le plein écran)")
    print(f"Mode Jarvis : tableau de bord sur {url} — Ctrl+C pour arrêter JIBI.")
    try:
        while True:
            time.sleep(3600)             # les services tournent en threads
    except KeyboardInterrupt:
        print("\nJIBI s'arrête. À bientôt !")
    finally:
        try:
            from interface import panneau
            panneau.arreter()
        except Exception:
            pass


def principal() -> int:
    parseur = argparse.ArgumentParser(description="JIBI 2 — assistant local (Ollama + voix).")
    parseur.add_argument("--console", action="store_true", help="console au lieu de la fenêtre")
    parseur.add_argument("--bureau", action="store_true",
                         help="ancienne fenêtre de bureau (Tkinter) au lieu du mode Jarvis")
    parseur.add_argument("--voix", action="store_true", help="JIBI parle ses réponses")
    parseur.add_argument("--mains-libres", action="store_true", help="boucle micro « jibi, … »")
    parseur.add_argument("--sans-confirmation", action="store_true",
                          help="exécute les actions risquées sans demander (déconseillé)")
    arguments = parseur.parse_args()

    config.preparer_dossiers()
    lancer_mcp()

    from jibi2.assistant import Assistant
    from jibi2.memoire import Memoire
    from jibi2.securite import Garde
    from outils import charger_perso

    charger_perso()
    memoire = Memoire()
    garde = Garde()
    if arguments.sans_confirmation:
        print("Avertissement : --sans-confirmation exécute les commandes risquées sans demander.")
        garde.confirmer = lambda nom, detail: True

    assistant = Assistant(memoire, garde)
    import queue as module_file
    from outils import regler_services
    annonces = module_file.Queue()
    regler_services(assistant=assistant, garde=garde, annonces=annonces)

    # panneau web local (page HTML discutée au clavier, 127.0.0.1 uniquement)
    port_panneau = 0
    module_panneau = None
    try:
        from interface import panneau as module_panneau
        port_panneau = module_panneau.demarrer(assistant)
        print(f"Panneau local : http://127.0.0.1:{port_panneau}")
    except Exception as echec:
        print(f"(panneau web indisponible : {echec})")
    from jibi2.planificateur import demarrer as demarrer_planificateur
    demarrer_planificateur()
    # Boucle continue (vérification périodique tant que JIBI est ouvert)
    from jibi2 import autonomie
    if config.valeur_bool("JIBI_AUTONOMIE_CONTINU"):
        stop_autonomie = threading.Event()
        thread = threading.Thread(
            target=autonomie.boucle_continue,
            args=(assistant, stop_autonomie),
            daemon=True,
        )
        thread.start()
    voix_on = arguments.voix or config.valeur_bool("JIBI_VOIX_ACTIVE")

    if arguments.bureau:
        try:
            from interface.bureau import lancer as lancer_fenetre
            lancer_fenetre(assistant, garde, voix_on=voix_on, annonces=annonces)
        except Exception as e:  # pas d'écran / Tkinter cassé → repli console
            print(f"(fenêtre indisponible : {e} — passage en console)")
            from interface.terminal import lancer
            lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    elif arguments.mains_libres:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, mains_libres=True,
               annonces=annonces)
    elif arguments.console:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    else:
        # Mode Jarvis (défaut) : le tableau de bord EST l'interface. L'avis
        # humain sur les actions risquées passe par la boîte du navigateur.
        if port_panneau:
            if not arguments.sans_confirmation:
                module_panneau.brancher_garde(garde)
            _mode_jarvis(port_panneau)
        else:
            # Aucun panneau : repli console (le terminal pose les questions).
            print("(panneau indisponible → repli console)")
            from interface.terminal import lancer
            lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
