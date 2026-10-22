# -*- coding: utf-8 -*-
"""Compatibilité pytest : ``pytest tests/test_suite.py`` rejoue toute la suite.

L'import de tests/verification.py exécute la suite complète dans l'ordre
historique (les mNN_* impriment leurs résultats comme dans le script
d'origine) ; l'assertion exige ensuite zéro échec.
"""
from __future__ import annotations


def test_complet():
    import moteur

    import verification  # l'import lance toute la suite, dans l'ordre

    assert verification.test_complet is not None
    assert moteur.stats["ko"] == 0, (
        f"{moteur.stats['ko']} contrôle(s) en échec : "
        f"{moteur.stats['ok']} OK avant l'échec"
    )
