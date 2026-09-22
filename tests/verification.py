#!/usr/bin/env python3
"""Vérification hors-ligne de JIBI 2 : tout ce qui ne demande ni Ollama ni micro.

  python tests/verification.py    → compte les ✅ et les ❌ (exit 1 si ❌)
"""
from __future__ import annotations

import json as _json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

os.environ["CONFIRMER_RISQUES"] = "1"

from jibi2 import config, evolution, llm, memoire

config.preparer_dossiers()
from jibi2.assistant import Assistant, _extraire_json
from jibi2.securite import Garde
from outils import OUTILS, executer

stats = {"ok": 0, "ko": 0}


def verif(nom: str, condition: bool, detail: str = "") -> None:
    if condition:
        stats["ok"] += 1
        print(f"  ✅ {nom}")
    else:
        stats["ko"] += 1
        print(f"  ❌ {nom} {detail}")


print("── JIBI 2, vérification hors-ligne ─────────────")

# 1. Outils enregistrés
verif("au moins 30 outils enregistrés", len(OUTILS) >= 30, f"({len(OUTILS)})")
categories = {o.categorie for o in OUTILS.values()}
verif("au moins 8 catégories", len(categories) >= 8, str(sorted(categories)))
verif("outils à risque élevé bien étiquetés",
      {"executer_commande", "eteindre_pc"} <= {o.nom for o in OUTILS.values() if o.risque == "eleve"})

# 2. Calcul
r = executer("calculer", {"expression": "(12*7)/3 + sqrt(16)"}, Garde(lambda n, d: False))
verif("calculer", r["ok"] and "32" in r["texte"], r["texte"])
r = executer("calculer", {"expression": "__import__('os').system('x')"}, Garde(lambda n, d: False))
verif("calculer refuse l'injection", "impossible" in r["texte"], r["texte"])

# 3. Fichiers (espace de travail)
r = executer("ecrire_fichier", {"nom": "essai.txt", "contenu": "bonjour JIBI"}, Garde(lambda n, d: False))
verif("ecrire_fichier", r["ok"], r["texte"])
r = executer("lire_fichier", {"nom": "essai.txt"}, Garde(lambda n, d: False))
verif("lire_fichier", r["ok"] and "bonjour JIBI" in r["texte"], r["texte"])
r = executer("ecrire_fichier", {"nom": "../sortie.txt", "contenu": "x"}, Garde(lambda n, d: False))
verif("évasion de dossier refusée", not r["ok"], r["texte"])
r = executer("chercher_fichier", {"mot": "essai"}, Garde(lambda n, d: False))
verif("chercher_fichier", r["ok"] and "essai" in r["texte"])
r = executer("supprimer_fichier", {"nom": "essai.txt"}, Garde(lambda n, d: False))
verif("supprimer_fichier → corbeille", r["ok"] and "corbeille" in r["texte"])

# 4. Risque élevé : confirmation exigée puis refus
garde_refus = Garde(lambda nom, detail: False)
r = executer("executer_commande", {"commande": "echo test"}, garde_refus)
verif("action risquée bloquée sans accord", not r["ok"] and "refusé" in r["texte"])

# 5. Mémoire SQLite
bd = memoire.Memoire(Path(tempfile.gettempdir()) / "jibi_test_memoire.db")
sid = bd.nouvelle_session("essai")
bd.ajouter_message("utilisateur", "bonjour")
bd.ajouter_message("jibi", "salut")
verif("messages persistés", len(bd.messages_de(sid)) == 2)
n = bd.ajouter_note("acheter du pain")
verif("note ajoutée", any("pain" in t for _, t, _ in bd.lister_notes()))
verif("chercher_notes", bd.chercher_notes("pain"))
verif("supprimer_note", bd.supprimer_note(n) and not bd.chercher_notes("pain"))
bd.retenir("ville", "Rennes")
verif("retenir/rappeler", ("ville", "Rennes") in bd.rappeler("renn"))
bd.fermer()

# 6. Protocole JSON du cerveau
verif("JSON simple", _extraire_json('{"reponse": "coucou"}') == {"reponse": "coucou"})
verif("JSON avec balises code", _extraire_json('```json\n{"outil": "calculer"}\n```') == {"outil": "calculer"})
verif("JSON avec du texte autour", _extraire_json('Voici : {"reponse": "ok"} voilà.') == {"reponse": "ok"})
verif("non-JSON → None", _extraire_json("je ne sais pas") is None)
verif("nettoyer_think", llm.nettoyer_think("<think>hm</think>bonjour") == "bonjour")

# 7. Assistant : repli local sans Ollama
class ClientMort:
    def disponible(self): return False
    def discuter(self, m, temperature=0.4): raise llm.ErreurLLM("hors ligne")
bd2 = memoire.Memoire(Path(tempfile.gettempdir()) / "jibi_test_memoire2.db")
assistant = Assistant(bd2, Garde(lambda n, d: False))
assistant.client = ClientMort()
rep = assistant.repondre("quelle heure est-il ?")
verif("repli local heure", rep["ok"] and "Il est" in rep["reponse"], rep["reponse"])
rep = assistant.repondre("calcule 6*7")
verif("repli local calcul", "42" in rep["reponse"], rep["reponse"])
rep = assistant.repondre("explique-moi la vie")
verif("repli local message d'aide", not rep["ok"] and "Ollama" in rep["reponse"])

# 8. Amélioration : proposition refusée si dangereuse, validée sinon
retour = evolution.proposer_outil("outil_mechant", "import os\nos.system('dir')")
verif("proposition dangereuse refusée", "refusée" in retour, retour)
BON_CODE = ("from outils import outil\n"
            "@outil('compteur_lettres_test', 'Compte les lettres.', "
            "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
            "def compteur_lettres_test(texte):\n    return f'{len(texte)} lettres'\n")
