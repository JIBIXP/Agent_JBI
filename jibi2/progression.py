"""Progression partagée des longues actions de JIBI.

Le bureau et le panneau web lisent ce petit état pour afficher une jauge.
Le fichier est dans donnees/ et ne contient ni code ni secret.
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from . import config

FICHIER = config.DOSSIER_JOURNAL / "progression.json"
HISTORIQUE = config.DOSSIER_JOURNAL / "progression.jsonl"
_VERROU = threading.RLock()


def _ecrire(etat: dict) -> None:
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    temporaire = FICHIER.with_suffix(".tmp")
    texte = json.dumps(etat, ensure_ascii=False, indent=2)
    temporaire.write_text(texte, encoding="utf-8")
    try:
        temporaire.replace(FICHIER)
    except PermissionError:
        # OneDrive peut verrouiller brièvement le replacement ; l'écriture
        # directe est le repli sûr pour ce petit état local.
        for _ in range(3):
            try:
                time.sleep(0.05)
                temporaire.replace(FICHIER)
                return
            except PermissionError:
                continue
        try:
            FICHIER.write_text(texte, encoding="utf-8")
        finally:
            temporaire.unlink(missing_ok=True)


def lire() -> dict:
    if not FICHIER.exists():
        return {"actif": False, "pourcent": 0, "titre": "", "etape": "", "resultat": ""}
    try:
        valeur = json.loads(FICHIER.read_text(encoding="utf-8"))
        return valeur if isinstance(valeur, dict) else {
            "actif": False, "pourcent": 0, "titre": "", "etape": "", "resultat": ""}
    except (OSError, json.JSONDecodeError):
        return {"actif": False, "pourcent": 0, "titre": "", "etape": "", "resultat": ""}


def demarrer(titre: str, detail: str = "") -> str:
    identifiant = f"{int(time.time() * 1000):x}"
    etat = {"id": identifiant, "actif": True, "pourcent": 0,
            "titre": str(titre)[:160], "etape": str(detail)[:240],
            "debut": time.strftime("%Y-%m-%dT%H:%M:%S"), "resultat": ""}
    with _VERROU:
        _ecrire(etat)
    return identifiant


def mettre(pourcent: int | float, etape: str = "") -> None:
    with _VERROU:
        etat = lire()
        if not etat.get("actif"):
            return
        etat["pourcent"] = max(0, min(100, int(round(float(pourcent)))))
        if etape:
            etat["etape"] = str(etape)[:240]
        _ecrire(etat)


def terminer(resultat: str = "terminé", succes: bool = True) -> None:
    with _VERROU:
        etat = lire()
        etat.update({"actif": False, "pourcent": 100 if succes else etat.get("pourcent", 0),
                     "etape": "terminé" if succes else "interrompu",
                     "resultat": str(resultat)[:300],
                     "fin": time.strftime("%Y-%m-%dT%H:%M:%S")})
        _ecrire(etat)
        try:
            with HISTORIQUE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(etat, ensure_ascii=False) + "\n")
        except OSError:
            pass


@contextmanager
def tache(titre: str, detail: str = "") -> Iterator[dict]:
    """Contexte simple : ``with tache(...): mettre(50, ...)``."""
    identifiant = demarrer(titre, detail)
    suivi = {"id": identifiant, "titre": titre}
    try:
        yield suivi
    except Exception as e:
        terminer(f"échec : {str(e)[:240]}", succes=False)
        raise
    else:
        terminer("terminé", succes=True)
