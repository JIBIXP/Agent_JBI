# -*- coding: utf-8 -*-
"""Section 20 — documents PDF/Word réels — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

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
demande_cours = _demande_cours("fais un petit cours sur les tableaux de signes sous forme de document word")
verif("cours autonome avec titre détecté",
      demande_cours is not None and demande_cours["sujet"] == "les tableaux de signes"
      and demande_cours["format"] == "word")
verif("refaire un cours détecté",
      (_demande_cours("tu peux refaire le cours sur les tableaux de signes") or {}).get("sujet")
      == "les tableaux de signes")
verif("tableau autonome détecté",
      (_demande_tableau("cree un tableau Excel pour mon budget") or {}).get("format") == "excel")
verif("dessin emoji autonome détecté",
      (_demande_dessin("fais un dessin avec des emotifs") or {}).get("format") == "word")
# évasion de dossier toujours refusée via _chemin_espace
try:
    documents.creer_pdf("../malplace.pdf", "x", "y")
    verif("creer_pdf confiné à l'espace", False)
except ValueError:
    verif("creer_pdf confiné à l'espace", True)
fichier_pdf.unlink(missing_ok=True)
(config.DOSSIER_FICHIERS / "test_demo.docx").unlink(missing_ok=True)