retour = evolution.proposer_outil("compteur_lettres_test", BON_CODE)
verif("proposition saine enregistrée", "enregistrée" in retour, retour)
retour = evolution.valider("compteur_lettres_test")
verif("validation → perso", "validée" in retour, retour)
r = executer("compteur_lettres_test", {"texte": "abc"}, Garde(lambda n, d: False))
verif("outil perso exécutable", r["ok"] and "3" in r["texte"], r["texte"])
# nettoie l'outil de test
perso = Path(__file__).resolve().parent.parent / "outils" / "perso" / "compteur_lettres_test.py"
perso.unlink(missing_ok=True)
OUTILS.pop("compteur_lettres_test", None)

# 9. Auto-amélioration : détecter, analyser, proposer, valider, annuler
r = executer("outil_qui_nexiste_pas", {}, Garde(lambda n, d: False))
verif("outil inconnu → échec propre", not r["ok"])
journal = config.DOSSIER_JOURNAL / "erreurs.jsonl"
verif("échec noté au journal",
      journal.exists() and "outil_qui_nexiste_pas" in journal.read_text(encoding="utf-8"))
r = executer("lister_erreurs", {"mot": "outil_qui_nexiste_pas"}, Garde(lambda n, d: False))
verif("lister_erreurs retrouve l'échec", r["ok"] and "outil_qui_nexiste_pas" in r["texte"], r["texte"])
r = executer("lire_code_outil", {"nom": "calculer"}, Garde(lambda n, d: False))
verif("lire_code_outil montre la source", r["ok"] and "def calculer" in r["texte"], r["texte"])

# correction d'un outil perso : v1 puis v2, l'ancienne version part en historique
V1 = ("from outils import outil\n"
      "@outil('compteur_mots', 'Compte les mots.', "
      "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
      "def compteur_mots(texte):\n    return f\"{len(texte.split())} mots\"\n")
V2 = ("from outils import outil\n"
      "@outil('compteur_mots', 'Compte les mots, version 2.', "
      "{'texte': {'type': 'str', 'obligatoire': True}}, categorie='divers')\n"
      "def compteur_mots(texte):\n    return f\"V2 : {len(texte.split())} mots\"\n")
retour = evolution.proposer_outil("compteur_mots", V1)
verif("proposition v1 enregistrée", "enregistrée" in retour, retour)
verif("validation v1", "activée" in evolution.valider("compteur_mots"))
r = executer("compteur_mots", {"texte": "un deux trois"}, Garde(lambda n, d: False))
verif("compteur_mots v1 fonctionne", r["ok"] and "3 mots" in r["texte"], r["texte"])
evolution.proposer_outil("compteur_mots", V2)
evolution.valider("compteur_mots")
r = executer("compteur_mots", {"texte": "un deux trois"}, Garde(lambda n, d: False))
verif("v2 remplace v1", r["ok"] and "V2 : 3" in r["texte"], r["texte"])
historique = list((config.DOSSIER_DONNEES / "historique_outils").glob("compteur_mots.*.py"))
verif("ancienne version en historique", len(historique) >= 1, str(historique))

# masquage d'un outil intégré + restauration par /retirer
AVANT = OUTILS["calculer"].fonction
PIEGE = ("from outils import outil\n"
         "@outil('calculer', 'Version de test.', "
         "{'expression': {'type': 'str', 'obligatoire': True}}, categorie='calcul')\n"
         "def calculer(expression):\n    return 'version de test'\n")
evolution.proposer_outil("calculer", PIEGE)
retour = evolution.valider("calculer")
verif("proposition masque l'intégré",
      OUTILS["calculer"].fonction is not AVANT and "masque" in retour, retour)
retour = evolution.retirer("calculer")
verif("retrait restaure l'intégré", OUTILS["calculer"].fonction is AVANT, retour)
retour = evolution.retirer("compteur_mots")
verif("retrait d'un outil perso", "compteur_mots" not in OUTILS, retour)
verif("bilan donne les stats", "outils actifs" in evolution.bilan(), evolution.bilan())

# 10. Workflows (routines)
from outils import regler_services, workflows  # noqa: E402

regler_services(garde=Garde(lambda n, d: False))
retour = workflows.creer("test_wf", "essai", "pas du json")
verif("workflow JSON invalide refusé", "JSON" in retour, retour)
retour = workflows.creer("test_wf", "essai", _json.dumps([{"outil": "outil_inconnu"}]))
verif("workflow outil inconnu refusé", "n'existe pas" in retour, retour)
retour = workflows.creer("test_wf", "essai",
                         _json.dumps([{"outil": "calculer",
                                       "parametres": {"expression": "6*7"}},
                                      {"message": "bonjour"}]))
verif("workflow créé", "créé" in retour, retour)
retour = workflows.executer("test_wf")
verif("workflow exécuté (outil ok, message passé)", "1 ok" in retour and "42" in retour
      and "passée" in retour, retour)
verif("liste des workflows", "test_wf" in workflows.lister())
verif("workflow supprimé", "supprimé" in workflows.supprimer("test_wf"))

# 11. Streaming : assemblage + filtre <think> sur un faux serveur Ollama
import threading as _threading  # noqa: E402
from http.server import BaseHTTPRequestHandler as _H  # noqa: E402
from http.server import HTTPServer as _Srv

