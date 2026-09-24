"""Outils documents de JIBI 2 : créer de vrais PDF et fichiers Word.

100 % Python standard : pas de dépendance. Le PDF est écrit à la main
(format minimal, Helvetica, accents gérés) ; le Word (.docx) est un
petit zip XML valide, ouvert par Word, LibreOffice et Google Docs.
Tout atterrit dans l'espace de travail (donnees/fichiers).
"""
from __future__ import annotations

import json
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


def _spec_document(spec=None, titre: str = "", contenu: str = "", theme: str = ""):
    from outils.document_renderer import normaliser_spec
    return normaliser_spec(spec, titre=titre, contenu=contenu, theme=theme)


def _creer_pdf_spec(nom: str, spec: dict) -> str:
    from outils.document_renderer import creer_pdf_html
    from outils.fichiers import _chemin_espace
    nom = nom.strip()
    if not nom.lower().endswith(".pdf"):
        nom += ".pdf"
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    try:
        return creer_pdf_html(nom, spec, chemin)
    except RuntimeError:
        # Le générateur historique reste le filet de sécurité si Chromium
        # n'est pas disponible : JIBI ne perd jamais une création demandée.
        lignes_texte = []
        for element in spec.get("sections", []):
            if element.get("type") == "texte":
                lignes_texte.extend(str(element.get("contenu", "")).splitlines())
            elif element.get("type") == "dessin":
                lignes_texte.extend(str(x) for x in element.get("elements", []))
        chemin.write_bytes(_construire_pdf(spec["titre"], lignes_texte))
        return (f"PDF créé avec le générateur local de secours : {chemin.name} "
                f"({chemin.stat().st_size} octets).")


