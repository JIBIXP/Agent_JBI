"""Contrôle de la souris — natif Windows (ctypes), inspiré de Jarvis/souris.py.

Jarvis clique sur ce qu'il VOIT : l'écran est capturé, le modèle repère
l'élément dans l'image, puis le clic se fait en FRACTIONS de l'écran
(0-100 %), ce qui annule les problèmes de résolution/DPI.
JIBI suit la même idée : combine voir_ecran (moondream, local) avec ces
outils pour « clique sur le bouton lecture ».

SÉCURITÉ : cliquer est SENSIBLE → risque élevé = JIBI demande TA
confirmation avant chaque clic (même doctrine que Jarvis). Déplacer et
faire défiler sont bénins.
"""
from __future__ import annotations

import os
import time

from outils import outil


def _user32():
    if os.name != "nt":
        return None
    import ctypes
    return ctypes.windll.user32


def _bornes(valeur: float) -> float:
    return max(0.0, min(100.0, float(valeur)))


@outil("deplacer_souris",
       "Déplace le curseur souris. x et y sont des POURCENTAGES de l'écran "
       "(0=gauche/haut, 100=droite/bas). Demande voir_ecran d'abord pour viser.",
       parametres={
           "x": {"type": "int", "obligatoire": True, "description": "position horizontale 0-100 (%)"},
           "y": {"type": "int", "obligatoire": True, "description": "position verticale 0-100 (%)"},
       },
       categorie="systeme", risque="faible",
       exemple="clique en bas à droite → x=90, y=95")
def deplacer_souris(x: float, y: float) -> str:
    u32 = _user32()
    if u32 is None:
        return "La souris n'est pilotable que sous Windows."
    largeur, hauteur = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
    px, py = int(largeur * _bornes(x) / 100), int(hauteur * _bornes(y) / 100)
    place = u32.SetPhysicalCursorPos(px, py) or u32.SetCursorPos(px, py)
    return f"Curseur placé en ({px}, {py})." if place else "Le déplacement a été refusé par Windows."


@outil("cliquer_souris",
       "CLIQUE à la position actuelle du curseur (déplace d'abord avec "
       "deplacer_souris). Action sensible : JIBI demandera ta confirmation.",
       parametres={
           "bouton": {"type": "str", "description": "gauche (défaut) | droit"},
           "double": {"type": "bool", "description": "true pour un double-clic"},
       },
       categorie="systeme", risque="eleve",
       exemple="valider le bouton → bouton=gauche")
def cliquer_souris(bouton: str = "gauche", double: bool = False) -> str:
    u32 = _user32()
    if u32 is None:
        return "La souris n'est pilotable que sous Windows."
    codes = {"gauche": (0x0002, 0x0004), "droit": (0x0008, 0x0010),
             "droite": (0x0008, 0x0010), "milieu": (0x0020, 0x0040)}
    paire = codes.get(bouton.strip().lower(), codes["gauche"])
    u32.mouse_event(paire[0], 0, 0, 0, 0)
    u32.mouse_event(paire[1], 0, 0, 0, 0)
    if double:
        time.sleep(0.06)
        u32.mouse_event(paire[0], 0, 0, 0, 0)
        u32.mouse_event(paire[1], 0, 0, 0, 0)
        return "Double-clic effectué."
    return "Clic effectué."


@outil("defiler",
       "Fait défiler la page sous le curseur (molette).",
       parametres={
           "direction": {"type": "str", "description": "haut | bas (défaut bas)"},
           "quantite": {"type": "int", "description": "crans de molette (défaut 3)"},
       },
       categorie="systeme", risque="faible",
       exemple="descend aux commentaires → direction=bas, quantite=5")
def defiler(direction: str = "bas", quantite: int = 3) -> str:
    u32 = _user32()
    if u32 is None:
        return "La souris n'est pilotable que sous Windows."
    quantite = max(1, min(20, int(quantite)))
    delta = -120 * quantite if direction.strip().lower() == "bas" else 120 * quantite
    u32.mouse_event(0x0800, 0, 0, delta, 0)          # MOUSEEVENTF_WHEEL
    return f"Page défilée vers le {direction.strip().lower()} ({quantite} crans)."
