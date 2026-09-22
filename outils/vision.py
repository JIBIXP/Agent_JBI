"""Vision d'écran de JIBI 2 — CPU uniquement.

Capture l'écran (Pillow), l'envoie à un modèle de vision léger d'Ollama
(moondream par défaut : ~1,4 Go, conçu pour tourner sur processeur) et
renvoie la description. Rien ne sort du PC.
"""
from __future__ import annotations

import base64
import io
import json
import time
import urllib.request

from jibi2 import config
from outils import outil


def _capturer() -> bytes:
    """Capture l'écran en JPEG (base64 prêt pour Ollama)."""
    from PIL import ImageGrab
    image = ImageGrab.grab()
    image.thumbnail((1024, 1024))
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, format="JPEG", quality=70)
    return tampon.getvalue()


def _analyser(image_jpeg: bytes, prompt: str) -> str:
    modele = config.valeur("JIBI_VISION_MODEL", "moondream")
    url = config.valeur("JIBI_LLM_URL", "http://127.0.0.1:11434").rstrip("/")
    corps = {
        "model": modele,
        "messages": [{"role": "user", "content": prompt,
                      "images": [base64.b64encode(image_jpeg).decode("utf-8")]}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2},
    }
    requete = urllib.request.Request(
        f"{url}/api/chat", data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(requete, timeout=300) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (f"Le modèle de vision « {modele} » est introuvable. "
                    f"Télécharge-le une fois :  ollama pull {modele}")
        return f"Ollama a répondu une erreur HTTP {e.code}."
    except Exception as e:
        return f"Analyse impossible (Ollama lancé ?) : {e}"
    return (donnees.get("message") or {}).get("content", "").strip() or "(réponse vide)"


@outil("voir_ecran", "Regarde l'écran du PC (capture d'écran) et répond à une question sur ce qu'il voit. "
                     "Utilise le modèle de vision local léger (moondream).",
       {"question": {"type": "str", "obligatoire": False,
                     "description": "ce qu'il faut regarder/décrire ; vide = décrire l'écran"}},
       categorie="vision", risque="moyen",
       exemple='{"outil": "voir_ecran", "parametres": {"question": "quelle application est ouverte ?"}}')
def voir_ecran(question: str = "") -> str:
    prompt = question.strip() or "Décris brièvement ce que tu vois sur cet écran, en français."
    try:
        image = _capturer()
    except Exception as e:
        return f"Capture d'écran impossible : {e}"
    # garde une copie horodatée
    dossier = config.DOSSIER_DONNEES / "captures"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"ecran_{int(time.time())}.jpg").write_bytes(image)
    return _analyser(image, prompt)
