# -*- coding: utf-8 -*-
"""Section 5 — mémoire SQLite — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 5. Mémoire SQLite
bd = memoire.Memoire(Path(tempfile.gettempdir()) / "jibi_test_memoire.db")
sid = bd.nouvelle_session("essai")
bd.ajouter_message("utilisateur", "bonjour")
bd.ajouter_message("jibi", "salut")
verif("messages persistés", len(bd.messages_de(sid)) == 2)
sid_supprime = bd.nouvelle_session("à supprimer")
bd.ajouter_message("utilisateur", "conversation à effacer")
verif("suppression session et messages", bd.supprimer_session(sid_supprime)
      and not bd.messages_de(sid_supprime)
      and not any(int(s) == sid_supprime for s, _t, _n in bd.lister_sessions(500)))
verif("suppression session inconnue refusée", not bd.supprimer_session(999999999))
n = bd.ajouter_note("acheter du pain")
verif("note ajoutée", any("pain" in t for _, t, _ in bd.lister_notes()))
verif("chercher_notes", bd.chercher_notes("pain"))
verif("supprimer_note", bd.supprimer_note(n) and not bd.chercher_notes("pain"))
bd.retenir("ville", "Rennes")
verif("retenir/rappeler", ("ville", "Rennes") in bd.rappeler("renn"))
bd.fermer()
