# -*- coding: utf-8 -*-
"""Section 25 — Chrome CDP factice + pont amaran — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 25. Assistance Chrome (CDP factice) + lumière amaran (pont factice)
import json as _js  # noqa: E402
import socket as _socket  # noqa: E402
import threading as _threading  # noqa: E402
import urllib.parse as _uparse  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402

import outils.amaran as module_amaran  # noqa: E402
import outils.chrome as module_chrome  # noqa: E402

_page_html = "<html><body><h1>Test Godox TL60</h1><p>Le TL60 coute 139 euros.</p></body></html>"
_cdp_onglets: list = []
_capte = {"route": "", "corps": {}}


class _FauxCDP(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _envoyer(self, corps, contenu="application/json"):
        if isinstance(corps, bytes):
            brut = corps
        else:
            brut = (_js.dumps(corps) if not isinstance(corps, str) else corps).encode()
        self.send_response(200)
        self.send_header("Content-Type", contenu)
        self.send_header("Content-Length", str(len(brut)))
        self.end_headers()
        self.wfile.write(brut)

    def do_GET(self):
        if self.path == "/json/version":
            self._envoyer({"Browser": "Chrome/150"})
        elif self.path == "/json/list":
            self._envoyer(_cdp_onglets)
        elif self.path.startswith("/json/activate/"):
            self._envoyer("Target activated", "text/plain")
        elif self.path.startswith("/json/close/"):
            self._envoyer("Target is closing", "text/plain")
        elif self.path.startswith("/page"):
            self._envoyer(_page_html, "text/html; charset=utf-8")
        else:
            self._envoyer({})

    def do_PUT(self):
        if self.path.startswith("/json/new"):
            url = _uparse.unquote(self.path.split("url=", 1)[1])
            self._envoyer({"id": "N9", "type": "page", "title": "Nouvel onglet", "url": url})


class _FauxPont(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        _capte["route"] = self.path
        _capte["corps"] = _js.loads(self.rfile.read(n) or b"{}")
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


_serveur = HTTPServer(("127.0.0.1", 0), _FauxCDP)
_port_cdp = _serveur.server_address[1]
_pont_http = HTTPServer(("127.0.0.1", 0), _FauxPont)
_port_pont = _pont_http.server_address[1]
_cdp_onglets.extend([
    {"id": "A1", "type": "page", "title": "Test du Godox TL60",
     "url": f"http://127.0.0.1:{_port_cdp}/page"},
    {"id": "A2", "type": "page", "title": "Documentation", "url": "https://exemple.fr/docs"},
    {"id": "D1", "type": "page", "title": "DevTools", "url": "devtools://devtools/inspector.html"},
])
for _s in (_serveur, _pont_http):
    _threading.Thread(target=_s.serve_forever, daemon=True).start()

_base_orig, _pont_orig = module_chrome._base, module_amaran._pont
_prise = _socket.socket()
_prise.bind(("127.0.0.1", 0))
_port_mort = _prise.getsockname()[1]
_prise.close()
try:
    module_chrome._base = lambda: f"http://127.0.0.1:{_port_cdp}"
    _liste = module_chrome.lister_onglets()
    verif("onglets listés (devtools filtré)",
          "2 onglet" in _liste and "Documentation" in _liste, _liste.splitlines()[0])
    verif("onglet ouvert via /json/new", "Nouvel onglet" in module_chrome.ouvrir_onglet("youtube.com"))
    verif("compte Google ouvert dans ChromeJIBI",
          "Compte ouvert" in module_chrome.ouvrir_compte_chrome("google"))
    verif("recherche ouverte dans ChromeJIBI",
          "Recherche ChromeJIBI" in module_chrome.chercher_dans_chrome("recettes de pasta"))
    verif("site direct ouvert dans ChromeJIBI",
          "Onglet ouvert" in module_chrome.visiter_site("https://exemple.fr", lire=False))
    verif("onglet activé par mot", "Documentation" in module_chrome.activer_onglet("documentation"))
    verif("onglet fermé par numéro", "fermé" in module_chrome.fermer_onglet("2"))
    _lu = module_chrome.lire_onglet_actif()
    verif("page active lue (texte extrait)",
          _lu.startswith("Onglet actif :") and "TL60" in _lu, _lu[:40])
    module_chrome._base = lambda: f"http://127.0.0.1:{_port_mort}"
    from outils import applications as _applications25
    _chrome_trouver_orig = _applications25._trouver_chrome
    _applications25._trouver_chrome = lambda: None
    try:
        verif("Chrome absent → message clair", "CHROME_JIBI.bat" in module_chrome.lister_onglets())
    finally:
        _applications25._trouver_chrome = _chrome_trouver_orig

    module_amaran._pont = lambda: f"http://127.0.0.1:{_port_pont}"
    verif("amaran allumer → /lights/all/on",
          module_amaran.controler_amaran("allumer") == "Lumière allumée."
          and _capte["route"] == "/lights/all/on")
    module_amaran.controler_amaran("luminosite", valeur=75)
    verif("amaran luminosite → brightness {value}",
          _capte["route"] == "/lights/all/brightness" and _capte["corps"] == {"value": 75})
    module_amaran.controler_amaran("couleur", teinte=200, valeur=80)
    verif("amaran couleur → hsi", _capte["route"] == "/lights/all/hsi" and _capte["corps"]["hue"] == 200)
    verif("amaran action inconnue signalée", "inconnue" in module_amaran.controler_amaran("changer"))
    module_amaran._pont = _pont_orig
    verif("amaran non configuré → mode d'emploi",
          "JIBI_AMARAN_URL" in module_amaran.controler_amaran("allumer"))
    module_amaran._pont = lambda: f"http://127.0.0.1:{_port_mort}"
    verif("amaran injoignable → message clair", "injoignable" in module_amaran.controler_amaran("allumer"))
finally:
    module_chrome._base, module_amaran._pont = _base_orig, _pont_orig
    _serveur.shutdown()
    _serveur.server_close()
    _pont_http.shutdown()
    _pont_http.server_close()
