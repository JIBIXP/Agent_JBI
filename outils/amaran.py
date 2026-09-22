"""Pilotage de la lumière vidéo amaran (Aputure) — 100 % local.

Les amaran (200x, 60x…) n'ont pas d'API officielle : elles parlent en
Bluetooth mesh (app Sidus Link), inutilisable directement depuis le PC.
Le contournement communautaire wesbos/amaran-BLE-control fait tourner un
ESP32 (~5 €) qui rejoint le mesh et expose une petite API HTTP locale.
JIBI se contente d'envoyer des requêtes HTTP à ce pont : aucun cloud,
aucune app propriétaire, réponse instantanée.

À régler une fois (matériel) dans le .env :
    JIBI_AMARAN_URL=http://192.168.1.50:2708

Routes du firmware wesbos (port 2708, à ajuster si le firmware change) :
POST /lights/all/on, /lights/all/off, /lights/all/brightness {value},
/lights/all/cct {brightness,kelvin,gm}, /lights/all/hsi {brightness,hue,saturation}.

Godox TL60 (DMX natif) : hors JIBI pour l'instant — il faudrait une
interface USB-DMX (Enttec-like) ; même Jarvis le laisse « à venir ».
"""
from __future__ import annotations

import json
import urllib.request

from outils import outil


def _pont() -> str | None:
    """URL du pont ESP32, ou None si non configuré."""
    from jibi2 import config
    url = config.valeur("JIBI_AMARAN_URL", "").strip()
    return url.rstrip("/") if url else None


def _post(pont: str, route: str, corps: dict | None = None) -> str:
    donnees = json.dumps(corps or {}).encode("utf-8")
    requete = urllib.request.Request(
        pont + route, data=donnees, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=3) as reponse:
        return reponse.read().decode("utf-8", "replace")[:200]


@outil("controler_amaran",
       "Pilote la lumière vidéo amaran via le pont ESP32 local. Actions : "
       "allumer, eteindre, luminosite (valeur 0-100), kelvin (2500-10000, "
       "blanc chaud/froid), couleur (teinte 0-360 + saturation 0-100). "
       "Demander la valeur de luminosité si l'utilisateur ne la donne pas.",
       parametres={
           "action": {"type": "str", "obligatoire": True,
                      "description": "allumer | eteindre | luminosite | kelvin | couleur"},
           "valeur": {"type": "int", "description": "luminosité en % (0-100, défaut 60)"},
           "kelvin": {"type": "int", "description": "température de couleur 2500-10000 (défaut 5600)"},
           "teinte": {"type": "int", "description": "teinte 0-360 (mode couleur)"},
           "saturation": {"type": "int", "description": "saturation 0-100 (mode couleur, défaut 100)"},
       },
       categorie="domotique", risque="faible",
       exemple="key light à 60 % en 5600 K → action=luminosite, valeur=60, kelvin=5600")
def controler_amaran(action: str = "", valeur: int = 60, kelvin: int = 5600,
                     teinte: int = 0, saturation: int = 100) -> str:
    a = action.strip().lower()
    pont = _pont()
    if pont is None:
        return ("La lumière amaran n'est pas configurée. Une fois (matériel) : "
                "un ESP32 (~5 €) flashé avec amaran-BLE-control, puis "
                "JIBI_AMARAN_URL=http://ip-esp32:2708 dans le .env.")
    try:
        if a in ("allumer", "allume", "on"):
            _post(pont, "/lights/all/on")
            return "Lumière allumée."
        if a in ("eteindre", "eteins", "off"):
            _post(pont, "/lights/all/off")
            return "Lumière éteinte."
        valeur = max(0, min(100, int(valeur)))
        if a in ("luminosite", "brightness"):
            _post(pont, "/lights/all/brightness", {"value": valeur})
            return f"Luminosité réglée à {valeur} %."
        if a in ("kelvin", "blanc", "cct"):
            kelvin = max(2500, min(10000, int(kelvin)))
            _post(pont, "/lights/all/cct", {"brightness": valeur, "kelvin": kelvin, "gm": 0})
            return f"Blanc réglé : {valeur} % à {kelvin} K."
        if a in ("couleur", "hsi", "rgb"):
            teinte = max(0, min(360, int(teinte)))
            saturation = max(0, min(100, int(saturation)))
            _post(pont, "/lights/all/hsi",
                  {"brightness": valeur, "hue": teinte, "saturation": saturation})
            return f"Couleur réglée : teinte {teinte}°, saturation {saturation} %, {valeur} %."
        return "Action inconnue : allumer, eteindre, luminosite, kelvin ou couleur."
    except Exception as e:  # noqa: BLE001 — un outil ne fait jamais planter JIBI
        return (f"Pont amaran injoignable ({str(e)[:100]}). "
                "Vérifie que l'ESP32 est allumé et JIBI_AMARAN_URL dans le .env.")
