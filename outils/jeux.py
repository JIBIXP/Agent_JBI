"""Petits jeux 100 % locaux avec JIBI — pour le plaisir, sans réseau.

Demandé : « n'oublie pas que jeux, quelque chose de local ». Le dépôt
Jarvis n'a pas de jeux : c'est une touche JIBI. Dé, pile ou face,
pierre-feuille-ciseaux et le nombre mystère — tout marche hors ligne et
se joue à la voix.
"""
from __future__ import annotations

import random

from outils import outil

_MYSTERE: dict = {}          # {"cible": int, "essais": int} pendant une partie


@outil("lancer_un_de", "Lance un dé (6 faces par défaut ; 4, 8, 12, 20… au choix).",
       parametres={"faces": {"type": "int", "description": "nombre de faces (défaut 6)"}},
       categorie="jeux", risque="faible",
       exemple="lance un dé à 20 faces → faces=20")
def lancer_un_de(faces: int = 6) -> str:
    faces = max(2, min(100, int(faces)))
    return f"🎲 Le dé à {faces} faces donne {random.randint(1, faces)}."


@outil("pile_ou_face", "Lance une pièce : pile ou face.",
       categorie="jeux", risque="faible", exemple="pile ou face ?")
def pile_ou_face() -> str:
    return "🪙 " + random.choice(["Pile !", "Face !"])


@outil("pierre_feuille_ciseaux",
       "Joue à pierre-feuille-ciseaux contre JIBI.",
       parametres={"choix": {"type": "str", "obligatoire": True,
                             "description": "pierre | feuille | ciseaux"}},
       categorie="jeux", risque="faible",
       exemple="je joue pierre → choix=pierre")
def pierre_feuille_ciseaux(choix: str) -> str:
    c = choix.strip().lower()
    if c not in ("pierre", "feuille", "ciseaux"):
        return "Choisis : pierre, feuille ou ciseaux."
    moi = random.choice(["pierre", "feuille", "ciseaux"])
    bat = {"pierre": "ciseaux", "feuille": "pierre", "ciseaux": "feuille"}
    if c == moi:
        return f"✊ {moi} contre {c} — égalité !"
    if bat[c] == moi:
        return f"J'ai joué {moi}… tu gagnes, bien joué ! 🎉"
    return f"J'ai joué {moi} — je gagne cette fois ! 😄"


@outil("nombre_mystere",
       "Jeu du nombre mystère entre 1 et 100 : JIBI choisit, tu devines, il "
       "dit « plus grand » ou « plus petit ». Action : commencer ou deviner.",
       parametres={
           "action": {"type": "str", "obligatoire": True,
                      "description": "commencer | deviner"},
           "nombre": {"type": "int", "description": "ta proposition (pour deviner)"},
       },
       categorie="jeux", risque="faible",
       exemple="c'est 50 ? → action=deviner, nombre=50")
def nombre_mystere(action: str, nombre: int = 0) -> str:
    a = action.strip().lower()
    if a == "commencer":
        _MYSTERE.clear()
        _MYSTERE["cible"] = random.randint(1, 100)
        _MYSTERE["essais"] = 0
        return "J'ai choisi un nombre entre 1 et 100. À toi de deviner !"
    if a in ("deviner", "propose", "essai"):
        if "cible" not in _MYSTERE:
            return "Aucune partie en cours — dis-moi « commence le nombre mystère »."
        _MYSTERE["essais"] += 1
        n = int(nombre)
        if n < _MYSTERE["cible"]:
            return f"C'est PLUS GRAND que {n} (essai n°{_MYSTERE['essais']})."
        if n > _MYSTERE["cible"]:
            return f"C'est PLUS PETIT que {n} (essai n°{_MYSTERE['essais']})."
        essais = _MYSTERE["essais"]
        _MYSTERE.clear()
        return f"🎉 Bravo ! C'était bien {n}, trouvé en {essais} essai(s) !"
    return "Action inconnue : commence ou devine."
