"""Outils documents de JIBI 2 : créer de vrais PDF et fichiers Word.

100 % Python standard : pas de dépendance. Le PDF est écrit à la main
(format minimal, Helvetica, accents gérés) ; le Word (.docx) est un
petit zip XML valide, ouvert par Word, LibreOffice et Google Docs.
Tout atterrit dans l'espace de travail (donnees/fichiers).
"""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape as xml_echap

from outils import outil


def _vers_latin1(texte: str) -> str:
    return texte.encode("cp1252", errors="replace").decode("cp1252")


def _echapper_pdf(texte: str) -> str:
    return (_vers_latin1(texte).replace("\\", r"\\")
            .replace("(", r"\(").replace(")", r"\)"))


def _construire_pdf(titre: str, lignes: list[str]) -> bytes:
    """Assemble un PDF minimal d'une page (A5 paysage large : 842x595 ? non : A4 595x842)."""
    morceaux_contenu = ["BT", "/F1 16 Tf", "50 800 Td", f"({_echapper_pdf(titre)}) Tj", "ET"]
    y = 770
    for ligne in lignes:
        # coupe les lignes trop longues (~95 caractères par ligne en 11 pt)
        reste = ligne
        while reste:
            morceaux_contenu += ["BT", "/F1 11 Tf", f"50 {y} Td",
                                 f"({_echapper_pdf(reste[:95])}) Tj", "ET"]
            reste = reste[95:]
            y -= 15
            if y < 40:
                break
        y -= 15
        if y < 40:
            break
    flux = "\n".join(morceaux_contenu).encode("cp1252", errors="replace")

    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(flux)).encode() + b" >>\nstream\n" + flux + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, objet in enumerate(objets, 1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + objet + b"\nendobj\n"
    debut_xref = len(pdf)
    pdf += f"xref\n0 {len(objets) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for decale in offsets[1:]:
        pdf += f"{decale:010d} 00000 n \n".encode()
    pdf += (f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\n"
            f"startxref\n{debut_xref}\n%%EOF\n").encode()
    return bytes(pdf)


def _construire_docx(titre: str, lignes: list[str]) -> bytes:
    paragraphes = ["<w:p><w:r><w:rPr><w:b/><w:sz w:val=\"32\"/></w:rPr>"
                   f"<w:t xml:space=\"preserve\">{xml_echap(titre)}</w:t></w:r></w:p>"]
    for ligne in lignes:
        paragraphes.append("<w:p><w:r><w:t xml:space=\"preserve\">"
                           f"{xml_echap(ligne)}</w:t></w:r></w:p>")
    document = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>" + "".join(paragraphes) +
        "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/></w:sectPr></w:body></w:document>")
    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>")
    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>")
    import io
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return tampon.getvalue()


def _couper(texte: str) -> list[str]:
    """Découpe le contenu fourni en lignes (les \n sont respectés)."""
    return [li for li in (texte or "").replace("\r\n", "\n").split("\n")]


@outil("creer_pdf", "Crée un VRAI fichier PDF (ouvert par n'importe quel lecteur) dans l'espace de travail.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier, ex. compte_rendu.pdf"},
        "titre": {"type": "str", "obligatoire": True, "description": "titre du document"},
        "contenu": {"type": "str", "obligatoire": True,
                    "description": "texte du document ; une ligne par paragraphe (retours à la ligne acceptés)"}},
       categorie="documents", risque="moyen",
       exemple='{"outil": "creer_pdf", "parametres": {"nom": "liste_courses.pdf", '
               '"titre": "Liste de courses", "contenu": "Pain\\nLait\\nChocolat"}}')
def creer_pdf(nom: str, titre: str, contenu: str) -> str:
    nom = nom.strip()
    if not nom.lower().endswith(".pdf"):
        nom += ".pdf"
    from outils.fichiers import _chemin_espace
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(_construire_pdf(titre, _couper(contenu)))
    return (f"PDF créé : {chemin.name} ({chemin.stat().st_size} octets, "
            f"{len(_couper(contenu))} ligne(s)).")


@outil("creer_word", "Crée un VRAI fichier Word (.docx, ouvert par Word/LibreOffice/Google Docs) "
                     "dans l'espace de travail.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier, ex. rapport.docx"},
        "titre": {"type": "str", "obligatoire": True, "description": "titre du document"},
        "contenu": {"type": "str", "obligatoire": True,
                    "description": "texte du document ; une ligne par paragraphe"}},
       categorie="documents", risque="moyen")
def creer_word(nom: str, titre: str, contenu: str) -> str:
    nom = nom.strip()
    if not nom.lower().endswith(".docx"):
        nom += ".docx"
    from outils.fichiers import _chemin_espace
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(_construire_docx(titre, _couper(contenu)))
    return (f"Word créé : {chemin.name} ({chemin.stat().st_size} octets, "
            f"{len(_couper(contenu))} ligne(s)).")
