# -*- coding: utf-8 -*-
"""Sections finales (34) — analyse/bureautique/géo/images/audit — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

from outils import analyse as _analyse34  # noqa: E402
from outils import bureautique as _bureau34  # noqa: E402
from outils import localisation as _local34  # noqa: E402
from outils import signaux as _signaux34  # noqa: E402
from outils import navigateur as _navigateur34  # noqa: E402
from outils import web as _web34  # noqa: E402
from jibi2 import audit as _audit34  # noqa: E402

_fichier_analyse = config.DOSSIER_FICHIERS / "_analyse_test.txt"
_fichier_analyse.write_text("une ligne de test\nune autre ligne de test\n", encoding="utf-8")
_analyse = _analyse34.analyser_fichier(_fichier_analyse.name)
verif("analyse : statistiques de fichier", "SHA-256" in _analyse and "Mots : 9" in _analyse, _analyse[:120])
_supprimer_tolerant(_fichier_analyse)
_excel_test = config.DOSSIER_FICHIERS / "_budget_test.xlsx"
_creation_excel = _bureau34.creer_excel(_excel_test.name,
                                       '[["Poste","Montant"],["Loyer",850]]')
_analyse_excel = _bureau34.analyser_excel(_excel_test.name)
verif("bureautique : Excel créé et analysé",
      "Excel créé" in _creation_excel and "Dimensions" in _analyse_excel,
      _analyse_excel[:100])
_supprimer_tolerant(_excel_test)
_ancien_get = _web34._get
_web34._get = lambda *args, **kwargs: '{"city":"Rennes","region":"Bretagne","country_name":"France","timezone":"Europe/Paris"}'
try:
    _position_test = _local34.localisation_approchee()
finally:
    _web34._get = _ancien_get
verif("géolocalisation : estimation de ville", "Rennes" in _position_test, _position_test)
_ancien_get_images = _web34._get
_web34._get = lambda *args, **kwargs: '{"results":[{"title":"Coucher de soleil","url":"https://images.exemple/photo.jpg","foreign_landing_url":"https://exemple/photo","license":"CC0","creator":"Test"}]}'
try:
    _images_test = _web34.rechercher_images_web("coucher de soleil")
finally:
    _web34._get = _ancien_get_images
verif("images : recherche et provenance", "photo.jpg" in _images_test and "CC0" in _images_test)
_statut_browser = _navigateur34.statut_browser_use()
verif("browser use : mode local sans API key",
      "sans API key" in _statut_browser and "Chrome local" in _statut_browser)
_signaux = _signaux34.collecter(force=True)
verif("signaux : état du PC collecté", "batterie" in _signaux and "documents" in _signaux)
_audit34.journaliser("test", "cible", resultat="ok")
verif("audit : chaîne d’événements vérifiable", _audit34.verifier_chaine()[0])
