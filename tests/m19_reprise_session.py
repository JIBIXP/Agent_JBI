# -*- coding: utf-8 -*-
"""Section 17 — reprise de session — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

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
historique_avant = list(asst_sess.histoire)
verif("suppression non courante conserve la conversation",
      asst_sess.supprimer_session(sid_b) and bd_sess.session_id == sid_a
      and asst_sess.histoire == historique_avant)
etat_avant = (bd_sess.session_id, list(asst_sess.histoire))
verif("suppression inconnue conserve l'état", not asst_sess.supprimer_session(999999998)
      and (bd_sess.session_id, asst_sess.histoire) == etat_avant)
supprimee = asst_sess.supprimer_session(sid_a)
verif("assistant supprime la session courante",
      supprimee and bd_sess.session_id is None and not asst_sess.histoire
      and not bd_sess.messages_de(sid_a))
bd_sess.fermer()
