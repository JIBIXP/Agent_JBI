"""Sécurité de JIBI 2 — permissions N1/N2/N3.

Chaque outil est étiqueté par risque (faible / moyen / élevé), traduit en
niveau de permission :

    N1 (faible)  → jamais demandé (lecture_sûre : heure, calcul, dé...)
    N2 (moyen)   → par défaut sans demande (écritures confinées à
                   donnees/fichiers/, workflows...) — réglable en
                   « demander » pour un PC prudent ;
    N3 (élevé)   → demande une confirmation humaine par défaut
                   (commande système, extinction, modification du noyau...).

Trois politiques possibles par niveau, dans le .env :

    JIBI_AUTORISATION_N1 / N2 / N3 = toujours | demander | jamais

Le verrou principal : pour les outils dits ``_N3`` (``OUTILS_N3_VERROUILLE``),
« toujours autoriser » est refusé par construction. Éteindre le PC, lancer
une commande, écrire dans le noyau, installer une mise à jour sans jamais
poser de question : jamais. Même si le .env dit « toujours », même si
CONFIRMER_RISQUES=0, la politique retombe sur « demander » — c'est le code
qui refuse, pas un réglage.

L'ancien drapeau global CONFIRMER_RISQUES reste compris : =0 fait passer
N3 en « toujours » ... sauf pour les outils _N3 verrouillés. Les exceptions
doublement logées (auto-modification du noyau, déplacements sans
confirmation) exigent chacune leur choix explicite dans le .env.

`JIBI_MODIFICATION_AUTO=1` active le mode de modification et de
restauration du noyau, mais `JIBI_AUTONOMIE_NOYAU` reste par défaut à 0 :
une modification du noyau demande toujours une confirmation explicite. Les
écritures restent confinées au projet, les tests et le retour arrière sont
obligatoires. Les écritures utilisateur restent confinées dans
donnees/fichiers/ (voir outils/fichiers.py).
"""
from __future__ import annotations

from collections.abc import Callable

from . import config

Confirmer = Callable[[str, str], bool]

#: risque → niveau de permission
NIVEAU_DU_RISQUE = {"faible": "N1", "moyen": "N2", "eleve": "N3"}

#: niveau → risque (utile aux interfaces/affichages)
RISQUE_DU_NIVEAU = {"N1": "faible", "N2": "moyen", "N3": "eleve"}

# Les outils ``_N3`` : concrètement dangereux jamais autorisés sans question.
# « Ajouter un exécutable lancé ensuite sans question : jamais toujours » —
# extinction du PC, commande système, écriture/restauration du noyau,
# installation d'un paquet : la politique « toujours » est refusée par
# construction, dans le code, par la Garde.
OUTILS_N3_VERROUILLE = frozenset({
    "eteindre_pc",
    "executer_commande",
    "modifier_noyau",
    "restaurer_noyau",
    "installer_mise_a_jour",
})

# Le noyau peut être autorisé automatiquement seulement si
# JIBI_AUTONOMIE_NOYAU=1 est explicitement choisi. Par défaut, ces deux
# actions restent soumises à la confirmation humaine.
OUTILS_MODIFICATION_AUTO = frozenset({"modifier_noyau", "restaurer_noyau"})


def niveau_de(risque: str) -> str:
    """Niveau N1/N2/N3 d'un outil à partir de son étiquette de risque.
    Une étiquette inconnue est traitée comme du risque maximal."""
    return NIVEAU_DU_RISQUE.get((risque or "").strip().lower(), "N3")


def _politique(niveau: str) -> str:
    """Politique effective d'un niveau : toujours | demander | jamais.

    Valeur vide = défaut du niveau (N1/N2 : toujours ; N3 : demander,
    tant que l'ancien drapeau CONFIRMER_RISQUES vaut 1). Une valeur
    présente mais inconnue vaut « demander » : on ne bricole pas la
    sûreté (fail-safe), on ne fail jamais ouvert.
    """
    brut = config.valeur("JIBI_AUTORISATION_" + niveau, "").strip().lower()
    if brut in ("toujours", "demander", "jamais"):
        return brut
    if brut:                      # valeur présente mais non reconnue
        return "demander"         # fail-safe : demander, jamais fail ouvert
    if niveau == "N3":
        return "toujours" if not config.valeur_bool("CONFIRMER_RISQUES") else "demander"
    return "toujours"


class Garde:
    def __init__(self, confirmer: Confirmer | None = None) -> None:
        # confirmer(titre, detail) -> bool ; remplacable par chaque interface
        # (console = input, fenêtre = boîte de dialogue).
        self.confirmer: Confirmer = confirmer or (lambda titre, detail: True)

    def est_permissive_par_defaut(self) -> bool:
        """Vrai tant qu'aucune interface n'a branché SA boîte de confirmation.
        Le défaut est la lambda de __init__ : autoriser() suit alors la
        politique N1/N2/N3 sans avis humain autre que les réglages .env."""
        return getattr(self.confirmer, "__qualname__", "").endswith("<lambda>")

    def autoriser(self, nom_outil: str, risque: str, detail: str) -> bool:
        # Si l'auto-amélioration du noyau est activée (deux drapeaux
        # explicites, tests + retour arrière obligatoires), autoriser les
        # modifications de code.
        if (risque == "eleve"
                and nom_outil in OUTILS_MODIFICATION_AUTO
                and config.valeur_bool("JIBI_MODIFICATION_AUTO")
                and config.valeur_bool("JIBI_AUTONOMIE_NOYAU")):
            return True
        # Si CONFIRMER_DEPLACEMENT=0, les déplacements/copies de fichiers
        # ne demandent pas de confirmation (choix explicite, périmètre
        # limité : l'espace de travail vers les dossiers personnels).
        if (nom_outil in ("deplacer_document", "copier_document")
                and not config.valeur_bool("CONFIRMER_DEPLACEMENT")):
            return True
        niveau = niveau_de(risque)
        politique = _politique(niveau)
        # LE VERROU : un outil _N3 ne court jamais « toujours autoriser »,
        # quelle que soit la config. Ce n'est pas un réglage, c'est le code.
        if (nom_outil in OUTILS_N3_VERROUILLE
                and politique == "toujours"):
            politique = "demander"
        if politique == "jamais":
            return False                 # refusé : la politique interdit ce niveau
        if politique == "demander":
            return bool(self.confirmer(nom_outil, detail))
        return True
