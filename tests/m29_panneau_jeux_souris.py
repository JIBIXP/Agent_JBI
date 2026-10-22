# -*- coding: utf-8 -*-
"""Section 27 — panneau web local, jeux, souris — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 27. Panneau web local, jeux, souris (adapté de Jarvis/panneau + souris)
import json as _json26  # noqa: E402
import urllib.error as _uerr26  # noqa: E402
import urllib.request as _ureq26  # noqa: E402

from interface import panneau as module_panneau  # noqa: E402
from outils.jeux import (  # noqa: E402
    lancer_un_de,
    nombre_mystere,
    pierre_feuille_ciseaux,
    pile_ou_face,
)
from outils.souris import _bornes, cliquer_souris, deplacer_souris  # noqa: E402


class _ClientFaux:
    modele = "faux-1b"
    def disponible(self):
        return True


class _AssistantFaux:
    client = _ClientFaux()

    class memoire:
        @staticmethod
        def session_courante():
            return 7

    def repondre(self, texte, **options):
        return {"reponse": "écho:" + texte, "actions": []}


_port_panneau = module_panneau.demarrer(_AssistantFaux(), port=0)
try:
    _page = _ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/").read().decode()
    verif("panneau : page HTML servie", "JIBI" in _page and "Envoyer" in _page)
    _demande = _ureq26.Request(
        f"http://127.0.0.1:{_port_panneau}/api/message",
        data=_json26.dumps({"texte": "bonjour panneau"}).encode(),
        headers={"Content-Type": "application/json"})
    _reponse = _json26.loads(_ureq26.urlopen(_demande).read())
    verif("panneau : échange de message", _reponse["reponse"] == "écho:bonjour panneau")
    _etat = _json26.loads(_ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/api/etat").read())
    verif("panneau : état", "modele" in _etat and "outils" in _etat, str(_etat)[:60])
    from jibi2 import progression as _progression26
    _progression26.demarrer("Test interface", "Analyse")
    _progression26.mettre(42, "Vérification")
    _progression = _json26.loads(
        _ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/api/progression").read())
    verif("panneau : jauge de progression exposée",
          _progression["pourcent"] == 42 and "Test interface" in _progression["titre"])
    _doc_interface = config.DOSSIER_FICHIERS / "document_interface.txt"
    _doc_interface.write_text("document téléchargeable", encoding="utf-8")
    _documents = _json26.loads(
        _ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/api/documents").read())
    verif("panneau : documents listés", any(x["nom"] == _doc_interface.name
                                             for x in _documents["documents"]))
    _telecharge = _ureq26.urlopen(
        f"http://127.0.0.1:{_port_panneau}/telecharger/{_doc_interface.name}").read()
    verif("panneau : bouton de téléchargement servi",
          _telecharge == "document téléchargeable".encode("utf-8"))
    _doc_interface.unlink(missing_ok=True)
    _progression26.terminer("test terminé")
    try:
        _ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/api/rien")
        verif("panneau : 404 sur route inconnue", False)
    except _uerr26.HTTPError as _e:
        verif("panneau : 404 sur route inconnue", _e.code == 404)
finally:
    module_panneau.arreter()
