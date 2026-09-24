"""Localisation approximative et recherche de lieux proches.

La localisation utilise l'estimation publique fournie par l'adresse de
connexion (IP). Ce n'est pas un GPS et l'adresse IP n'est pas conservée par
JIBI. L'utilisateur peut désactiver la fonction dans le .env.
"""
from __future__ import annotations

import json

from outils import outil

URL_IPAPI = "https://ipapi.co/json/"


def _active() -> bool:
    from jibi2 import config
    return config.valeur_bool("JIBI_GEOLOCATION")


def _position() -> dict:
    if not _active():
        raise PermissionError("La géolocalisation est désactivée (JIBI_GEOLOCATION=0).")
    from outils.web import _get
    brut = _get(URL_IPAPI, timeout=8, public_seulement=True)
    donnees = json.loads(brut)
    if donnees.get("error"):
        raise RuntimeError(str(donnees.get("reason", "estimation indisponible")))
    # Ne conserve que les champs nécessaires à l'affichage et à la recherche.
    return {cle: donnees.get(cle) for cle in
            ("city", "region", "country_name", "latitude", "longitude", "timezone")}


@outil("localisation_approchee",
       "Donne une localisation approximative (ville, région, pays) basée sur la "
       "connexion réseau. Ce n'est pas un GPS précis et aucune adresse IP n'est stockée.",
       {}, categorie="web", risque="moyen",
       exemple='{"outil": "localisation_approchee", "parametres": {}}')
def localisation_approchee() -> str:
    try:
        p = _position()
    except PermissionError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001
        return f"Localisation indisponible : {str(e)[:180]}"
    if not p.get("city"):
        return "Localisation approximative indisponible."
    return (f"Position approximative : {p.get('city')}, {p.get('region', '')} "
            f"({p.get('country_name', '')}). Fuseau : {p.get('timezone', '?')}.")


@outil("rechercher_pres",
       "Cherche des lieux ou services près d'un endroit. Si le lieu est vide, "
       "utilise la ville estimée par la connexion réseau.",
       {"requete": {"type": "str", "obligatoire": True,
                    "description": "restaurant, pharmacie, garage..."},
        "lieu": {"type": "str", "obligatoire": False,
                  "description": "ville ou quartier ; vide = position approximative"},
        "ouvrir_chrome": {"type": "bool", "obligatoire": False,
                           "description": "ouvrir aussi la recherche dans ChromeJIBI"}},
       categorie="web", risque="faible",
       exemple='{"outil": "rechercher_pres", "parametres": {"requete": "restaurant", "lieu": "Rennes"}}')
def rechercher_pres(requete: str, lieu: str = "", ouvrir_chrome: bool = False) -> str:
    if not (requete or "").strip():
        return "Dis-moi ce que tu veux chercher près de toi."
    if lieu.strip():
        endroit = lieu.strip()
    else:
        try:
            p = _position()
            endroit = ", ".join(str(p.get(k, "")) for k in ("city", "country_name") if p.get(k))
        except Exception as e:  # noqa: BLE001
            return f"Impossible de déterminer ta ville : {str(e)[:150]}. Precise un lieu."
    from outils.web import rechercher_web
    query = f"{requete.strip()} près de {endroit}"
    resultat = rechercher_web(query, 5)
    if ouvrir_chrome:
        from outils.chrome import chercher_dans_chrome
        chercher_dans_chrome(query)
    return f"Recherche de « {requete.strip()} » près de {endroit} :\n{resultat}"
