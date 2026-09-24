"""Rendu de documents JIBI : spécification JSON → HTML/CSS → PDF local.

Le modèle ne produit pas de PDF ni de CSS libre. Il remplit une spécification
JSON validée par Python, qui choisit un thème et produit un HTML sûr. Le PDF
est rendu par Chromium local headless (Playwright ou le binaire Chrome), sans
service cloud. Les images importées sont limitées à l'espace de travail.
"""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import subprocess
from pathlib import Path
from typing import Any

from jibi2 import config

MAX_JSON = 300_000
MAX_SECTIONS = 80
MAX_TABLE_ROWS = 200
MAX_TABLE_COLS = 30
MAX_IMAGE_BYTES = 12 * 1024 * 1024

THEMES: dict[str, dict[str, str]] = {
    "sobre": {
        "bg": "#f7f8fb", "surface": "#ffffff", "ink": "#172033",
        "muted": "#5e687c", "primary": "#334155", "accent": "#64748b",
        "line": "#dbe1ea", "head": "#eef2f7", "font": "Segoe UI, Arial, sans-serif",
    },
    "colore": {
        "bg": "#fffaf3", "surface": "#ffffff", "ink": "#31223b",
        "muted": "#766b7d", "primary": "#7c3aed", "accent": "#f97316",
        "line": "#f1d7c2", "head": "#fce7f3", "font": "Segoe UI, Arial, sans-serif",
    },
    "scolaire": {
        "bg": "#f4f8ff", "surface": "#ffffff", "ink": "#17233d",
        "muted": "#5b6b85", "primary": "#1d4ed8", "accent": "#0f766e",
        "line": "#cbdcf5", "head": "#dbeafe", "font": "Segoe UI, Arial, sans-serif",
    },
    "moderne_sombre": {
        "bg": "#0b1020", "surface": "#141d31", "ink": "#f3f6ff",
        "muted": "#aab6ce", "primary": "#8b6cff", "accent": "#54b9ff",
        "line": "#2b3a5d", "head": "#1c2944", "font": "Segoe UI, Arial, sans-serif",
    },
    "professionnel": {
        "bg": "#f4f6f8", "surface": "#ffffff", "ink": "#1f2937",
        "muted": "#64748b", "primary": "#0f4c81", "accent": "#0f766e",
        "line": "#d6dee8", "head": "#e8f0f8", "font": "Segoe UI, Arial, sans-serif",
    },
    "enfant": {
        "bg": "#fffdf4", "surface": "#ffffff", "ink": "#293241",
        "muted": "#6c7280", "primary": "#ea580c", "accent": "#2563eb",
        "line": "#f2d7a6", "head": "#ffedd5", "font": "Segoe UI, Arial, sans-serif",
    },
}

MOTIFS = ("aucun", "degrade", "rayures", "cercles", "points")

EXEMPLES: dict[str, dict[str, Any]] = {
    "compte_rendu": {
        "titre": "Compte rendu de réunion",
        "sous_titre": "Décisions et prochaines étapes",
        "theme": "professionnel",
        "motif": "degrade",
        "sections": [
            {"type": "texte", "titre": "Résumé",
             "contenu": "La équipe a validé les objectifs de la semaine et réparti les responsabilités."},
            {"type": "tableau", "titre": "Décisions", "colonnes": ["Sujet", "Décision", "Responsable"],
             "lignes": [["Livraison", "Avancer au vendredi", "Marie"], ["Documentation", "Mettre à jour le guide", "Alex"]]},
            {"type": "liste", "titre": "Prochaines étapes", "elements": ["Préparer le planning", "Relire le compte rendu"]},
        ],
        "pied_de_page": "JIBI — document local",
    },
    "fiche_scolaire": {
        "titre": "Fiche pédagogique",
        "sous_titre": "Séance et objectifs",
        "theme": "scolaire",
        "motif": "cercles",
        "sections": [
            {"type": "texte", "titre": "Objectif", "contenu": "Comprendre les notions essentielles et savoir les appliquer."},
            {"type": "liste", "titre": "Activités", "elements": ["Rappel", "Exercice guidé", "Correction collective"]},
        ],
    },
    "budget": {
        "titre": "Budget mensuel",
        "sous_titre": "Revenus et dépenses",
        "theme": "coloré",
        "motif": "points",
        "sections": [
            {"type": "tableau", "colonnes": ["Poste", "Montant"], "lignes": [["Loyer", "850"], ["Courses", "320"], ["Transport", "75"]]},
        ],
    },
    "moderne": {
        "titre": "Note de projet",
        "sous_titre": "Version JIBI",
        "theme": "moderne_sombre",
        "motif": "rayures",
        "sections": [
            {"type": "texte", "titre": "Idea", "contenu": "Une page claire, structurée et facile à partager."},
            {"type": "texte", "titre": "Prochaine étape", "contenu": "Collecter les retours puis améliorer le contenu."},
        ],
    },
}