def _docx_spec(spec: dict) -> bytes:
    """Rend un DOCX python-docx si disponible, sinon l'OOXML minimal."""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor
    except Exception:
        lignes = [spec["titre"]]
        for element in spec.get("sections", []):
            if element.get("titre"):
                lignes.append(str(element["titre"]))
            if element.get("type") == "texte":
                lignes.extend(str(element.get("contenu", "")).splitlines())
            elif element.get("type") == "liste":
                lignes.extend(f"• {x}" for x in element.get("elements", []))
            elif element.get("type") == "dessin":
                lignes.extend(str(x) for x in element.get("elements", []))
            elif element.get("type") == "tableau":
                lignes.append(" | ".join(element.get("colonnes", [])))
                lignes.extend(" | ".join(str(x) for x in row) for row in element.get("lignes", []))
        return _construire_docx(spec["titre"], lignes)

    from outils.document_renderer import THEMES
    theme = THEMES.get(spec.get("theme", "sobre"), THEMES["sobre"])

    def _colorer_cellule(cellule, couleur: str) -> None:
        tc_pr = cellule._tc.get_or_add_tcPr()
        shd = tc_pr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tc_pr.append(shd)
        shd.set(qn("w:fill"), couleur.lstrip("#"))
        for paragraph in cellule.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor.from_string(theme["ink"].lstrip("#"))

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(.7)
    section.bottom_margin = Inches(.7)
    section.left_margin = Inches(.75)
    section.right_margin = Inches(.75)
    normal = document.styles["Normal"]
    normal.font.name = "Segoe UI"
    normal.font.size = Pt(10.5)
    titre = document.add_heading(spec["titre"], level=0)
    titre.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in titre.runs:
        run.font.color.rgb = RGBColor.from_string(theme["primary"].lstrip("#"))
    if spec.get("sous_titre"):
        p = document.add_paragraph(spec["sous_titre"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.color.rgb = RGBColor.from_string(theme["muted"].lstrip("#"))
    for element in spec.get("sections", []):
        if element.get("titre"):
            document.add_heading(element["titre"], level=1)
        if element.get("type") == "texte":
            for bloc in str(element.get("contenu", "")).split("\n"):
                document.add_paragraph(bloc)
        elif element.get("type") == "liste":
            for valeur in element.get("elements", []):
                document.add_paragraph(str(valeur), style="List Bullet")
        elif element.get("type") == "tableau":
            colonnes = element.get("colonnes", [])
            lignes = element.get("lignes", [])
            tableau = document.add_table(rows=1, cols=max(1, len(colonnes)))
            tableau.style = "Table Grid"
            for i, valeur in enumerate(colonnes):
                cellule = tableau.rows[0].cells[i]
                cellule.text = str(valeur)
                _colorer_cellule(cellule, theme["head"])
                for run in cellule.paragraphs[0].runs:
                    run.font.bold = True
            for index_ligne, ligne in enumerate(lignes):
                cells = tableau.add_row().cells
                for i, valeur in enumerate(ligne[:len(colonnes)]):
                    cells[i].text = str(valeur)
                    if index_ligne % 2 == 1:
                        _colorer_cellule(cells[i], theme["bg"])
        elif element.get("type") == "dessin":
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run("\n".join(str(x) for x in element.get("elements", [])))
            run.font.name = "Segoe UI Emoji"
            run.font.size = Pt(18)
        elif element.get("type") == "image":
            try:
                from outils.fichiers import _chemin_espace
                image = _chemin_espace(element.get("chemin", ""))
                if image.is_file() and image.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                    document.add_picture(str(image), width=Inches(5.8))
                    if element.get("legende"):
                        document.add_paragraph(element["legende"])
            except Exception:
                document.add_paragraph("Image indisponible.")
    footer = section.footer.paragraphs[0]
    footer.text = spec.get("pied_de_page", "JIBI — document local")
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    from io import BytesIO
    tampon = BytesIO()
    document.save(tampon)
    return tampon.getvalue()


def _pptx_spec(spec: dict) -> bytes:
    """Rend une présentation PowerPoint locale si python-pptx est installé."""
    try:
        from io import BytesIO
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("python-pptx est nécessaire pour créer un PowerPoint.") from exc
    from outils.document_renderer import THEMES
    theme = THEMES.get(spec.get("theme", "moderne_sombre"), THEMES["moderne_sombre"])
    presentation = Presentation()
    titre = presentation.slides.add_slide(presentation.slide_layouts[0])
    titre.shapes.title.text = spec["titre"]
    if spec.get("sous_titre"):
        titre.placeholders[1].text = spec["sous_titre"]
    for element in spec.get("sections", []):
        diapo = presentation.slides.add_slide(presentation.slide_layouts[1])
        diapo.shapes.title.text = str(element.get("titre") or spec["titre"])
        zone = diapo.placeholders[1].text_frame
        zone.clear()
        if element.get("type") == "texte":
            lignes = str(element.get("contenu", "")).splitlines() or [""]
        elif element.get("type") == "liste":
            lignes = [f"• {x}" for x in element.get("elements", [])]
        elif element.get("type") == "dessin":
            lignes = [str(x) for x in element.get("elements", [])]
        elif element.get("type") == "tableau":
            lignes = [" | ".join(str(x) for x in element.get("colonnes", []))]
            lignes += [" | ".join(str(x) for x in row) for row in element.get("lignes", [])]
        else:
            lignes = [str(element.get("legende") or "Image importée")]
        for index, ligne in enumerate(lignes):
            paragraphe = zone.paragraphs[0] if index == 0 else zone.add_paragraph()
            paragraphe.text = ligne
            paragraphe.font.size = Pt(18)
        for forme in diapo.shapes:
            if hasattr(forme, "text_frame") and forme.has_text_frame:
                for paragraphe in forme.text_frame.paragraphs:
                    for run in paragraphe.runs:
                        run.font.color.rgb = RGBColor.from_string(theme["ink"].lstrip("#"))
    tampon = BytesIO()
    presentation.save(tampon)
    return tampon.getvalue()


def _xlsx_spec(spec: dict) -> bytes:
    from outils.bureautique import _parse_contenu, _xlsx
    tableaux = [x for x in spec.get("sections", []) if x.get("type") == "tableau"]
    if tableaux:
        donnees = [tableaux[0].get("colonnes", [])] + tableaux[0].get("lignes", [])
        contenu = json.dumps(donnees, ensure_ascii=False)
    else:
        contenu = "\n".join(str(x.get("contenu", "")) for x in spec.get("sections", [])
                            if x.get("type") == "texte")
    lignes = _parse_contenu(contenu)
    try:
        from io import BytesIO
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        classeur = Workbook()
        feuille = classeur.active
        feuille.title = str(spec.get("sous_titre") or "Feuille1")[:31]
        for ligne in lignes:
            feuille.append(ligne)
        for cellule in feuille[1]:
            cellule.font = Font(bold=True, color="FFFFFF")
            cellule.fill = PatternFill("solid", fgColor="4F46E5")
        feuille.freeze_panes = "A2"
        feuille.column_dimensions["A"].width = 24
        for index, ligne in enumerate(lignes, 1):
            for colonne, valeur in enumerate(ligne, 1):
                if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                    feuille.cell(index, colonne).number_format = "#,##0.00"
        tampon = BytesIO()
        classeur.save(tampon)
        return tampon.getvalue()
    except Exception:
        return _xlsx(lignes, str(spec.get("sous_titre") or "Feuille1")[:31])


@outil("creer_document",
       "Crée un document autonome à partir d'une spécification JSON : PDF via "
       "HTML/CSS et Chromium headless local, Word via python-docx, Excel via "
       "openpyxl et PowerPoint via python-pptx. Utilise un thème JIBI ; "
       "n'envoie jamais de CSS libre.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier final"},
        "format": {"type": "str", "obligatoire": True, "description": "pdf, word ou excel"},
        "spec": {"type": "str", "obligatoire": True, "description": "spécification JSON du document"},
        "theme": {"type": "str", "obligatoire": False, "description": "theme : sobre, colore, scolaire, moderne_sombre, professionnel, enfant"}},
       categorie="documents", risque="moyen",
       exemple='{"outil": "creer_document", "parametres": {"nom": "resume.pdf", "format": "pdf", "theme": "moderne_sombre", "spec": "{\\"titre\\":\\"Résumé\\",\\"sections\\":[{\\"type\\":\\"texte\\",\\"contenu\\":\\"...\\"}]}"}}')