SCENARIOS = [[
    {"message": {"content": "Bon"}},
    {"message": {"content": "jour"}},
    {"message": {"content": " le monde"}, "done": True},
], [
    {"message": {"content": "<think>"}},
    {"message": {"content": "réflexion secrète"}},
    {"message": {"content": "</think>Salut !"}, "done": True},
]]
_reponses = {"boîte": 0}

class _FauxOllama(_H):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"models": [{"name": "qwen3.5:4b"}], "version": "0.12.3"}')

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.end_headers()
        for ligne in SCENARIOS[_reponses["boîte"]]:
            self.wfile.write((_json.dumps(ligne) + "\n").encode())
        _reponses["boîte"] += 1

_serveur = _Srv(("127.0.0.1", 11521), _FauxOllama)
_threading.Thread(target=_serveur.serve_forever, daemon=True).start()
client = llm.ClientLLM(url="http://127.0.0.1:11521", modele="qwen3.5:4b")
morceaux: list[str] = []
texte = client.discuter_stream([{"role": "user", "content": "x"}], on_chunk=morceaux.append)
verif("streaming assemblé", texte == "Bonjour le monde", repr(texte))
verif("streaming diffusé au fil de l'eau", "".join(morceaux) == "Bonjour le monde",
      repr(morceaux))
morceaux.clear()
texte = client.discuter_stream([{"role": "user", "content": "x"}], on_chunk=morceaux.append)
verif("bloc <think> filtré dans le flux", texte == "Salut !" and "".join(morceaux) == "Salut !",
      repr((texte, morceaux)))
_serveur.shutdown()

# 12. Le JSON de protocole ne doit jamais être diffusé à l'affichage
class ClientFluxJSON:
    def disponible(self):
        return True

    def discuter(self, messages, temperature=0.4):
        return '{"reponse": "texte final"}'

    def discuter_stream(self, messages, temperature=0.4, on_chunk=None):
        for morceau in ('{"re', 'ponse"', ': "voil\u00e0"}'):
            if on_chunk:
                on_chunk(morceau)
        return '{"reponse": "voil\u00e0"}'

assistant.client = ClientFluxJSON()
fuites: list[str] = []
rep = assistant.repondre("coucou", on_chunk=fuites.append)
verif("JSON de protocole tu (pas de fuite dans le flux)", fuites == [] and rep["reponse"] == "voilà",
      repr((fuites, rep["reponse"])))

class ClientFluxTexte:
    """1er appel : texte brut (hors protocole) → relance ; 2e : JSON muet."""

    def __init__(self):
        self.appel = 0

    def disponible(self):
        return True

    def discuter(self, messages, temperature=0.4):
        return '{"reponse": "bien reçu !"}'

    def discuter_stream(self, messages, temperature=0.4, on_chunk=None):
        self.appel += 1
        morceaux = ("Réponse ", "finale ", "claire.") if self.appel == 1 \
            else ('{"reponse": "bien reçu !"}',)
        for morceau in morceaux:
            if on_chunk:
                on_chunk(morceau)
        return "".join(morceaux)

assistant.client = ClientFluxTexte()
fuites.clear()
rep = assistant.repondre("coucou", on_chunk=fuites.append)
verif("texte diffusé au fil de l'eau, relance muette",
      "".join(fuites) == "Réponse finale claire." and rep["reponse"] == "bien reçu !",
      repr((fuites, rep["reponse"])))

# 13. Laboratoire (bac à sable, risque, intégrité, changelog)
from jibi2 import labo  # noqa: E402

CODE_RISQUE_FAIBLE = "from outils import outil\n@outil('a', 'A.', {}, categorie='divers')\ndef a():\n    return 1\n"
verif("évaluation de risque (faible)",
      labo.evaluer_risque(CODE_RISQUE_FAIBLE)[0] == "faible", str(labo.evaluer_risque(CODE_RISQUE_FAIBLE)))
verif("évaluation de risque (élevé)",
      labo.evaluer_risque("import subprocess\nx = 1\n")[0] == "eleve")
CODE_SYNTAX_CASSÉE = ("from outils import outil\n"
                      "@outil('outil_casse', 'Cassé.', {}, categorie='divers')\n"
                      "def outil_casse(:\n    return 1\n")
retour = evolution.proposer_outil("outil_casse", CODE_SYNTAX_CASSÉE)
verif("proposition à erreur de syntaxe acceptée au dépôt", "enregistrée" in retour, retour)
verdict = labo.tester_proposition("outil_casse")
verif("bac à sable rejette l'erreur de syntaxe",
      not verdict["ok"] and "SYNTAXE" in verdict["resume"], verdict["resume"])
BON = ("from outils import outil\n"
       "@outil('ajoute_deux', 'Ajoute 2.', "
       "{'nombre': {'type': 'int', 'obligatoire': True}}, categorie='calcul')\n"
       "def ajoute_deux(nombre):\n    return nombre + 2\n")
retour = evolution.proposer_outil("ajoute_deux", BON)
verif("bonne proposition enregistrée avec risque", "risque faible" in retour, retour)
verdict = labo.tester_proposition("ajoute_deux")
verif("bac à sable valide le bon outil",
      verdict["ok"] and "risque faible" in verdict["resume"], verdict["resume"])