def exemple(nom: str = "") -> str:
    """Renvoie un exemple JSON court, pour guider le modèle et l'utilisateur."""
    if nom:
        cle = nom.strip().lower().replace(" ", "_")
        if cle not in EXEMPLES:
            return f"Exemple inconnu. Choisis parmi : {', '.join(EXEMPLES)}."
        return json.dumps(EXEMPLES[cle], ensure_ascii=False, indent=2)
    return json.dumps(EXEMPLES, ensure_ascii=False, indent=2)


def _limite(texte: str, maximum: int, message: str) -> str:
    valeur = str(texte or "")
    if len(valeur) > maximum:
        raise ValueError(message)
    return valeur


def normaliser_spec(spec: str | dict[str, Any] | None, titre: str = "",
                    contenu: str = "", theme: str = "") -> dict[str, Any]:
    """Valide et complète une spécification sans jamais accepter de CSS libre."""
    if isinstance(spec, str):
        if len(spec) > MAX_JSON:
            raise ValueError("La spécification JSON est trop volumineuse.")
        try:
            brut = json.loads(spec)
        except json.JSONDecodeError as exc:
            if not contenu:
                raise ValueError(f"JSON de document invalide : {exc.msg} (position {exc.pos}).") from exc
            brut = {}
    elif isinstance(spec, dict):
        brut = dict(spec)
    elif spec is None:
        brut = {}
    else:
        raise ValueError("La spécification doit être un objet JSON.")

    titre = _limite(str(brut.get("titre") or titre or "Document JIBI"), 180,
                   "Titre de document trop long.")
    theme_choisi = str(brut.get("theme") or theme or "moderne_sombre").strip().lower()
    alias = {"sombre": "moderne_sombre", "dark": "moderne_sombre", "clair": "sobre",
             "coloré": "colore", "colorful": "colore", "scolaire": "scolaire", "pro": "professionnel"}
    theme_choisi = alias.get(theme_choisi, theme_choisi)
    if theme_choisi not in THEMES:
        raise ValueError(f"Thème inconnu. Choisis parmi : {', '.join(THEMES)}.")
    motif = str(brut.get("motif") or "degrade").strip().lower()
    if motif not in MOTIFS:
        motif = "degrade"

    sections_brutes = brut.get("sections")
    if not isinstance(sections_brutes, list) or not sections_brutes:
        contenu_brut = str(brut.get("contenu") or contenu or "").strip()
        sections_brutes = ([{"type": "texte", "titre": "", "contenu": contenu_brut}]
                          if contenu_brut else [])
    if len(sections_brutes) > MAX_SECTIONS:
        raise ValueError(f"Trop de sections : maximum {MAX_SECTIONS}.")

    sections: list[dict[str, Any]] = []
    for element in sections_brutes[:MAX_SECTIONS]:
        if not isinstance(element, dict):
            element = {"type": "texte", "contenu": str(element)}
        type_section = str(element.get("type") or "texte").lower()
        if type_section in ("texte", "text", "paragraphe"):
            valeur = _limite(str(element.get("contenu") or element.get("texte") or ""), 40_000,
                              "Section texte trop longue.")
            sections.append({"type": "texte", "titre": _limite(str(element.get("titre") or ""), 180, "Titre de section trop long."),
                              "contenu": valeur})
        elif type_section in ("liste", "list", "puce"):
            elements = element.get("elements", element.get("contenu", []))
            if isinstance(elements, str):
                elements = elements.splitlines()
            if not isinstance(elements, list):
                elements = [elements]
            sections.append({"type": "liste", "titre": _limite(str(element.get("titre") or ""), 180, "Titre de section trop long."),
                              "elements": [_limite(str(x), 1_000, "Élément de liste trop long.") for x in elements[:200]]})
        elif type_section in ("tableau", "table"):
            colonnes = element.get("colonnes", [])
            lignes = element.get("lignes", element.get("rows", []))
            if not isinstance(colonnes, list) or not colonnes:
                colonnes = [f"Colonne {i + 1}" for i in range(max((len(x) for x in lignes if isinstance(x, list)), default=1))]
            colonnes = [_limite(str(x), 100, "En-tête de tableau trop long.") for x in colonnes[:MAX_TABLE_COLS]]
            lignes_propres: list[list[str]] = []
            if isinstance(lignes, list):
                for ligne in lignes[:MAX_TABLE_ROWS]:
                    if isinstance(ligne, (list, tuple)):
                        valeurs = [_limite(str(x), 2_000, "Cellule de tableau trop longue.") for x in ligne[:MAX_TABLE_COLS]]
                    else:
                        valeurs = [_limite(str(ligne), 2_000, "Cellule de tableau trop longue.")]
                    valeurs += [""] * (len(colonnes) - len(valeurs))
                    lignes_propres.append(valeurs[:len(colonnes)])
            sections.append({"type": "tableau", "titre": _limite(str(element.get("titre") or ""), 180, "Titre de section trop long."),
                              "colonnes": colonnes, "lignes": lignes_propres})
        elif type_section in ("dessin", "schema", "diagramme", "emoji", "emojis", "emotifs"):
            elements = element.get("elements", element.get("lignes", element.get("contenu", [])))
            if isinstance(elements, str):
                elements = elements.splitlines()
            if not isinstance(elements, list):
                elements = [elements]
            sections.append({"type": "dessin", "titre": _limite(str(element.get("titre") or "Schéma"), 180, "Titre de dessin trop long."),
                              "elements": [_limite(str(x), 2_000, "Ligne de dessin trop longue.") for x in elements[:100]]})
        elif type_section in ("image", "illustration", "photo"):
            chemin = _limite(str(element.get("chemin") or element.get("source") or ""), 500, "Chemin d'image trop long.")
            sections.append({"type": "image", "titre": _limite(str(element.get("titre") or ""), 180, "Titre de section trop long."),
                              "chemin": chemin, "legende": _limite(str(element.get("legende") or ""), 500, "Légende trop longue.")})
        else:
            raise ValueError(f"Type de section inconnu : {type_section}.")

    images = []
    for element in sections:
        if element.get("type") == "image" and element.get("chemin"):
            images.append(element["chemin"])
    for chemin in (brut.get("images") or [])[:20]:
        if isinstance(chemin, str):
            images.append(_limite(chemin, 500, "Chemin d'image trop long."))
    return {"titre": titre,
            "sous_titre": _limite(str(brut.get("sous_titre") or ""), 300, "Sous-titre trop long."),
            "theme": theme_choisi, "motif": motif, "sections": sections,
            "images": list(dict.fromkeys(images))[:30],
            "pied_de_page": _limite(str(brut.get("pied_de_page") or "JIBI — document local"), 200, "Pied de page trop long.")}


