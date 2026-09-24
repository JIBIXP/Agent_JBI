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


def _analyser_fichier_image(chemin, question: str) -> str:
    """Prépare une image de l'espace de travail pour le modèle visuel."""
    from PIL import Image
    prompt = question.strip() or "Décris brièvement cette image, en français."
    try:
        with Image.open(chemin) as image:
            image.thumbnail((1024, 1024))
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            tampon = io.BytesIO()
            image.save(tampon, format="JPEG", quality=75)
    except Exception as e:  # noqa: BLE001
        return f"Image illisible : {e}"
    return _analyser(tampon.getvalue(), prompt)


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


@outil("voir_image",
       "Observe une image téléchargée dans donnees/fichiers et répond à une question "
       "sur son contenu avec le modèle de vision local. Utilise telecharger_image_web "
       "pour une image trouvée sur le web.",
       {"chemin": {"type": "str", "obligatoire": True,
                   "description": "nom de l'image dans donnees/fichiers"},
        "question": {"type": "str", "obligatoire": False,
                     "description": "question ou description demandée"}},
       categorie="vision", risque="moyen",
       exemple='{"outil": "voir_image", "parametres": {"chemin": "image.jpg", "question": "qu\'y a-t-il ?"}}')
def voir_image(chemin: str, question: str = "") -> str:
    from outils.fichiers import _chemin_espace
    try:
        cible = _chemin_espace(chemin)
    except ValueError as e:
        return str(e)
    if not cible.is_file():
        return f"Image introuvable dans l'espace de travail : {chemin}"
    if cible.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return "Le fichier n'est pas une image reconnue."
    return _analyser_fichier_image(cible, question)
