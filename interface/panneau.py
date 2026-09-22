"""Panneau web local de JIBI — inspiré du panneau de Jarvis.

Un petit serveur HTTP qui tourne sur le PC (127.0.0.1 UNIQUEMENT — comme
chez Jarvis : jamais accessible depuis le réseau) et sert une page web
pour discuter avec JIBI au clavier, voir son état, avec des raccourcis.
C'est le fichier panneau.html qui est servi : aucun CDN, aucun appel
extérieur, ça marche hors ligne.

Démarré automatiquement par run.py ; « ouvre le panneau » lance le
navigateur dessus. Port réglable : JIBI_PANNEAU_PORT dans le .env.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).parent / "panneau.html"

SERVEUR: ThreadingHTTPServer | None = None
_ASSISTANT = None
_VERROU = threading.Lock()          # un message à la fois (histoire partagée)


def definir_assistant(assistant) -> None:
    global _ASSISTANT
    _ASSISTANT = assistant


def _assurer_assistant():
    global _ASSISTANT
    if _ASSISTANT is None:
        from jibi2.assistant import Assistant
        from jibi2.memoire import Memoire
        from jibi2.securite import Garde
        _ASSISTANT = Assistant(Memoire(), Garde())
    return _ASSISTANT


def demarrer(assistant=None, port: int | None = None) -> int:
    """Démarre le serveur local (idempotent). Renvoie le port effectif."""
    global SERVEUR
    if assistant is not None:
        definir_assistant(assistant)
    if SERVEUR is not None:
        return SERVEUR.server_address[1]
    if port is None:
        from jibi2 import config
        try:
            port = int(str(config.valeur("JIBI_PANNEAU_PORT", "8756")).strip() or 8756)
        except ValueError:
            port = 8756
    _assurer_assistant()
    SERVEUR = ThreadingHTTPServer(("127.0.0.1", port), _Gestionnaire)
    threading.Thread(target=SERVEUR.serve_forever, daemon=True).start()
    return SERVEUR.server_address[1]


def arreter() -> None:
    global SERVEUR
    if SERVEUR is not None:
        SERVEUR.shutdown()
        SERVEUR.server_close()
        SERVEUR = None


def port() -> int:
    return SERVEUR.server_address[1] if SERVEUR is not None else 0


def _page_html() -> bytes:
    """Page du panneau, avec la surcharge de design si l'utilisateur (ou
    JIBI lui-même) a personnalisé les couleurs (donnees/design.json)."""
    try:
        page = PAGE.read_text(encoding="utf-8")
    except OSError:
        return (b"<html><body><h1>JIBI</h1><p>panneau.html introuvable</p>"
                b"</body></html>")
    from outils.design import style_panneau
    surcharge = style_panneau()
    if surcharge:
        page = page.replace("</head>", surcharge + "</head>", 1)
    return page.encode("utf-8")


class _Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _json(self, objet: dict, code: int = 200) -> None:
        brut = json.dumps(objet, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(brut)))
        self.end_headers()
        self.wfile.write(brut)

    def do_GET(self) -> None:
        if self.path in ("/", "/panneau"):
            brut = _page_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)
        elif self.path == "/api/etat":
            a = _ASSISTANT
            import datetime
            etat = {
                "heure": datetime.datetime.now().strftime("%H:%M"),
                "outils": 0, "modele": "?", "ollama": False, "session": 0,
            }
            if a is not None:
                import contextlib
                with contextlib.suppress(Exception):
                    etat.update({
                        "outils": len(_lister_outils()),
                        "modele": getattr(a.client, "modele", "?"),
                        "ollama": bool(a.client.disponible()),
                        "session": a.memoire.session_courante() or 0,
                    })
            self._json(etat)
        else:
            self._json({"erreur": "introuvable"}, 404)

    def do_POST(self) -> None:
        if self.path != "/api/message":
            self._json({"erreur": "introuvable"}, 404)
            return
        try:
            taille = int(self.headers.get("Content-Length", 0) or 0)
            donnees = json.loads(self.rfile.read(taille) or b"{}")
            texte = str(donnees.get("texte", "")).strip()
            if not texte:
                self._json({"reponse": "Dis-moi quelque chose d'abord 🙂", "actions": []})
                return
            with _VERROU:                      # un échange à la fois
                resultat = _assurer_assistant().repondre(texte)
            self._json({"reponse": resultat.get("reponse", ""),
                        "actions": resultat.get("actions", [])})
        except Exception as e:  # noqa: BLE001
            self._json({"reponse": f"Oups, j'ai échoué : {str(e)[:120]}", "actions": []}, 500)


def _lister_outils() -> list[str]:
    from outils import lister_noms
    return lister_noms()
