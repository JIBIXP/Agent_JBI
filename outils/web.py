"""Outils web de JIBI 2 : recherche et lecture de pages.

Recherche : Tavily si TAVILY_API_KEY est renseignée dans le .env (résultats
plus fiables, pensés pour un agent IA) ; repli automatique sur DuckDuckGo
(gratuit, sans clé) si la clé est absente ou si Tavily échoue.
"""
from __future__ import annotations

import html as module_html
import json
import re
import urllib.parse
import urllib.request

from jibi2 import config
from outils import outil

ENTETES = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JIBI2/2.0"}
MAX_PAGE = 4000

# Le bloc d'attributs de la balise <a> est capturé en entier (sans supposer
# l'ordre class/href) puis l'attribut href en est extrait séparément —
# ça évite de casser si DuckDuckGo change l'ordre des attributs HTML.
#
# Titres et extraits sont capturés par DEUX regex séparées (plutôt qu'une
# seule regex avec deux ".*?" en DOTALL reliés par un span libre) puis
# associés par position : un span libre entre deux groupes non-gourmands
# peut provoquer un backtracking en cascade sur une page adverse ou mal
# formée (temps d'exécution non linéaire) — le séparer en deux passes
# indépendantes reste linéaire dans tous les cas.
TITRE_DDG = re.compile(r'<a\s+([^>]*\bclass="result__a"[^>]*)>(.*?)</a>', re.DOTALL)
EXTRAIT_DDG = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
HREF_ATTR = re.compile(r'href="([^"]*)"')
BALISE_HTML = re.compile(r"<[^>]+>")


def _get(url: str, timeout: int = 12) -> str:
    requete = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        return reponse.read().decode("utf-8", errors="replace")


def _rechercher_tavily(requete: str, nombre: int) -> str | None:
    """Cherche via l'API Tavily. Renvoie None si pas de clé ou en cas d'échec
    (pour laisser rechercher_web() basculer sur DuckDuckGo)."""
    cle = config.valeur("TAVILY_API_KEY", "")
    if not cle:
        return None
    corps = json.dumps({
        "api_key": cle,
        "query": requete,
        "max_results": max(1, min(int(nombre), 8)),
    }).encode("utf-8")
    requete_http = urllib.request.Request(
        "https://api.tavily.com/search",
        data=corps,
        headers={**ENTETES, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete_http, timeout=12) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    resultats = donnees.get("results") or []
    if not resultats:
        return None
    lignes = []
    for r in resultats:
        titre = (r.get("title") or "").strip()
        lien = (r.get("url") or "").strip()
        extrait = (r.get("content") or "").strip()[:220]
        lignes.append(f"{len(lignes) + 1}. {titre}\n   {lien}\n   {extrait}")
    return "\n".join(lignes)


def _rechercher_duckduckgo(requete: str, nombre: int) -> str:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(requete)
    try:
        page = _get(url)
    except Exception as e:
        return f"La recherche web a échoué (connexion ?) : {e}"
    limite = max(1, min(int(nombre), 8))
    titres = TITRE_DDG.findall(page)
    extraits = EXTRAIT_DDG.findall(page)
    lignes = []
    for i, (attrs, titre) in enumerate(titres):
        href = HREF_ATTR.search(attrs)
        if not href:
            continue
        lien = href.group(1)
        titre = module_html.unescape(BALISE_HTML.sub("", titre)).strip()
        extrait_html = extraits[i] if i < len(extraits) else ""
        extrait = module_html.unescape(BALISE_HTML.sub("", extrait_html)).strip()[:220]
        if "uddg=" in lien:
            lien = urllib.parse.unquote(lien.split("uddg=")[1].split("&")[0])
        lignes.append(f"{len(lignes) + 1}. {titre}\n   {lien}\n   {extrait}")
        if len(lignes) >= limite:
            break
    if not lignes:
        return "Aucun résultat trouvé (ou la page a changé de format)."
    return "\n".join(lignes)


@outil("rechercher_web",
       "Cherche sur le web (Tavily si configuré, sinon DuckDuckGo) et renvoie "
       "titres, liens et extraits.",
       {"requete": {"type": "str", "obligatoire": True, "description": "ce qu'il faut chercher"},
        "nombre": {"type": "int", "obligatoire": False, "description": "nombre de résultats (défaut 5)"}},
       categorie="web", exemple='{"outil": "rechercher_web", "parametres": {"requete": "météo Rennes"}}')
def rechercher_web(requete: str, nombre: int = 5) -> str:
    resultat = _rechercher_tavily(requete, nombre)
    if resultat is not None:
        return resultat
    return _rechercher_duckduckgo(requete, nombre)


@outil("lire_page_web", "Lit le texte d'une page web (sans les images ni la mise en page).",
       {"url": {"type": "str", "obligatoire": True, "description": "adresse de la page"}},
       categorie="web", risque="moyen")
def lire_page_web(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        page = _get(url, timeout=15)
    except Exception as e:
        return f"Impossible de lire la page : {e}"
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.DOTALL | re.IGNORECASE)
    page = BALISE_HTML.sub(" ", page)
    page = module_html.unescape(page)
    page = re.sub(r"[ \t\r\f\v]+", " ", page)
    page = re.sub(r"\n\s*\n+", "\n", page).strip()
    if not page:
        return "La page ne contient pas de texte lisible."
    if len(page) > MAX_PAGE:
        page = page[:MAX_PAGE] + f"… (tronqué, {len(page)} caractères au total)"
    return page