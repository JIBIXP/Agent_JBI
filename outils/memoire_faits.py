"""Outils mémoire de JIBI 2 : faits durables (« retiens que… », « que sais-tu… »)."""
from __future__ import annotations

from outils import outil, service


@outil("retenir", "Mémorise durablement un fait sur l'utilisateur (remplace la valeur si la clé existe déjà).",
       {"cle": {"type": "str", "obligatoire": True, "description": "étiquette courte, ex. 'prénom', 'ville', 'boisson'"},
        "valeur": {"type": "str", "obligatoire": True, "description": "le fait à retenir"}},
       categorie="memoire", exemple='{"outil": "retenir", "parametres": {"cle": "ville", "valeur": "Rennes"}}')
def retenir(cle: str, valeur: str) -> str:
    service("memoire").retenir(cle, valeur)
    return f"Retenu : {cle} = {valeur}"


@outil("rappeler", "Retrouve les faits mémorisés (par mot-clé, ou tous si mot vide).",
       {"mot": {"type": "str", "obligatoire": False, "description": "mot à chercher ; vide = derniers faits"}},
       categorie="memoire")
def rappeler(mot: str = "") -> str:
    faits = service("memoire").rappeler(mot or "")
    if not faits:
        return "Je n'ai encore rien en mémoire qui corresponde."
    return "\n".join(f"{c} : {v}" for c, v in faits)
