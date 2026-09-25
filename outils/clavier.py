"""Contrôle du clavier — natif Windows (ctypes), sans dépendance.

Complète la souris (outils/souris.py) : JIBI peut maintenant taper du texte,
appuyer sur des touches et envoyer des raccourcis (Win, Alt+Tab, Ctrl+S…).

SÉCURITÉ (même doctrine que la souris) :
- taper_du_texte : risque ÉLEVÉ (confirmation à chaque fois) ;
- appuyer_touche : risque ÉLEVÉ ;
- raccourci_clavier : risque ÉLEVÉ ;
Aucune saisie de mot de passe : JIBI refuse explicitement les champs de
type mot de passe qu'il ne peut pas identifier, et ne tape jamais dans un
champ qu'il n'a pas vu (voir_ecran d'abord).
"""
from __future__ import annotations

import os
import time

from outils import outil

# Touches virtuelles Windows usuelles (VK codes).
TOUCHES = {
    "entree": 0x0D, "return": 0x0D, "echap": 0x1B, "escape": 0x1B,
    "tab": 0x09, "espace": 0x20, "space": 0x20, "retour": 0x08,
    "backspace": 0x08, "suppr": 0x2E, "delete": 0x2E, "fin": 0x23, "end": 0x23,
    "origine": 0x24, "home": 0x24, "page_haut": 0x21, "pageup": 0x21,
    "page_bas": 0x22, "pagedown": 0x22,
    "fleche_haut": 0x26, "up": 0x26, "fleche_bas": 0x28, "down": 0x28,
    "fleche_gauche": 0x25, "left": 0x25, "fleche_droite": 0x27, "right": 0x27,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
MODIFICATEURS = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
                 "maj": 0x10, "win": 0x5B, "windows": 0x5B}


def _user32():
    if os.name != "nt":
        return None
    import ctypes
    return ctypes.windll.user32


def _vk_for_char(lettre: str) -> int | None:
    """VK code d'un caractère alphanumérique simple (A-Z, 0-9)."""
    bas = lettre.lower()
    if len(bas) == 1 and bas.isalnum():
        return ord(bas.upper())
    return None


def _taper_caractere(u32, caractere: str) -> None:
    """Tape UN caractère, y compris accentués, via scancode Unicode."""
    import ctypes
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    for code in (ord(caractere[0]),):
        u32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
        u32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)


@outil("taper_du_texte",
       "Tape du texte au clavier dans la fenêtre ACTIVE (déplace d'abord le "
       "curseur et clique dans le champ avec deplacer_souris + cliquer_souris, "
       "ou utilise Alt+Tab via raccourci_clavier). Action sensible : "
       "confirmation demandée. Combien avec voir_ecran pour vérifier.",
       parametres={
           "texte": {"type": "str", "obligatoire": True,
                      "description": "texte à taper (accents acceptés)"},
           "entrer": {"type": "bool",
                       "description": "true pour appuyer sur Entrée après (défaut false)"},
       },
       categorie="systeme", risque="eleve",
       exemple="remplir une note → texte=bonjour, entrer=true")
def taper_du_texte(texte: str, entrer: bool = False) -> str:
    u32 = _user32()
    if u32 is None:
        return "Le clavier n'est pilotable que sous Windows."
    texte = str(texte or "")
    if not texte.strip():
        return "Texte vide : rien à taper."
    if len(texte) > 500:
        return "Texte trop long à taper d'un coup (500 caractères max)."
    for caractere in texte:
        _taper_caractere(u32, caractere)
        time.sleep(0.008)          # rythme humain : les applications suivent
    if entrer:
        time.sleep(0.05)
        u32.keybd_event(TOUCHES["entree"], 0, 0, 0)
        u32.keybd_event(TOUCHES["entree"], 0, 2, 0)   # KEYEVENTF_KEYUP
        return f"Texte tapé ({len(texte)} caractères) + Entrée."
    return f"Texte tapé ({len(texte)} caractères)."


@outil("appuyer_touche",
       "Appuie sur une touche du clavier : entree, echap, tab, suppr, fleche_haut/"
       "bas/gauche/droite, f5, fin, origine, page_haut, page_bas… Action sensible.",
       parametres={
           "touche": {"type": "str", "obligatoire": True,
                       "description": "nom de la touche (ex. entree, f5, fleche_bas)"},
           "fois": {"type": "int", "description": "nombre d'appuis (défaut 1, max 10)"},
       },
       categorie="systeme", risque="eleve",
       exemple="valider une boîte de dialogue → touche=entree")
def appuyer_touche(touche: str, fois: int = 1) -> str:
    u32 = _user32()
    if u32 is None:
        return "Le clavier n'est pilotable que sous Windows."
    nom = str(touche or "").strip().lower()
    code = TOUCHES.get(nom) or _vk_for_char(nom)
    if code is None:
        return ("Touche inconnue : " + nom + ". Utilise entree, echap, tab, suppr, "
                "fleche_haut/bas/gauche/droite, f1-f12, fin, origine, page_haut, page_bas, "
                "ou une lettre/chiffre simple.")
    fois = max(1, min(int(fois), 10))
    for _ in range(fois):
        u32.keybd_event(code, 0, 0, 0)
        u32.keybd_event(code, 0, 2, 0)
        time.sleep(0.05)
    return f"Touche {nom} appuyée ({fois}x)."


@outil("raccourci_clavier",
       "Envoie un raccourci clavier (touches tenues ensemble) : ctrl+s, alt+tab, "
       "win+d, ctrl+shift+echap… Modificateurs : ctrl, alt, shift/maj, win. "
       "Action sensible : confirmation demandée.",
       parametres={
           "touches": {"type": "str", "obligatoire": True,
                        "description": "séparées par + : ctrl+s, alt+f4, win+d, ctrl+shift+echap"},
       },
       categorie="systeme", risque="eleve",
       exemple="enregistrer → touches=ctrl+s")
def raccourci_clavier(touches: str) -> str:
    u32 = _user32()
    if u32 is None:
        return "Le clavier n'est pilotable que sous Windows."
    morceaux = [t.strip().lower() for t in str(touches or "").split("+") if t.strip()]
    if not morceaux or len(morceaux) > 4:
        return "Raccourci invalide : utilise 1 à 4 touches séparées par + (ex. ctrl+s)."
    mods: list[int] = []
    derniere: int | None = None
    for nom in morceaux:
        if nom in MODIFICATEURS:
            mods.append(MODIFICATEURS[nom])
            continue
        code = TOUCHES.get(nom) or _vk_for_char(nom)
        if code is None:
            return f"Touche inconnue dans le raccourci : {nom}."
        derniere = code
    if derniere is None:
        return "Un raccourci doit contenir une touche finale (pas seulement des modificateurs)."
    # alt+f4 est interdit : fermeture brutale de fenêtre, JIBI refuse.
    # "f4" est intercepté AVANT sa conversion (0x74), y compris via lettre+chiffre.
    if 0x12 in mods and any(m in ("f4", "04") for m in morceaux):
        return "alt+f4 refusé : pour fermer une fenêtre, dis « ferme l'onglet » ou utilise la souris."
    for code in mods:
        u32.keybd_event(code, 0, 0, 0)
    u32.keybd_event(derniere, 0, 0, 0)
    u32.keybd_event(derniere, 0, 2, 0)
    for code in reversed(mods):
        u32.keybd_event(code, 0, 2, 0)
    return f"Raccourci {touches} envoyé."