# intégrité : on trafique le fichier après test → validation refusée
chemin = config.DOSSIER_PROPOSITIONS / "ajoute_deux.py"
chemin.write_text(chemin.read_text(encoding="utf-8") + "\n# trafiqué\n", encoding="utf-8")
retour = evolution.valider("ajoute_deux")
verif("fichier trafiqué → validation refusée (SHA-256)", "CHANGÉ" in retour, retour)
# version propre re-testée puis validée → outil actif + changelog
evolution.proposer_outil("ajoute_deux", BON)
labo.tester_proposition("ajoute_deux")
retour = evolution.valider("ajoute_deux")
verif("validation après test OK", "activé" in retour and "Test bac à sable" in retour, retour)
r = executer("ajoute_deux", {"nombre": 5}, Garde(lambda n, d: False))
verif("outil validé fonctionne", r["ok"] and "7" in r["texte"], r["texte"])
changelog = (config.RACINE / "CHANGELOG.md")
verif("CHANGELOG tenu à jour", changelog.exists() and "ajoute_deux" in changelog.read_text(encoding="utf-8"))
perso_aj = Path(__file__).resolve().parent.parent / "outils" / "perso" / "ajoute_deux.py"
perso_aj.unlink(missing_ok=True)
OUTILS.pop("ajoute_deux", None)
# risque élevé refusé dès la proposition
MAUVAIS = "import subprocess\n" + ("x = 1\n" * 50)
retour = evolution.proposer_outil("trop_lourd", MAUVAIS)
verif("risque élevé refusé à la proposition", "refusée" in retour, retour)
# lancement de la suite interne (sur un mini-script, pas récursif)
evolution_ch = Path(tempfile.gettempdir()) / "mini_verif.py"
evolution_ch.write_text("print('1/1 OK')\n", encoding="utf-8")
import subprocess as _sub  # noqa: E402

fait = _sub.run([sys.executable, str(evolution_ch)], capture_output=True, text=True)
verif("lancer_verification : sous-processus OK", fait.returncode == 0 and "1/1" in fait.stdout)

# 14. Workflows programmés (horaire)
from jibi2 import planificateur  # noqa: E402

workflows.creer("routine_horo", "test horaire",
                _json.dumps([{"outil": "heure_actuelle", "parametres": {}}]), "07:41")
programmes = planificateur.workflows_programmes()
verif("workflow programmé listé", ("routine_horo", "07:41") in programmes, str(programmes))
retour = workflows.creer("routine_horo2", "x",
                         _json.dumps([{"outil": "heure_actuelle", "parametres": {}}]), "7h99")
verif("horaire invalide refusé", "invalide" in retour, retour)
workflows.supprimer("routine_horo")

# 15. Analyse du code du projet (auto-contrôle)
from jibi2.labo import verifier_code_projet  # noqa: E402

bilan_code = verifier_code_projet()
verif("analyse du code de JIBI", "tout compile" in bilan_code and "fichiers" in bilan_code,
      bilan_code[:120])

# 16. Wake-word : repli propre sans openwakeword
from audio import wake  # noqa: E402

verif("wake neuronal : repli propre (non installé)", wake.disponible() is False
      and wake.ecouter_mot() is False)

# 17. Reprise de session
bd_sess = memoire.Memoire(Path(tempfile.gettempdir()) / "jibi_test_sessions.db")
sid_a = bd_sess.nouvelle_session("gâteau au chocolat")
bd_sess.ajouter_message("utilisateur", "donne une recette de gâteau")
bd_sess.ajouter_message("jibi", "Beurre, œufs, farine, chocolat…")
sid_b = bd_sess.nouvelle_session("autre sujet")
bd_sess.ajouter_message("utilisateur", "bonjour")
verif("sessions distinctes", sid_a != sid_b)
messages = bd_sess.charger_session(sid_a)
verif("charger_session change de session courante",
      messages and messages[0][1].startswith("donne") and bd_sess.session_id == sid_a)
verif("charger_session : session inconnue", bd_sess.charger_session(999) is None)
asst_sess = Assistant(bd_sess, Garde(lambda n, d: False))
retour = asst_sess.reprendre(sid_a)
verif("assistant.reprendre restaure l'histoire",
      "reprise" in retour and len(asst_sess.histoire) == 2
      and asst_sess.histoire[0]["content"].startswith("donne"), retour)
verif("reprendre une session inconnue", "introuvable" in asst_sess.reprendre(999))
bd_sess.fermer()

# 18. Dictée en continu (segments simulés, mot final « envoie »)
from audio import ecoute  # noqa: E402

SEGMENTS = iter(["écris un petit mot pour demain", "n'oublie pas le pain",
                 "envoie"])
ecoute.ecouter_phrase = lambda **params: next(SEGMENTS)
recus_partiels: list[str] = []
texte_dicte = ecoute.dicter(mot_fin="envoie", on_partiel=recus_partiels.append)
verif("dictée : texte cumulé sans le mot final",
      texte_dicte == "écris un petit mot pour demain n'oublie pas le pain",
      repr(texte_dicte))
verif("dictée : partiels diffusés", len(recus_partiels) == 2, str(recus_partiels))
SEGMENTS = iter(["juste ça", "envoie"])
verif("dictée courte", ecoute.dicter() == "juste ça")

# 19. Wake-word : modèle officiel référencé, repli propre sans paquet
from audio import wake  # noqa: E402

verif("modèle wake officiel déclaré", "hey_jarvis" in wake.MODELES_OFFICIELS.get("jarvis", ""))
verif("wake inconnu refusé", "inconnu" in wake.telecharger("jibi_inexistant"))

# 20. Documents : PDF et Word réels (sans dépendance)
from outils import documents  # noqa: E402

retour = documents.creer_pdf("test_demo.pdf", "Mon titre accentué éàç",
                             "Première ligne avec des accents : éèêàç\nDeuxième ligne (avec parenthèses)")
verif("creer_pdf", "PDF créé" in retour, retour)
fichier_pdf = config.DOSSIER_FICHIERS / "test_demo.pdf"
brut = fichier_pdf.read_bytes()
verif("structure PDF valide", brut.startswith(b"%PDF") and b"xref" in brut
      and brut.rstrip().endswith(b"%%EOF") and len(brut) > 500)
