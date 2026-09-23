"""Planificateur de JIBI 2 : exécute les workflows à heure fixe.

Un workflow peut déclarer "horaire": "08:00" dans son JSON : il est alors
exécuté automatiquement chaque jour à cette heure (tant que JIBI tourne).
Chaque exécution est annoncée (console, voix, ou boule de l'interface).
"""
from __future__ import annotations

import json
import threading
import time

from jibi2 import config

_dernier_jour: dict[str, str] = {}
_verrou = threading.Lock()


def _annoncer(texte: str) -> None:
    """Envoie une annonce à l'interface (ou la console en repli)."""
    try:
        from outils.notifications import notifier_systeme
        notifier_systeme("JIBI — Routine programmée", texte.splitlines()[-1][:150])
    except Exception:
        pass
    try:
        from outils import service
        file = service("annonces")
        file.put_nowait(texte)
        return
    except Exception:
        pass
    print("\n" + texte)


def workflows_programmes() -> list[tuple[str, str]]:
    """Liste (nom, horaire) des workflows programmés."""
    from outils.workflows import _dossier
    resultats: list[tuple[str, str]] = []
    if not config.DOSSIER_DONNEES.exists():
        return resultats
    for chemin in _dossier().glob("*.json"):
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        horaire = str(donnees.get("horaire", "")).strip()
        if horaire:
            resultats.append((donnees.get("nom", chemin.stem), horaire))
    return resultats


def _cycle() -> None:
    import outils.workflows as workflows
    maintenant = time.strftime("%H:%M")
    jour = time.strftime("%Y-%m-%d")
    for nom, horaire in workflows_programmes():
        if not maintenant.startswith(horaire[:5]):
            continue
        with _verrou:
            if _dernier_jour.get(nom) == jour:
                continue
            _dernier_jour[nom] = jour
        resultat = workflows.executer(nom)
        premiere = resultat.splitlines()[1] if resultat.count("\n") >= 1 else resultat
        _annoncer(f"⏰ Workflow programmé « {nom} » ({horaire}) :\n{premiere}")
        try:
            from jibi2.evolution import noter_changelog
            noter_changelog(f"workflow programmé « {nom} » exécuté automatiquement ({horaire})")
        except Exception:
            pass


def _boucle(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            if config.valeur_bool("JIBI_HORAIRE_ACTIF"):
                _cycle()
        except Exception as e:  # le planificateur ne doit jamais tuer JIBI
            print(f"(planificateur : {e})")
        stop.wait(20)


def demarrer(stop: threading.Event | None = None) -> threading.Event:
    stop = stop or threading.Event()
    threading.Thread(target=_boucle, args=(stop,), daemon=True).start()
    return stop