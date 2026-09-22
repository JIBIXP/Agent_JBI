"""Outils notes de JIBI 2 : pense-bête stocké dans la base SQLite locale."""
from __future__ import annotations

from outils import outil, service


@outil("ajouter_note", "Enregistre une note personnelle pour l'utilisateur (pense-bête).",
       {"texte": {"type": "str", "obligatoire": True, "description": "la note à retenir"}},
       categorie="notes", exemple='{"outil": "ajouter_note", "parametres": {"texte": "acheter du pain"}}')
def ajouter_note(texte: str) -> str:
    numero = service("memoire").ajouter_note(texte)
    return f"Note n°{numero} enregistrée : « {texte} »"


@outil("lister_notes", "Liste les dernières notes enregistrées.",
       {"nombre": {"type": "int", "obligatoire": False, "description": "combien en montrer (défaut 10)"}},
       categorie="notes")
def lister_notes(nombre: int = 10) -> str:
    notes = service("memoire").lister_notes(max(1, min(int(nombre), 30)))
    if not notes:
        return "Aucune note enregistrée pour l'instant."
    return "\n".join(f"n°{n} — {t}  ({h})" for n, t, h in notes)


@outil("chercher_notes", "Cherche dans les notes un mot ou une expression.",
       {"mot": {"type": "str", "obligatoire": True, "description": "morceau de texte à chercher"}},
       categorie="notes")
def chercher_notes(mot: str) -> str:
    notes = service("memoire").chercher_notes(mot)
    if not notes:
        return f"Aucune note ne contient « {mot} »."
    return "\n".join(f"n°{n} — {t}  ({h})" for n, t, h in notes)


@outil("supprimer_note", "Supprime une note par son numéro (ex. n°3 → numero = 3).",
       {"numero": {"type": "int", "obligatoire": True, "description": "numéro de la note"}},
       categorie="notes", risque="moyen")
def supprimer_note(numero: int) -> str:
    if service("memoire").supprimer_note(int(numero)):
        return f"Note n°{numero} supprimée."
    return f"Aucune note n°{numero}."
