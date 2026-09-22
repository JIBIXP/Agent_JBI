"""Wake-word neuronal de JIBI 2 — OPTIONNEL, léger sur CPU.

Si le paquet `openwakeword` est installé ET qu'un modèle (.tflite/.onnx)
se trouve dans modeles/wake/, JIBI utilise la détection neuronale : il
n'écoute quasiment rien en permanence et réagit au mot prononcé.
Sinon, repli automatique sur la détection par transcription
(fonctionne partout, déjà active dans mains_libres).

Modèle prêt à l'emploi : `python docteur.py --installer-wake` télécharge
le modèle officiel « hey jarvis » (JIBI réagit à « Hey Jarvis »).
Pour un modèle qui réagit à « jibi » : entraîne-le une fois avec la
recette openWakeWord (génération TTS + entraînement, ~30 min sur Colab)
puis dépose le .onnx obtenu dans modeles/wake/.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from jibi2 import config

_modele = None

# Modèles officiels openWakeWord prêts à l'emploi (format .onnx : onnxruntime
# est déjà installé avec piper-tts, rien de plus à ajouter).
MODELES_OFFICIELS = {
    "jarvis": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx",
}


def telecharger(nom: str = "jarvis") -> str:
    """Télécharge un modèle wake officiel dans modeles/wake/."""
    url = MODELES_OFFICIELS.get(nom)
    if url is None:
        return f"Modèle wake inconnu « {nom} ». Choix : {', '.join(MODELES_OFFICIELS)}"
    dossier = config.DOSSIER_MODELES / "wake"
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / Path(url).name
    if destination.exists() and destination.stat().st_size > 10000:
        return f"✅ déjà là : {destination.name}"
    print(f" ⏳ téléchargement du modèle wake « {nom} »…")
    try:
        urllib.request.urlretrieve(url, destination)  # noqa: S310 — URL fixe et sûre
        return f"✅ {destination.name} ({destination.stat().st_size / 2**20:.1f} Mo) — " \
               "relance JIBI : dis « Hey Jarvis » pour l'appeler."
    except Exception as e:
        return f"❌ échec du téléchargement : {e}"


def disponible() -> bool:
    try:
        import openwakeword  # noqa: F401
    except ImportError:
        return False
    return len(modeles_disponibles()) > 0


def modeles_disponibles() -> list[Path]:
    dossier = config.DOSSIER_MODELES / "wake"
    if not dossier.exists():
        return []
    return [p for p in dossier.iterdir() if p.suffix in (".tflite", ".onnx")]


def _charger():
    global _modele
    if _modele is not None:
        return _modele
    try:
        from openwakeword.model import Model
    except ImportError:
        return None
    fichiers = modeles_disponibles()
    if not fichiers:
        return None
    framework = "onnx" if fichiers[0].suffix == ".onnx" else "tflite"
    try:
        _modele = Model(wakeword_models=[str(fichiers[0])],
                        inference_framework=framework)
    except Exception:
        _modele = None
    return _modele


def ecouter_mot(seuil: float = 0.5, timeout: float = 30.0) -> bool:
    """Écoute le micro jusqu'à détecter le mot d'activation (neuronal).

    Renvoie True si le mot est détecté, False sinon (délai/pas de modèle).
    """
    modele = _charger()
    if modele is None:
        return False
    try:
        import sounddevice as sd
    except ImportError:
        return False
    frequence = 16000
    bloc = 1280  # openWakeWord travaille par blocs de 80 ms
    debut = time.time()
    try:
        with sd.InputStream(samplerate=frequence, channels=1, dtype="int16",
                            blocksize=bloc) as flux:
            while time.time() - debut < timeout:
                morceau, _ = flux.read(bloc)
                predictions = modele.predict(morceau[:, 0])
                if any(score > seuil for score in predictions.values()):
                    modele.reset()
                    return True
    except Exception:
        return False
    return False