def creer_document(nom: str, format: str, spec: str, theme: str = "") -> str:
    format = (format or "pdf").strip().lower().replace(".", "")
    format = {"docx": "word", "xlsx": "excel", "pptx": "powerpoint",
              "presentation": "powerpoint"}.get(format, format)
    document = _spec_document(spec, theme=theme)
    from outils.fichiers import _chemin_espace
    nom = nom.strip()
    extension = {"pdf": ".pdf", "word": ".docx", "excel": ".xlsx",
                 "powerpoint": ".pptx"}.get(format)
    if extension is None:
        return "Format inconnu. Utilise pdf, word, excel ou powerpoint."
    if not nom.lower().endswith(extension):
        nom += extension
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if format == "pdf":
        message = _creer_pdf_spec(nom, document)
    elif format == "word":
        chemin.write_bytes(_docx_spec(document))
        message = f"Word créé : {chemin.name} ({chemin.stat().st_size} octets)."
    elif format == "powerpoint":
        chemin.write_bytes(_pptx_spec(document))
        message = f"PowerPoint créé : {chemin.name} ({chemin.stat().st_size} octets)."
    else:
        chemin.write_bytes(_xlsx_spec(document))
        message = f"Excel créé : {chemin.name} ({chemin.stat().st_size} octets)."
    return message


