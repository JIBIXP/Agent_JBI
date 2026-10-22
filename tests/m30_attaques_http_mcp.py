# -*- coding: utf-8 -*-
"""Section 35 — attaques HTTP + MCP verrouillé — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 35. Être lié sur 127.0.0.1 ne suffit pas : attaques HTTP + MCP verrouillé
import asyncio as asyncio_mod35   # noqa: E402
import socket as _socket35  # noqa: E402
from jibi2 import http_local as _http_local35  # noqa: E402
from interface.panneau import _etat_securite  # noqa: E402


class _Entetes(dict):
    """Headers insensibles à la casse, comme http.client.HTTPMessage."""

    def get(self, cle, defaut=None):
        cle = str(cle).lower()
        for k, v in dict.items(self):
            if str(k).lower() == cle:
                return v
        return defaut


_tete_local = _Entetes({"Host": "127.0.0.1:8756"})
ok_local, raison_local = _http_local35.requete_locale("127.0.0.1", _tete_local)
verif("http_local : requête locale acceptée",
      ok_local and not raison_local, raison_local)
ok, _raison = _http_local35.requete_locale(
    "127.0.0.1", _Entetes({"Host": "mon-domaine.exemple"}))
verif("http_local : DNS rebinding refusé", not ok, _raison)
ok, _raison = _http_local35.requete_locale(
    "127.0.0.1", _Entetes({"Host": "127.0.0.1:8756", "X-Forwarded-For": "1.2.3.4"}))
verif("http_local : tunnel X-Forwarded refusé", not ok, _raison)
ok, _raison = _http_local35.requete_locale(
    "192.168.1.24", _Entetes({"Host": "127.0.0.1:8756"}))
verif("http_local : socket réseau refusée", not ok, _raison)
verif("http_local : CSRF (Origin tierce) interdit",
      _http_local35.origin_interdite(_Entetes({"Origin": "https://mon-domaine.exemple"})))
verif("http_local : Origin locale acceptée",
      not _http_local35.origin_interdite(_Entetes({"Origin": "http://127.0.0.1:8756"})))
verif("http_local : pas d'Origin (client local) acceptée",
      not _http_local35.origin_interdite(_Entetes({})))


def _brute(port: int, requete: str) -> int:
    """Envoie une requête HTTP brute (contrôle total des en-têtes)."""
    with _socket35.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(requete.encode("utf-8"))
        reponse = b""
        try:
            reponse = s.recv(4096)
        except OSError:
            pass
    return int(reponse.split(b" ")[1]) if reponse else 0


_port_secu = module_panneau.demarrer(_AssistantFaux(), port=0)
try:
    _code = _brute(_port_secu, "GET /api/etat HTTP/1.1\r\n"
                   f"Host: mon-domaine.exemple\r\nConnection: close\r\n\r\n")
    verif("panneau : rebinding DNS refusé (403)", _code == 403, str(_code))
    _code = _brute(_port_secu, "GET /api/etat HTTP/1.1\r\n"
                   f"Host: 127.0.0.1:{_port_secu}\r\n"
                   "X-Forwarded-For: 1.2.3.4\r\nConnection: close\r\n\r\n")
    verif("panneau : tunnel X-Forwarded refusé (403)", _code == 403, str(_code))
    _code = _brute(_port_secu, "POST /api/message HTTP/1.1\r\n"
                   f"Host: 127.0.0.1:{_port_secu}\r\n"
                   "Origin: https://mon-domaine.exemple\r\n"
                   f"Content-Length: 21\r\nConnection: close\r\n\r\n"
                   + '{"texte":"salut jibi"}')
    verif("panneau : CSRF (Origin tierce) refusé (403)", _code == 403, str(_code))
    _reponse_secu = _ureq26.urlopen(
        f"http://127.0.0.1:{_port_secu}/api/securite").read()
    _secu = _json26.loads(_reponse_secu)
    # Format tableau de bord : {verrous:[{cle,titre,ok,detail,source}], actifs,
    # total}. Le contrôle vérifie le CONTRAT (lecture en direct, cohérence des
    # compteurs) — pas un .env entièrement verrouillé : les verrous ouverts
    # sciemment (cloud, déplacement auto, auto-modification du noyau…) sont
    # affichés rouges à dessein. Seul « local » ne doit JAMAIS être ouvert.
    _verrous_secu = _secu.get("verrous", [])
    _cles_ok = all({"cle", "titre", "ok", "source"} <= set(v) for v in _verrous_secu)
    _local_ok = all(v.get("ok") for v in _verrous_secu if v.get("cle") == "local")
    verif("panneau : /api/securite lit les verrous en direct",
          len(_verrous_secu) >= 5 and _cles_ok and _local_ok
          and _secu.get("actifs") == sum(1 for v in _verrous_secu if v.get("ok")),
          str(_secu)[:80])
finally:
    module_panneau.arreter()

# MCP : liste blanche, Garde, jeton
import mcp_server as _mcp35  # noqa: E402

verif("mcp : liste blanche ⊆ outils enregistrés et à risque faible",
      set(_mcp35.MCP_EXPOSES) <= {o.nom for o in _mcp35.OUTILS.values()
                                  if o.risque == "faible"},
      str(sorted(_mcp35.MCP_EXPOSES - set(_mcp35.OUTILS))))
verif("mcp : au moins 10 lectures sûres exposées",
      len(_mcp35.outils_exposes()) >= 10, str(len(_mcp35.outils_exposes())))
_serveur_mcp = _mcp35.MCPServer()
verif("mcp : tools/list limité à la liste blanche",
      {t["name"] for t in _serveur_mcp.get_tools()} <= _mcp35.MCP_EXPOSES)
_brut = _serveur_mcp.call_tool("executer_commande", {"commande": "echo x"})
verif("mcp : executer_commande hors liste refusé",
      "non exposé" in _brut, _brut[:80])
# le double contrôle défensif : si un outil à risque moyen finit par être
# ajouté à la liste blanche (une bourde future), l'appel est tout de même
# refusé — le refus ne repose pas que sur la liste.
_mcp35.MCP_EXPOSES.add("ecrire_fichier")
_brut = _serveur_mcp.call_tool("ecrire_fichier", {"nom": "x.txt", "contenu": "x"})
_mcp35.MCP_EXPOSES.discard("ecrire_fichier")
verif("mcp : risque moyen refusé à l'appel même inscrit au blanc",
      "lecture sûre" in _brut, _brut[:80])
_brut = _serveur_mcp.call_tool("lancer_un_de", {})
verif("mcp : lecture sûre passe par la Garde et répond",
      '"result"' in _brut and "faces" in _brut, _brut[:80])
_reponse_mcp = asyncio_mod35.run(_serveur_mcp.handle_request(
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
     "params": {"name": "batterie", "arguments": {}}}))
verif("mcp : protocole JSON-RPC répond avec contenu",
      _reponse_mcp["id"] == 7 and "content" in _reponse_mcp.get("result", {}),
      str(_reponse_mcp)[:80])
_reponse_inconnue = asyncio_mod35.run(_serveur_mcp.handle_request(
    {"jsonrpc": "2.0", "id": 8, "method": "autre/inconnu"}))
verif("mcp : méthode inconnue → erreur -32601",
      _reponse_inconnue["error"]["code"] == -32601)
verif("mcp : jeton présent, jamais vide", bool(_mcp35.jeton()))
verif("mcp : jeton invalide refusé",
      not _mcp35.jeton_valide("") and not _mcp35.jeton_valide("faux-jeton"))
verif("mcp : le bon jeton passe",
      _mcp35.jeton_valide(_mcp35.jeton(creer=False)))
