"""Outils web de JIBI 2 : recherche et lecture de pages — sans clé d'API."""
from __future__ import annotations

import html as module_html
import re
import urllib.parse
import urllib.request

from outils import outil

ENTETES = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JIBI2/2.0"}
MAX_PAGE = 4000


def _get(url: str, timeout: int = 12) -> str:
    requete = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        return reponse.read().decode("utf-8", errors="replace")


@outil("rechercher_web", "Cherche sur le web (DuckDuckGo) et renvoie titres, liens et extraits.",
       {"requete": {"type": "str", "obligatoire": True, "description": "ce qu'il faut chercher"},
        "nombre": {"type": "int", "obligatoire": False, "description": "nombre de résultats (défaut 5)"}},
       categorie="web", exemple='{"outil": "rechercher_web", "parametres": {"requete": "météo Rennes"}}')
def rechercher_web(requete: str, nombre: int = 5) -> str:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(requete)
    try:
        page = _get(url)
    except Exception as e:
        return f"La recherche web a échoué (connexion ?) : {e}"
    resultats = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
        page, re.DOTALL)
    if not resultats:
        return "Aucun résultat trouvé (ou la page a changé de format)."
    lignes = []
    for lien, titre, extrait in resultats[:max(1, min(int(nombre), 8))]:
        titre = module_html.unescape(re.sub(r"<[^>]+>", "", titre)).strip()
        extrait = module_html.unescape(re.sub(r"<[^>]+>", "", extrait)).strip()[:220]
        if "uddg=" in lien:
            lien = urllib.parse.unquote(lien.split("uddg=")[1].split("&")[0])
        lignes.append(f"{len(lignes) + 1}. {titre}\n   {lien}\n   {extrait}")
    return "\n".join(lignes)


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
    page = re.sub(r"<[^>]+>", " ", page)
    page = module_html.unescape(page)
    page = re.sub(r"[ \t\r\f\v]+", " ", page)
    page = re.sub(r"\n\s*\n+", "\n", page).strip()
    if not page:
        return "La page ne contient pas de texte lisible."
    if len(page) > MAX_PAGE:
        page = page[:MAX_PAGE] + f"… (tronqué, {len(page)} caractères au total)"
    return page
