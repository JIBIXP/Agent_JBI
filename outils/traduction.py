"""Outils de traduction de JIBI 2.

Traduit du texte vers plusieurs langues en utilisant le modèle local
Ollama si disponible, sinon un dictionnaire de base. Entièrement local.
"""
from __future__ import annotations

from pathlib import Path

from outils import outil


LANGUES = {
    "fr": "français",
    "en": "anglais",
    "es": "espagnol",
    "de": "allemand",
    "it": "italien",
    "pt": "portugais",
    "zh": "chinois",
    "ja": "japonais",
    "ko": "coréen",
    "ar": "arabe",
    "ru": "russe",
    "nl": "néerlandais",
    "pl": "polonais",
    "tr": "turc",
    "vi": "vietnamien",
    "th": "thaï",
}

# Dictionnaire de base pour les phrases courantes (fallback)
_DICT_BASE = {
    ("fr", "en"): {"bonjour": "hello", "merci": "thank you", "au revoir": "goodbye",
                    "oui": "yes", "non": "no", "s'il vous plaît": "please"},
    ("fr", "es"): {"bonjour": "hola", "merci": "gracias", "au revoir": "adiós",
                    "oui": "sí", "non": "no"},
    ("en", "fr"): {"hello": "bonjour", "thank you": "merci", "goodbye": "au revoir",
                    "yes": "oui", "no": "non", "please": "s'il vous plaît"},
}


def _traduire_texte(texte: str, langue_cible: str) -> str:
    """Traduit un texte via le modèle local Ollama avec fallback."""
    # Tentative Ollama
    try:
        from jibi2 import llm
        prompt = (
            f"Traduis uniquement ce texte en {LANGUES.get(langue_cible, langue_cible)} :\n"
            f"---Début---\n{texte}\n---Fin---\n"
            "Réponds uniquement avec la traduction."
        )
        reponse = llm.repondre(prompt)
        if reponse and "reponse" in reponse:
            return reponse["reponse"]
    except Exception:
        pass
    # Fallback : dictionnaire simple
    mots = texte.lower().split()
    trad = []
    for mot in mots:
        trouve = False
        for (src, dst), dico in _DICT_BASE.items():
            if src == "fr" and langue_cible in ("en", "es") and mot in dico:
                trad.append(dico[mot]); trouve = True; break
            elif src == "en" and langue_cible == "fr" and mot in dico:
                trad.append(dico[mot]); trouve = True; break
        if not trouve:
            trad.append(mot)
    return " ".join(trad) if trad else texte


@outil("traduire",
       "Traduit un texte vers une langue cible en utilisant le modèle "
       "local Ollama. Fallback par dictionnaire si Ollama indisponible. "
       "Langues : fr, en, es, de, it, pt, zh, ja, ko, ar, ru, nl, pl, tr, vi, th.",
       {"texte": {"type": "str", "obligatoire": True,
                    "description": "texte à traduire"},
        "langue": {"type": "str", "obligatoire": False,
                    "description": "code langue cible (fr, en, es, de, ...)"}},
       categorie="traduction", risque="faible",
       exemple='{"outil": "traduire", "parametres": {"texte": "Bonjour", "langue": "en"}}')
def traduire(texte: str, langue: str = "en") -> str:
    """Traduit un texte vers la langue cible."""
    if langue not in LANGUES:
        return f"Langue inconnue. Disponibles : {', '.join(LANGUES)}"
    resultat = _traduire_texte(texte, langue)
    return f"[{LANGUES[langue]}] {resultat}"


@outil("langues_disponibles",
       "Liste toutes les langues supportées par la traduction.",
       {}, categorie="traduction", risque="faible",
       exemple='{"outil": "langues_disponibles", "parametres": {}}')
def langues_disponibles() -> str:
    """Retourne la liste des langues disponibles."""
    return "Langues disponibles : " + ", ".join(
        f"{code} ({nom})" for code, nom in LANGUES.items()
    )