def _image_data_uri(chemin: str) -> str | None:
    if not chemin:
        return None
    try:
        from outils.fichiers import _chemin_espace
        cible = _chemin_espace(chemin)
    except Exception:
        return None
    if not cible.is_file() or cible.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return None
    try:
        if cible.stat().st_size > MAX_IMAGE_BYTES:
            return None
        mime = mimetypes.guess_type(cible.name)[0] or "application/octet-stream"
        donnees = base64.b64encode(cible.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{donnees}"
    except OSError:
        return None


def _css(theme: str, motif: str) -> str:
    c = THEMES[theme]
    fond_motif = {
        "aucun": c["bg"],
        "degrade": f"linear-gradient(135deg, {c['bg']} 0%, {c['head']} 100%)",
        "rayures": f"repeating-linear-gradient(135deg, {c['bg']} 0, {c['bg']} 12px, {c['head']} 12px, {c['head']} 24px)",
        "cercles": f"radial-gradient(circle at 15% 20%, {c['head']} 0, transparent 28%), radial-gradient(circle at 90% 80%, {c['head']} 0, transparent 24%), {c['bg']}",
        "points": f"radial-gradient({c['line']} 1px, transparent 1px), {c['bg']}",
    }.get(motif, c["bg"])
    background_size = "background-size: 18px 18px;" if motif == "points" else ""
    return f"""
@page {{ size: A4; margin: 16mm 15mm 17mm; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; }}
body {{ background:{fond_motif}; {background_size} color:{c['ink']}; font-family:{c['font']}; font-size:10.5pt; line-height:1.48; }}
.page {{ max-width: 178mm; margin:0 auto; background:{c['surface']}; padding:12mm 13mm; box-shadow:0 8px 28px #0001; }}
header {{ border-bottom:3px solid {c['primary']}; padding-bottom:7mm; margin-bottom:8mm; }}
h1 {{ color:{c['primary']}; font-size:25pt; line-height:1.1; margin:0 0 3mm; }}
.subtitle {{ color:{c['muted']}; font-size:12pt; margin:0; }}
section {{ margin:0 0 7mm; break-inside:avoid; }}
h2 {{ color:{c['primary']}; font-size:15pt; border-left:4px solid {c['accent']}; padding-left:3mm; margin:0 0 3mm; }}
p {{ margin:0 0 3mm; orphans:3; widows:3; }}
ul {{ margin:2mm 0 0 6mm; padding-left:5mm; }}
li {{ margin:1.5mm 0; }}
table {{ width:100%; border-collapse:collapse; margin-top:2mm; font-size:9.3pt; }}
th {{ background:{c['head']}; color:{c['ink']}; font-weight:700; }}
th, td {{ border:1px solid {c['line']}; padding:2.2mm 2.5mm; text-align:left; vertical-align:top; }}
tr:nth-child(even) td {{ background:{c['bg']}; opacity:.92; }}
.emoji-art {{ white-space:pre-wrap; text-align:center; font-family:'Segoe UI Emoji','Segoe UI',sans-serif; font-size:20pt; line-height:1.35; padding:5mm; border:2px solid {c['primary']}; border-radius:4mm; background:{c['bg']}; color:{c['ink']}; }}
figure {{ margin:3mm 0; text-align:center; break-inside:avoid; }}
figure img {{ max-width:100%; max-height:75mm; object-fit:contain; border-radius:3mm; border:1px solid {c['line']}; }}
figcaption {{ color:{c['muted']}; font-size:8.5pt; margin-top:1.5mm; }}
footer {{ border-top:1px solid {c['line']}; color:{c['muted']}; font-size:8.5pt; margin-top:9mm; padding-top:3mm; text-align:right; }}
.missing {{ color:{c['muted']}; font-style:italic; }}
"""


def html_document(spec: dict[str, Any]) -> str:
    """Construit un HTML autonome et sans JavaScript."""
    c = THEMES[spec["theme"]]
    esc = html.escape
    parties = [f"<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">",
               f"<title>{esc(spec['titre'])}</title><style>{_css(spec['theme'], spec['motif'])}</style></head>",
               f"<body><main class=\"page\"><header><h1>{esc(spec['titre'])}</h1>",
               f"<p class=\"subtitle\">{esc(spec.get('sous_titre', ''))}</p></header>"]
    for element in spec.get("sections", []):
        type_section = element.get("type")
        titre = esc(str(element.get("titre") or ""))
        if type_section == "texte":
            corps = str(element.get("contenu") or "").strip()
            if not corps:
                continue
            blocs = re.split(r"\n\s*\n", corps)
            contenu = "".join(f"<p>{esc(bloc).replace(chr(10), '<br>')}</p>" for bloc in blocs if bloc.strip())
            parties.append(f"<section><h2>{titre}</h2>{contenu}</section>")
        elif type_section == "liste":
            elements = element.get("elements", [])
            li = "".join(f"<li>{esc(str(x))}</li>" for x in elements)
            parties.append(f"<section><h2>{titre}</h2><ul>{li}</ul></section>")
        elif type_section == "tableau":
            colonnes = element.get("colonnes", [])
            tete = "".join(f"<th>{esc(str(x))}</th>" for x in colonnes)
            corps = "".join("<tr>" + "".join(f"<td>{esc(str(x))}</td>" for x in ligne) + "</tr>"
                            for ligne in element.get("lignes", []))
            parties.append(f"<section><h2>{titre}</h2><table><thead><tr>{tete}</tr></thead><tbody>{corps}</tbody></table></section>")
        elif type_section == "dessin":
            art = esc("\n".join(str(x) for x in element.get("elements", [])))
            parties.append(f"<section><h2>{titre}</h2><div class=\"emoji-art\">{art}</div></section>")
        elif type_section == "image":
            source = _image_data_uri(str(element.get("chemin") or ""))
            if source:
                legende = esc(str(element.get("legende") or ""))
                parties.append(f"<section><h2>{titre}</h2><figure><img src=\"{source}\"><figcaption>{legende}</figcaption></figure></section>")
            else:
                parties.append(f"<section><h2>{titre}</h2><p class=\"missing\">Image indisponible : {esc(str(element.get('chemin') or ''))}</p></section>")
    images = spec.get("images", [])
    if images:
        figures = []
        for chemin in images:
            source = _image_data_uri(str(chemin))
            if source:
                figures.append(f"<figure><img src=\"{source}\"></figure>")
        if figures:
            parties.append("<section><h2>Images importées</h2>" + "".join(figures) + "</section>")
    parties.append(f"<footer>{esc(spec.get('pied_de_page', ''))}</footer></main></body></html>")
    return "".join(parties)


def ecrire_html(spec: dict[str, Any], chemin: Path) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(html_document(spec), encoding="utf-8")
    return chemin


def _chrome_local() -> str:
    configure = config.valeur("JIBI_BROWSER_CHROME", "").strip()
    if configure and Path(configure).is_file():
        return configure
    try:
        from outils.applications import _trouver_chrome
        return str(_trouver_chrome() or "")
    except Exception:
        return ""


def html_vers_pdf(html_path: Path, pdf_path: Path) -> None:
    """Convertit le HTML avec Chromium local, sans fenêtre visible."""
    erreurs: list[str] = []
    pdf_path.unlink(missing_ok=True)
    def _valide() -> bool:
        return (pdf_path.is_file() and pdf_path.stat().st_size > 100
                and pdf_path.read_bytes()[:5] == b"%PDF-")
    navigateur = None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as play:
            navigateur = play.chromium.launch(
                headless=True, executable_path=_chrome_local() or None,
                args=["--disable-gpu", "--disable-extensions"])
            page = navigateur.new_page()
            page.goto(html_path.as_uri(), wait_until="load", timeout=30_000)
            page.emulate_media(media="print")
            page.pdf(path=str(pdf_path), format="A4", print_background=True,
                     margin={"top": "12mm", "right": "12mm", "bottom": "14mm", "left": "12mm"})
        if _valide():
            return
        erreurs.append("Chromium Playwright n'a produit aucun PDF valide.")
    except Exception as exc:  # noqa: BLE001
        erreurs.append(f"Playwright : {str(exc)[:180]}")
    finally:
        if navigateur is not None:
            try:
                navigateur.close()
            except Exception:
                pass
    chrome = _chrome_local()
    if chrome:
        profil = Path(tempfile.mkdtemp(prefix="jibi-pdf-chrome-"))
        try:
            finished = subprocess.run([
                chrome, "--headless=new", "--disable-gpu", "--disable-extensions",
                "--disable-background-networking", "--no-first-run",
                "--no-default-browser-check", "--user-data-dir=" + str(profil),
                f"--print-to-pdf={pdf_path.resolve()}", "--no-pdf-header-footer",
                html_path.resolve().as_uri()], capture_output=True, timeout=90, check=False)
            if finished.returncode == 0 and _valide():
                return
            erreurs.append(f"Chrome CLI : code {finished.returncode}.")
        except Exception as exc:  # noqa: BLE001
            erreurs.append(f"Chrome CLI : {str(exc)[:180]}")
        finally:
            shutil.rmtree(profil, ignore_errors=True)
    raise RuntimeError(" ; ".join(erreurs) or "Aucun moteur PDF local disponible.")


def creer_pdf_html(nom: str, spec: dict[str, Any], chemin: Path) -> str:
    """Écrit le HTML, le PDF et retourne une description courte pour l'outil."""
    html_path = chemin.with_suffix(".html")
    ecrire_html(spec, html_path)
    try:
        html_vers_pdf(html_path, chemin)
        moteur = "Chromium headless local"
    except Exception:
        # L'appelant peut fournir un fallback pur Python si nécessaire.
        raise
    return (f"PDF créé avec {moteur} : {chemin.name} ({chemin.stat().st_size} octets). "
            f"HTML source : {html_path.name}")