@outil("exemple_document",
       "Donne un exemple JSON prêt à remplir pour un document JIBI. Utilise-le "
       "avant de créer un document pour te guider sans inventer de CSS.",
       {"nom": {"type": "str", "obligatoire": False, "description": "compte_rendu, fiche_scolaire, budget ou moderne"}},
       categorie="documents", exemple='{"outil": "exemple_document", "parametres": {"nom": "compte_rendu"}}')
def exemple_document(nom: str = "") -> str:
    from outils.document_renderer import exemple
    return exemple(nom)


@outil("creer_pdf", "Crée un VRAI PDF. Le contenu simple est rendu en HTML/CSS "
       "par Chromium headless local ; l'ancien générateur reste le secours.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier, ex. compte_rendu.pdf"},
        "titre": {"type": "str", "obligatoire": True, "description": "titre du document"},
        "contenu": {"type": "str", "obligatoire": True,
                    "description": "texte simple ; une ligne par paragraphe"},
        "theme": {"type": "str", "obligatoire": False, "description": "thème JIBI"},
        "spec": {"type": "str", "obligatoire": False, "description": "spécification JSON complète prioritaire"}},
       categorie="documents", risque="moyen",
       exemple='{"outil": "creer_pdf", "parametres": {"nom": "liste_courses.pdf", '
               '"titre": "Liste de courses", "contenu": "Pain\\nLait\\nChocolat"}}')
def creer_pdf(nom: str, titre: str, contenu: str, theme: str = "", spec: str = "") -> str:
    document = _spec_document(spec or None, titre=titre, contenu=contenu, theme=theme)
    return _creer_pdf_spec(nom, document)


@outil("creer_word", "Crée un VRAI fichier Word (.docx) avec python-docx ou un "
       "rendu OOXML de secours, à partir d'un contenu simple ou d'un JSON.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier, ex. rapport.docx"},
        "titre": {"type": "str", "obligatoire": True, "description": "titre du document"},
        "contenu": {"type": "str", "obligatoire": True,
                    "description": "texte simple ; une ligne par paragraphe"},
        "theme": {"type": "str", "obligatoire": False, "description": "thème JIBI"},
        "spec": {"type": "str", "obligatoire": False, "description": "spécification JSON complète prioritaire"}},
       categorie="documents", risque="moyen")
def creer_word(nom: str, titre: str, contenu: str, theme: str = "", spec: str = "") -> str:
    document = _spec_document(spec or None, titre=titre, contenu=contenu, theme=theme)
    nom = nom.strip()
    if not nom.lower().endswith(".docx"):
        nom += ".docx"
    from outils.fichiers import _chemin_espace
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(_docx_spec(document))
    return (f"Word créé : {chemin.name} ({chemin.stat().st_size} octets).")


@outil("creer_cours",
       "Crée un cours complet structuré avec tableaux, sections et exercices. "
       "Produit un PDF professionnel (et optionnellement un Word). Idéal pour "
       "les cours, les leçons, les exposés et les fiches pédagogiques.",
       {"sujet": {"type": "str", "obligatoire": True,
                   "description": "sujet du cours (ex. : tableaux de signes)"},
        "niveau": {"type": "str", "obligatoire": False,
                   "description": "débutant, intermédiaire ou avancé"},
        "sections": {"type": "str", "obligatoire": False,
                    "description": "JSON des sections personnalisées (optionnel)"},
        "format": {"type": "str", "obligatoire": False,
                   "description": "pdf, word ou les deux (défaut pdf)"},
        "nom": {"type": "str", "obligatoire": False,
                "description": "nom du fichier (défaut : sujet_clean)"}},
       categorie="documents", risque="moyen",
       exemple='{"outil": "creer_cours", "parametres": {"sujet": "tableaux de signes", "niveau": "débutant"}}')
