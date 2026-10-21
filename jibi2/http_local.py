"""Diriger une requête vers un serveur local (panneau web, MCP).

Vérifier si une requête provenant du projet lui-même est VRAIMENT locale.
Être lié sur 127.0.0.1 ne suffit pas : n'importe quelle page web ouverte
dans le navigateur peut émettre des requêtes vers localhost. Quatre
contrôles, tous nécessaires :

1. l'adresse IP de la socket est 127.0.0.1 ou ::1 — adresse non falsifiable,
   refuse tout accès venant d'une autre machine (réseau local, tunnel...) ;
2. l'en-tête ``Host`` désigne la machine — bloque le DNS rebinding : un
   site web qui fait pointer son propre domaine vers 127.0.0.1 pour
   piloter les pages locales depuis le navigateur de l'utilisateur ;
3. aucun en-tête ``X-Forwarded-*`` : un tunnel (ngrok, cloudflared) les
   ajoute ; son trafic doit être refusé même s'il arrive sur la boucle ;
4. pour les écritures (POST), l'``Origin`` éventuelle doit être locale :
   c'est ce qui bloque le CSRF, du JavaScript tiers qui POSTe vers 127.0.0.1.

Pur Python standard, aucune dépendance extérieure : importable depuis
n'importe quel serveur du projet.
"""
from __future__ import annotations

from urllib.parse import urlsplit

#: Aucune : les quatre contrôles sont indépendants.
ADRESSES_LOCALES = {"127.0.0.1", "::1"}


def _sans_port(brut: str) -> str:
    """Retire le port d'un nom d'hôte : `127.0.0.1:8756` -> `127.0.0.1`,
    `[::1]:8756` -> `::1`."""
    brut = brut.strip().lower()
    if brut.startswith("["):                       # IPv6 littéral
        fin = brut.find("]")
        return brut[1:fin] if fin >= 0 else brut
    if brut.count(":") == 1:                       # `hote:port`
        return brut.rsplit(":", 1)[0]
    return brut


def host_local(host: str) -> bool:
    """L'en-tête Host désigne-t-il la machine (et pas un domaine qui y pointerait) ?"""
    return _sans_port(host or "") in ADRESSES_LOCALES


def origin_locale(origin: str) -> bool:
    """Origin absente (client local, curl, Claude Desktop...) -> True.
    Origin présente et non locale -> False : requête CSRF, refusée."""
    origin = (origin or "").strip()
    if not origin:                                 # aucun outil de navigateur tiers
        return True
    try:
        morceaux = urlsplit(origin)
    except ValueError:
        return False
    return (morceaux.scheme in ("http", "https")
            and _sans_port(morceaux.netloc or "") in ADRESSES_LOCALES)


def requete_locale(client_ip: str, entetes) -> tuple[bool, str]:
    """Requête vraiment locale ? (panneau web, MCP HTTP...)

    ``client_ip`` : IP de la socket — côté http.server,
    ``self.client_address[0]``. ``entetes`` : les en-têtes de la requête
    (tout objet munis d'un ``.get()`` insensible à la casse).
    """
    if not host_local(entetes.get("Host", "")):
        return False, "Host non local : rebinding DNS refusé."
    if any(entetes.get(cle) for cle in
           ("X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto")):
        return False, "X-Forwarded-* présent : tunnel refusé."
    ip = (client_ip or "").strip().lower()
    if ip.startswith("::ffff:"):                   # socket IPv6→v4 mappée
        ip = ip[len("::ffff:"):]
    if ip not in ADRESSES_LOCALES:
        return False, "Requête venue d'une autre machine — refusée."
    return True, ""


def origin_interdite(entetes) -> bool:
    """True <=> requête en écriture avec une Origin non locale (CSRF)."""
    return not origin_locale(entetes.get("Origin", ""))
