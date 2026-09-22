"""Outils rappels de JIBI 2 : minuteurs internes (« rappelle-moi dans 10 minutes »)."""
from __future__ import annotations

import contextlib
import threading
import time

from outils import outil, service

_RAPPELS: list[dict] = []          # {"numero", "texte", "echeance", "minuterie"}
_VERROU = threading.Lock()
_prochain_numero = 1


def _sonner(texte: str, numero: int) -> None:
    with _VERROU:
        _RAPPELS[:] = [r for r in _RAPPELS if r["numero"] != numero]
    message = f"⏰ RAPPEL : {texte}"
    try:
        from outils.notifications import notifier_systeme
        notifier_systeme("JIBI — Rappel", texte)
    except Exception:
        pass
    diffuse = False
    with contextlib.suppress(KeyError):
        file = service("annonces")
        file.put_nowait(message)
        diffuse = True
    if not diffuse:
        with contextlib.suppress(KeyError):
            sur_rappel = service("sur_rappel")
            sur_rappel(message)
            diffuse = True
    if not diffuse:
        print("\n" + message)


@outil("programmer_rappel", "Programme un rappel qui se déclenchera dans X minutes (JIBI affichera et dira le message).",
       {"texte": {"type": "str", "obligatoire": True, "description": "message du rappel"},
        "minutes": {"type": "int", "obligatoire": True, "description": "délai en minutes"}},
       categorie="rappels", exemple='{"outil": "programmer_rappel", "parametres": {"texte": "sortir le four", "minutes": 15}}')
def programmer_rappel(texte: str, minutes: int) -> str:
    global _prochain_numero
    with _VERROU:
        numero = _prochain_numero
        _prochain_numero += 1
        minuteur = threading.Timer(max(5, int(minutes) * 60), _sonner, args=(texte, numero))
        minuteur.daemon = True
        _RAPPELS.append({"numero": numero, "texte": texte,
                         "echeance": time.time() + max(5, int(minutes) * 60), "minuterie": minuteur})
    minuteur.start()
    return f"Rappel n°{numero} programmé dans {minutes} min : « {texte} »"


@outil("lister_rappels", "Liste les rappels en attente.", {}, categorie="rappels")
def lister_rappels() -> str:
    with _VERROU:
        if not _RAPPELS:
            return "Aucun rappel en attente."
        lignes = []
        for r in _RAPPELS:
            reste = max(0, int(r["echeance"] - time.time()) // 60)
            lignes.append(f"n°{r['numero']} — dans ~{reste} min : {r['texte']}")
        return "\n".join(lignes)


@outil("annuler_rappel", "Annule un rappel par son numéro.",
       {"numero": {"type": "int", "obligatoire": True, "description": "numéro du rappel"}},
       categorie="rappels")
def annuler_rappel(numero: int) -> str:
    with _VERROU:
        for r in _RAPPELS:
            if r["numero"] == int(numero):
                r["minuterie"].cancel()
                _RAPPELS.remove(r)
                return f"Rappel n°{numero} annulé."
    return f"Aucun rappel n°{numero}."
