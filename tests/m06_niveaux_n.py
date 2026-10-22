# -*- coding: utf-8 -*-
"""Section 4bis — permissions N1/N2/N3 — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 4bis. Permissions N1 / N2 / N3 (verrou « jamais toujours » pour N3)
from jibi2 import securite as _securite  # noqa: E402

_env_sauve = {}
def _regle_env(cle: str, valeur: str | None) -> None:
    _env_sauve[cle] = os.environ.get(cle)
    if valeur is None:
        os.environ.pop(cle, None)
    else:
        os.environ[cle] = valeur
    config._cache = None

try:
    for _cle in ("JIBI_AUTORISATION_N1", "JIBI_AUTORISATION_N2",
                 "JIBI_AUTORISATION_N3"):
        _regle_env(_cle, None)
    verif("N : faible→N1, moyen→N2, élevé→N3",
          (_securite.niveau_de("faible"), _securite.niveau_de("moyen"),
           _securite.niveau_de("eleve")) == ("N1", "N2", "N3"))
    verif("N : étiquette inconnue traitée comme N3 (sûr)",
          _securite.niveau_de("bizarre") == "N3")
    _garde_jamais = Garde(lambda n, d: False)
    _garde_accord = Garde(lambda n, d: True)
    verif("N1 par défaut : toujours accordé, sans demander",
          _garde_jamais.autoriser("calculer", "faible", "detail"))
    verif("N2 par défaut : toujours accordé (défaut conservé de JIBI)",
          _garde_jamais.autoriser("ecrire_fichier", "moyen", "detail"))
    verif("N3 par défaut : demande humaine exigée",
          not _garde_jamais.autoriser("eteindre_pc", "eleve", "detail")
          and _garde_accord.autoriser("eteindre_pc", "eleve", "detail"))
    # LE VERROU : même « JIBI_AUTORISATION_N3=toujours », un outil _N3
    # retombe sur « demander » — ce n'est pas un réglage, c'est le code.
    # Discriminateur : une Garde qui refuse tout — le vieux « toujours »
    # donnait True, la demande forcée donne False.
    _regle_env("JIBI_AUTORISATION_N3", "toujours")
    verif("N3 verrouillé : la politique réglée est bien « toujours »",
          _securite._politique("N3") == "toujours")
    verif("N3 verrouillé : eteindre_pc demande malgré « toujours »",
          not _garde_jamais.autoriser("eteindre_pc", "eleve", "detail"))
    verif("N3 verrouillé : executer_commande demande malgré « toujours »",
          not _garde_jamais.autoriser("executer_commande", "eleve", "detail"))
    verif("N3 verrouillé : modifier_noyau demande malgré « toujours »",
          not _garde_jamais.autoriser("modifier_noyau", "eleve", "detail"))
    verif("N3 verrouillé : les autres outils N3 restent sur leur réglage",
          _garde_accord.autoriser("lire_fichier_pc", "eleve", "detail"))
    # Politique « jamais » : un niveau entier est refusé net.
    _regle_env("JIBI_AUTORISATION_N2", "jamais")
    verif("N2=jamais : tout outil moyen est refusé",
          not _garde_accord.autoriser("ecrire_fichier", "moyen", "detail"))
    # Valeur inconnue dans le .env → « demander » (fail-safe : jamais
    # fail ouvert). Une Garde qui refuse tout dévoile la demande.
    _regle_env("JIBI_AUTORISATION_N2", "peut-être")
    verif("N2 valeur inconnue → demander (fail-safe)",
          not _garde_jamais.autoriser("ecrire_fichier", "moyen", "detail")
          and _garde_accord.autoriser("ecrire_fichier", "moyen", "detail"))
    # CONFIRMER_RISQUES=0 : l'ancien drapeau global ne débloque pas _N3.
    _regle_env("JIBI_AUTORISATION_N3", None)
    _regle_env("CONFIRMER_RISQUES", "0")
    verif("CONFIRMER_RISQUES=0 : N3 non-_N3 passe sans question",
          _garde_jamais.autoriser("lire_fichier_pc", "eleve", "detail"))
    verif("CONFIRMER_RISQUES=0 : eteindre_pc demande QUAND MÊME",
          not _garde_jamais.autoriser("eteindre_pc", "eleve", "detail"))
finally:
    for _cle, _val in _env_sauve.items():
        if _val is None:
            os.environ.pop(_cle, None)
        else:
            os.environ[_cle] = _val
    config._cache = None