def creer_cours(sujet: str, niveau: str = "débutant",
                sections: str = "", format: str = "pdf",
                nom: str = "") -> str:
    """Crée un cours complet avec tables et sections structurées."""
    import json as _json
    from outils import fichiers
    from outils.document_renderer import normaliser_spec, exemple

    sujet_clean = "".join(c for c in sujet if c.isalnum() or c in " _-").strip()[:60]
    if not nom:
        nom = f"{sujet_clean.replace(' ', '_')}.pdf"
    chemin_pdf = fichiers._chemin_espace(nom)
    chemin_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Construire le spec du cours
    if sections:
        try:
            spec_perso = _json.loads(sections)
        except (json.JSONDecodeError, ValueError):
            spec_perso = {}
    else:
        spec_perso = {}

    # Sections par défaut si non fournies
    if not spec_perso.get("sections"):
        niveau_map = {
            "débutant": "Introduction aux bases",
            "intermédiaire": "Approfondissement et applications",
            "avancé": "Concepts avancés et cas pratiques",
        }
        sous_titre = f"Niveau : {niveau}"
        spec_perso = {
            "nom": nom.replace(".pdf", ""),
            "titre": f"Cours : {sujet}",
            "sous_titre": sous_titre,
            "theme": "sobre",
            "sections": [
                {"type": "texte", "titre": "Introduction",
                 "contenu": f"Ce cours sur {sujet} aborde les concepts fondamentaux "
                           f"et les principes de base. Il est conçu pour les apprenants "
                           f"de niveau {niveau}."},
                {"type": "tableau", "titre": "Aperçu du sujet",
                 "colonnes": ["Concept", "Description", "Exemple"],
                 "lignes": [["Définition", f"Qu'est-ce que {sujet} ?", "Voir le cours"],
                            ["Application", f"Où et comment l'utiliser ?", "Cas pratiques"],
                            ["Avantages", "Pourquoi l'apprendre ?", "Bénéfices"]]},
                {"type": "texte", "titre": "Contenu principal",
                 "contenu": f"Le cœur du cours sur {sujet} est présenté ci-dessous. "
                           f"Chaque section est illustrée par des exemples concrets."},
                {"type": "tableau", "titre": "Tableau récapitulatif",
                 "colonnes": ["Catégorie", "Détail", "Note"],
                 "lignes": [["Théorie", "Fondements scientifiques", "★★★★★"],
                            ["Pratique", "Exercices guidés", "★★★★☆"],
                            ["Avancé", "Cas complexes", "★★★☆☆"]]},
                {"type": "liste", "titre": "Exercices recommandés",
                 "elements": [f"Exercice 1 : Identifier les bases de {sujet}",
                              f"Exercice 2 : Appliquer les règles à un cas concret",
                              f"Exercice 3 : Créer votre propre exemple"]},
                {"type": "texte", "titre": "Conclusion",
                 "contenu": f"Ce cours sur {sujet} vous a donné les fondamentaux pour "
                           f"progresser. Consultez les ressources supplémentaires pour "
                           f"approfondir vos connaissances."}
            ]
        }
    else:
        spec_perso["titre"] = spec_perso.get("titre", f"Cours : {sujet}")
        spec_perso["sous_titre"] = spec_perso.get("sous_titre", f"Niveau : {niveau}")
        spec_perso["theme"] = spec_perso.get("theme", "sobre")

    # Normaliser le spec
    spec = normaliser_spec(spec_perso)

    # Créer le PDF
    resultat = _creer_pdf_spec(chemin_pdf.name, spec)

    # Créer le Word si demandé
    mot = ""
    if format in ("word", "les deux", "pdf+word"):
        chemin_docx = fichiers._chemin_espace(chemin_pdf.name.replace(".pdf", ".docx"))
        chemin_docx.parent.mkdir(parents=True, exist_ok=True)
        from outils.documents import _docx_spec
        chemin_docx.write_bytes(_docx_spec(spec))
        mot = (f" Word créé : {chemin_docx.name} "
               f"({chemin_docx.stat().st_size} octets). ")

    return f"Cours créé ! {resultat} {mot}Consultez la liste Documents."