import zipfile as _zip  # noqa: E402

retour = documents.creer_word("test_demo.docx", "Rapport important",
                              "Paragraphe un\\nParagraphe deux : 100% <valid>")
verif("creer_word", "Word créé" in retour, retour)
archive = _zip.ZipFile(config.DOSSIER_FICHIERS / "test_demo.docx")
verif("docx = zip valide avec document.xml",
      archive.testzip() is None and "word/document.xml" in archive.namelist())
archive.close()
# évasion de dossier toujours refusée via _chemin_espace
try:
    documents.creer_pdf("../malplace.pdf", "x", "y")
    verif("creer_pdf confiné à l'espace", False)
except ValueError:
    verif("creer_pdf confiné à l'espace", True)
fichier_pdf.unlink(missing_ok=True)
(config.DOSSIER_FICHIERS / "test_demo.docx").unlink(missing_ok=True)

# 21. Chrome : recherche de binaire (sans lancer de navigateur)
from outils.applications import _trouver_chrome  # noqa: E402

verif("recherche Chrome/Edge renvoie une chaîne ou None",
      _trouver_chrome() is None or Path(_trouver_chrome()).exists())

# 22. Notifications : outil enregistré, canal terminal fonctionnel ici
from outils import notifications  # noqa: E402

retour = notifications.notifier("JIBI test", "coucou du test")
verif("notifier répond", "notification" in retour.lower(), retour)
verif("dernière notification mémorisée", notifications.derniere == ["JIBI test", "coucou du test"])

# 23. keep_alive : lecture du réglage
from jibi2.llm import _keep_alive  # noqa: E402

_valeur_keep = _keep_alive()
verif("keep_alive lu du .env", _valeur_keep == -1 or
      (isinstance(_valeur_keep, str) and _valeur_keep.endswith(("m", "h"))),
      str(_valeur_keep))

# 24. Jeu d'outils adaptatif (leçon Jarvis : petit modèle + 47 outils = noyade)
from outils import NOYAU, catalogue_pour_llm, outils_pour_message  # noqa: E402

base = outils_pour_message("bonjour")
verif("noyau du quotidien toujours montré", set(base) >= NOYAU and len(base) < 25, f"{len(base)} outils")
etendu = outils_pour_message("éteins le PC et regarde mon écran")
verif("extension par mots-clés", {"eteindre_pc", "voir_ecran"} <= set(etendu))
complet = catalogue_pour_llm()
filtre = catalogue_pour_llm(outils_pour_message("quelle heure est-il ?"))
verif("catalogue filtré ~2× plus court", 0 < len(filtre) < len(complet) // 2, f"{len(filtre)}/{len(complet)} car.")
verif("filtrage respecté", "voir_ecran" not in filtre and "heure_actuelle" in filtre)

# 25. Assistance Chrome (CDP factice) + lumière amaran (pont factice)
import json as _js  # noqa: E402
import socket as _socket  # noqa: E402
import threading as _threading  # noqa: E402
import urllib.parse as _uparse  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402

import outils.amaran as module_amaran  # noqa: E402
import outils.chrome as module_chrome  # noqa: E402

_page_html = "<html><body><h1>Test Godox TL60</h1><p>Le TL60 coute 139 euros.</p></body></html>"
_cdp_onglets: list = []
_capte = {"route": "", "corps": {}}


class _FauxCDP(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _envoyer(self, corps, contenu="application/json"):
        if isinstance(corps, bytes):
            brut = corps
        else:
            brut = (_js.dumps(corps) if not isinstance(corps, str) else corps).encode()
        self.send_response(200)
        self.send_header("Content-Type", contenu)
        self.send_header("Content-Length", str(len(brut)))
        self.end_headers()
        self.wfile.write(brut)

    def do_GET(self):
        if self.path == "/json/version":
            self._envoyer({"Browser": "Chrome/150"})
        elif self.path == "/json/list":
            self._envoyer(_cdp_onglets)
        elif self.path.startswith("/json/activate/"):
            self._envoyer("Target activated", "text/plain")
        elif self.path.startswith("/json/close/"):
            self._envoyer("Target is closing", "text/plain")
        elif self.path.startswith("/page"):
            self._envoyer(_page_html, "text/html; charset=utf-8")
        else:
            self._envoyer({})

    def do_PUT(self):
        if self.path.startswith("/json/new"):
            url = _uparse.unquote(self.path.split("url=", 1)[1])
            self._envoyer({"id": "N9", "type": "page", "title": "Nouvel onglet", "url": url})


class _FauxPont(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        _capte["route"] = self.path
        _capte["corps"] = _js.loads(self.rfile.read(n) or b"{}")
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


_serveur = HTTPServer(("127.0.0.1", 0), _FauxCDP)
_port_cdp = _serveur.server_address[1]
_pont_http = HTTPServer(("127.0.0.1", 0), _FauxPont)
_port_pont = _pont_http.server_address[1]
_cdp_onglets.extend([
    {"id": "A1", "type": "page", "title": "Test du Godox TL60",
     "url": f"http://127.0.0.1:{_port_cdp}/page"},
    {"id": "A2", "type": "page", "title": "Documentation", "url": "https://exemple.fr/docs"},
    {"id": "D1", "type": "page", "title": "DevTools", "url": "devtools://devtools/inspector.html"},
])
for _s in (_serveur, _pont_http):
    _threading.Thread(target=_s.serve_forever, daemon=True).start()

_base_orig, _pont_orig = module_chrome._base, module_amaran._pont
_prise = _socket.socket()
_prise.bind(("127.0.0.1", 0))
_port_mort = _prise.getsockname()[1]
_prise.close()
try:
    module_chrome._base = lambda: f"http://127.0.0.1:{_port_cdp}"
    _liste = module_chrome.lister_onglets()
    verif("onglets listés (devtools filtré)",
          "2 onglet" in _liste and "Documentation" in _liste, _liste.splitlines()[0])
    verif("onglet ouvert via /json/new", "Nouvel onglet" in module_chrome.ouvrir_onglet("youtube.com"))
    verif("onglet activé par mot", "Documentation" in module_chrome.activer_onglet("documentation"))
    verif("onglet fermé par numéro", "fermé" in module_chrome.fermer_onglet("2"))
    _lu = module_chrome.lire_onglet_actif()
    verif("page active lue (texte extrait)",
          _lu.startswith("Onglet actif :") and "TL60" in _lu, _lu[:40])
    module_chrome._base = lambda: f"http://127.0.0.1:{_port_mort}"
    verif("Chrome absent → message clair", "CHROME_JIBI.bat" in module_chrome.lister_onglets())

    module_amaran._pont = lambda: f"http://127.0.0.1:{_port_pont}"
    verif("amaran allumer → /lights/all/on",
          module_amaran.controler_amaran("allumer") == "Lumière allumée."
          and _capte["route"] == "/lights/all/on")
    module_amaran.controler_amaran("luminosite", valeur=75)
    verif("amaran luminosite → brightness {value}",
          _capte["route"] == "/lights/all/brightness" and _capte["corps"] == {"value": 75})
    module_amaran.controler_amaran("couleur", teinte=200, valeur=80)
    verif("amaran couleur → hsi", _capte["route"] == "/lights/all/hsi" and _capte["corps"]["hue"] == 200)
    verif("amaran action inconnue signalée", "inconnue" in module_amaran.controler_amaran("changer"))
    module_amaran._pont = _pont_orig
    verif("amaran non configuré → mode d'emploi",
          "JIBI_AMARAN_URL" in module_amaran.controler_amaran("allumer"))
    module_amaran._pont = lambda: f"http://127.0.0.1:{_port_mort}"
    verif("amaran injoignable → message clair", "injoignable" in module_amaran.controler_amaran("allumer"))
finally:
    module_chrome._base, module_amaran._pont = _base_orig, _pont_orig
    _serveur.shutdown()
    _serveur.server_close()
    _pont_http.shutdown()
    _pont_http.server_close()

# 26. Panneau web local, jeux, souris (adapté de Jarvis/panneau + souris)
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
    try:
        _ureq26.urlopen(f"http://127.0.0.1:{_port_panneau}/api/rien")
        verif("panneau : 404 sur route inconnue", False)
    except _uerr26.HTTPError as _e:
        verif("panneau : 404 sur route inconnue", _e.code == 404)
finally:
    module_panneau.arreter()

_de = lancer_un_de()
_faces = int(_de.split("faces donne")[1].strip().rstrip("."))
verif("jeu : dé dans les bornes", 1 <= _faces <= 6, _de)
verif("jeu : pile ou face", pile_ou_face().split()[1].rstrip("!") in ("Pile", "Face"))
_verdicts = [pierre_feuille_ciseaux("pierre") for _ in range(3)]   # 3 essais : test relançable
verif("jeu : chifoumi répond un verdict",
      any(m in _v for _v in _verdicts for m in ("égalité", "gagnes", "gagne")),
      _verdicts[0][:40])
nombre_mystere("commencer")
module_jeux_etat = nombre_mystere
import outils.jeux as _module_jeux  # noqa: E402

_module_jeux._MYSTERE["cible"] = 50
_module_jeux._MYSTERE["essais"] = 0
verif("jeu : mystère trop grand", "PLUS PETIT" in nombre_mystere("deviner", 60))
verif("jeu : mystère gagné", "Bravo" in nombre_mystere("deviner", 50)
      and not _module_jeux._MYSTERE)

verif("souris : réservée à Windows ici", "Windows" in deplacer_souris(50, 50)
      and "Windows" in cliquer_souris())
verif("souris : pourcentages bornés", _bornes(-5) == 0 and _bornes(150) == 100)

# 27. Voie rapide : réponses instantanées sans passer par le modèle
import time as _time27  # noqa: E402

import outils.jeux as _jeux27  # noqa: E402
from jibi2.assistant import _voie_rapide  # noqa: E402
from jibi2.securite import Garde as _Garde27  # noqa: E402

_garde27 = _Garde27()
_voie_rapide("pile ou face", _garde27)          # échauffement (premiers imports)
_t0 = _time27.perf_counter()
_r = _voie_rapide("Quelle heure est-il ?", _garde27)
_duree = _time27.perf_counter() - _t0
verif("voie rapide : heure instantanée", _r is not None and _r["ok"] and _duree < 0.5,
      f"{_duree * 1000:.0f} ms")
verif("voie rapide : jour capté", _voie_rapide("quel jour est-on ?", _garde27) is not None)
_de = _voie_rapide("lance un dé à 20 faces", _garde27)
verif("voie rapide : dé à 20 faces", _de is not None and "20 faces" in _de["reponse"])
_pf = _voie_rapide("pile ou face", _garde27)
verif("voie rapide : pile ou face", _pf is not None and ("Pile" in _pf["reponse"] or "Face" in _pf["reponse"]))
verif("voie rapide : chifoumi",
      _voie_rapide("on joue à pierre feuille ciseaux, je joue feuille", _garde27) is not None)
_jeux27._MYSTERE["cible"] = 50
_jeux27._MYSTERE["essais"] = 0
_m = _voie_rapide("c'est 50 ?", _garde27)
verif("voie rapide : essai du nombre mystère", _m is not None and "Bravo" in _m["reponse"])
verif("voie rapide : calcul direct",
      "408" in (_voie_rapide("calcule 12*34", _garde27)["reponse"]))
verif("voie rapide : le passé passe par le modèle",
      _voie_rapide("quelle heure était-il hier ?", _garde27) is None)
verif("voie rapide : pas de faux positif",
      _voie_rapide("mets une alarme dans une heure", _garde27) is None
      and _voie_rapide("rappelle-moi dans 2 minutes", _garde27) is None)

# 28. Version & mise à jour (honnête : pas d'auto-update du noyau)
from outils.systeme import _version_locale, verifier_mise_a_jour  # noqa: E402

_ver = _version_locale()
verif("fichier VERSION lisible", _ver != "inconnue" and "ADD" in _ver, _ver)
_message = verifier_mise_a_jour()
verif("mise à jour : position honnête annoncée",
      _ver in _message and "PAS automatique" in _message)
verif("mise à jour : procédure de sauvegarde rappelée",
      "donnees/" in _message and "modeles/voix" in _message)

# 29. Autonomie graduée : design libre, outils auto-activés, noyau sur permission
from interface.panneau import _page_html  # noqa: E402
from outils.design import personnaliser_design, style_panneau  # noqa: E402

verif("design : couleur appliquée",
      "Appliqué" in personnaliser_design("panneau.accent", "#12aa55"))
verif("design : injecté dans la page du panneau", "#12aa55" in _page_html().decode())
verif("design : valeur invalide refusée",
      "hex" in personnaliser_design("panneau.accent", "rouge"))
verif("design : clé inconnue refusée",
      "inconnu" in personnaliser_design("orbe.nuit", "#111111, #222222, #333333"))
verif("design : reset", "origine" in personnaliser_design("reset", "") and style_panneau() == "")

from jibi2 import evolution as _evo29  # noqa: E402
from jibi2.labo import tester_proposition as _tester29  # noqa: E402

_CODE29 = '''"""Outil posé par JIBI lui-même (test autonomie)."""
from outils import outil


@outil("outil_auto29", "Outil de test posé par JIBI seul.",
       {"texte": {"type": "str", "obligatoire": True,
                  "description": "texte à renvoyer"}},
       categorie="calcul", risque="faible", exemple="")
def outil_auto29(texte: str) -> str:
    return "écho29:" + texte
'''
_evo29.proposer_outil("outil_auto29", _CODE29)
tester_ok = _tester29("outil_auto29")
from jibi2.securite import Garde as _Garde29  # noqa: E402
from outils import executer as _exec29  # noqa: E402

_g29 = _Garde29()
_g29.confirmer = lambda nom, detail: False      # par défaut : TOUT refuser
_activation = _exec29("activer_proposition", {"nom": "outil_auto29"}, _g29)
verif("autonomie : JIBI active sa proposition seul",
      _activation["ok"] and "outil_auto29" in _activation["texte"])
_echo = _exec29("outil_auto29", {"texte": "ça marche"}, _g29)
verif("autonomie : l'outil auto-activé fonctionne", _echo["ok"] and "écho29" in _echo["texte"])
_evo29.retirer("outil_auto29")

# noyau : permission demandée (risque élevé → la garde bloque d'abord)
_refus = _exec29("modifier_noyau", {"fichier": "jibi2/assistant.py", "contenu": "x = 1"}, _g29)
verif("noyau : bloqué si l'utilisateur refuse", "refusé" in _refus["texte"])
_g29.confirmer = lambda nom, detail: True          # l'utilisateur dit oui
_piece = Path("tests/_piece_test29.py")
_ok = _exec29("modifier_noyau", {"fichier": "tests/_piece_test29.py",
                                 "contenu": "PIECE29 = 'ok'\n", "verifier": False}, _g29)
verif("noyau : création acceptée avec permission", _ok["ok"] and _piece.exists())
_casse = _exec29("modifier_noyau", {"fichier": "tests/_piece_test29.py",
                                    "contenu": "def casse(:\n", "verifier": False}, _g29)
verif("noyau : syntaxe cassée refusée avant écriture",
      not _casse["ok"] and _piece.read_text() == "PIECE29 = 'ok'\n")
_verrou = _exec29("modifier_noyau", {"fichier": ".env", "contenu": "x", "verifier": False}, _g29)
_travers = _exec29("modifier_noyau", {"fichier": "../.env", "contenu": "x",
                                      "verifier": False}, _g29)
verif("noyau : .env et traversée interdits",
      "jamais modifiable" in _verrou["texte"] and "refusé" in _travers["texte"])
_piece.unlink(missing_ok=True)

# 30. Voix au choix (dont masculine) + parole au fil de l'eau
from audio import parole as _parole30  # noqa: E402
from outils.voix import _ecrire_env, changer_voix  # noqa: E402

verif("voix : catalogue avec voix masculine",
      "tom" in _parole30.CATALOGUE_VOIX
      and _parole30.CATALOGUE_VOIX["tom"]["sexe"] == "homme")
_onnx, _json = _parole30.url_modele("tom")
verif("voix : URL officielle Piper", _onnx.endswith("fr_FR-tom-medium.onnx")
      and "rhasspy/piper-voices" in _onnx)
_liste = changer_voix("")
verif("voix : listage avec sexe", "tom (homme" in _liste and "siwis (femme" in _liste)
verif("voix : nom inconnu refusé", "inconnue" in changer_voix("skynet"))
verif("voix : découpage en phrases",
      _parole30.extraire_phrases("Salut ! Je parle") == (["Salut !"], "Je parle"))
verif("voix : phrase inachevée gardée en tampon",
      _parole30.extraire_phrases("une phrase sans point") == ([], "une phrase sans point"))

_dit30: list[str] = []
_orig30 = _parole30.parler
_parole30.parler = lambda t, attendre=False: _dit30.append(t) or True
try:
    _lec = _parole30.LecteurPhrases()
    _lec.alimenter("Bonjour ! Je parle")
    _lec.alimenter(" dès que la phrase est prête.")
    _lec.terminer()
    _lec.attendre()
    verif("voix : phrases dites au fil de l'eau, dans l'ordre",
          _dit30 == ["Bonjour !", "Je parle dès que la phrase est prête."], str(_dit30))
    _dit30.clear()
    _lec2 = _parole30.LecteurPhrases()
    _lec2.alimenter("Une phrase complète. Le reste ne sera jamais dit.")
    _lec2.couper()
    _lec2.attendre()
    verif("voix : couper stoppe la file", _dit30 == ["Une phrase complète."], str(_dit30))
finally:
    _parole30.parler = _orig30

_env_avant = (Path(".env").read_text(encoding="utf-8"), Path(".env").stat().st_size)
_ecrire_env("PIPER_MODELE", "essai")
_ecrire_env("PIPER_MODELE", "")
_apres = Path(".env").read_text(encoding="utf-8")
verif("voix : .env réécrit proprement (rien de perdu)",
      _apres == _env_avant[0] and Path(".env").stat().st_size == _env_avant[1])

# 31. Vitesse CPU : plafonds de génération + historique compressé (prefill)
from docteur import bench_vitesse  # noqa: E402, F401  (importable sans Ollama)
from jibi2 import llm as module_llm  # noqa: E402

_orig_valeur = module_llm.config.valeur
module_llm.config.valeur = lambda cle, defaut="": {
    "JIBI_LLM_MAX": "77", "JIBI_LLM_CTX": "2048"}.get(cle, defaut)
try:
    verif("llm : plafond et contexte lus du réglage",
          module_llm._plafond() == 77 and module_llm._contexte() == 2048)
finally:
    module_llm.config.valeur = _orig_valeur
verif("llm : défauts bornés", module_llm._plafond() == 600 and module_llm._contexte() == 4096)
_corps = module_llm.ClientLLM(url="http://127.0.0.1:1")._corps(
    [{"role": "user", "content": "x"}], 0.4, stream=False)
verif("llm : requête plafonnée (num_predict, num_ctx, keep_alive)",
      _corps["options"]["num_predict"] == 600 and _corps["options"]["num_ctx"] == 4096
      and "keep_alive" in _corps)

_grosse = "[Résultat de l'outil lire_page_web] " + "page " * 500
assistant.histoire = [
    {"role": "user", "content": "résume la page"},
    {"role": "user", "content": _grosse},
    {"role": "assistant", "content": "Résumé."},
    {"role": "user", "content": "et celle-ci ?"},
    {"role": "user", "content": _grosse},
    {"role": "assistant", "content": "Résumé 2."},
    {"role": "user", "content": "merci"},
]
_messages31 = assistant._messages()
vieux = [m for m in _messages31[1:-2] if m["content"].startswith("[Résultat")]
verif("vitesse : vieux résultats d'outils compressés",
      all(len(m["content"]) <= 230 for m in vieux) and len(vieux) >= 1)
verif("vitesse : /no_think en fin de prompt système",
      _messages31[0]["content"].rstrip().endswith("/no_think"))
assistant.histoire = []
assistant._ajouter("user", "x" * 4000)
verif("vitesse : aucun message d'historique > 1 500 car.",
      all(len(m["content"]) <= 1500 for m in assistant.histoire))
assistant.histoire = []

# 32. Bench & adoption de modèle (l'éditeur .env du docteur)
from docteur import _ecrire_env  # noqa: E402

_avant32 = Path(".env").read_text(encoding="utf-8")
try:
    _ecrire_env("JIBI_TEST_BENCH", "v1")
    _ecrire_env("JIBI_TEST_BENCH", "v2")
    _entre = Path(".env").read_text(encoding="utf-8")
    verif("docteur : .env édité proprement (1 ligne, rien de perdu)",
          "JIBI_TEST_BENCH=v2" in _entre and _entre.count("JIBI_TEST_BENCH") == 1
          and "JIBI_HISTOIRE=6" in _entre)
finally:
    Path(".env").write_text(_avant32, encoding="utf-8")
verif("docteur : .env restauré à l'identique",
      Path(".env").read_text(encoding="utf-8") == _avant32)
verif("docteur : bench importable", callable(_ecrire_env))

# 33. Chaîne « apprendre sur le web → s'améliorer » complète et enseignée
import outils as _module_outils33  # noqa: E402
from jibi2.assistant import SYSTEME as _SYSTEME33  # noqa: E402

verif("web→amélioration : comportement enseigné au modèle",
      "t'instruire sur le WEB" in _SYSTEME33
      and "proposer_nouvel_outil" in _SYSTEME33)
verif("web→amélioration : toute la chaîne d'outils enregistrée",
      {"rechercher_web", "lire_page_web", "proposer_nouvel_outil",
       "tester_proposition", "activer_proposition",
       "modifier_noyau"} <= set(_module_outils33.lister_noms()))

print("────────────────────────────────────────────────")
print(f"{stats['ok']}/{stats['ok'] + stats['ko']} OK")
raise SystemExit(1 if stats["ko"] else 0)
