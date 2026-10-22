# -*- coding: utf-8 -*-
'''Rail documents de JIBI 2 — helpers documents extraits de jibi2/assistant.py.

Tranche T1 de la refonte : extrait TEL QUEL (verbatim), comportement
identique. Les noms restent importables depuis jibi2.assistant, qui
ré-exporte tout (contrat des tests et des rails vivants).
'''
from __future__ import annotations

import json
import re


def _reponse_pdf_exemple(texte: str, garde) -> dict | None:
    """Crée réellement un PDF pour une demande d'exemple, sans dépendre du modèle."""
    t = " ".join((texte or "").strip().split())
    minuscule = t.lower()
    if not re.search(r"\b(crée|créer|cree|generer|génère|fais|réalise)\b", minuscule):
        return None
    if not re.search(r"\b(pdf|document)\b", minuscule):
        return None
    if not re.search(r"\b(exemple|exemplaire|test|voir|juste)\b", minuscule):
        return None
    if re.search(r"\b(json|spécification|specification|modèle|modele|structure)\b", minuscule):
        from jibi2.assistant import _reponse_outil  # import tardif : boucle d'import évitée
        return _reponse_outil("exemple_document", {}, garde)
    from outils import executer
    from outils.fichiers import _chemin_espace
    nom = "exemple_jibi.pdf"
    index = 2
    while _chemin_espace(nom).exists():
        nom = f"exemple_jibi_{index}.pdf"
        index += 1
    resultat = executer("creer_pdf", {
        "nom": nom,
        "titre": "Exemple de document JIBI",
        "contenu": ("Ceci est un document PDF de démonstration créé par JIBI.\n"
                    "Tu peux maintenant le retrouver dans la liste Documents."),
    }, garde)
    return {"reponse": resultat["texte"],
            "actions": [{"outil": "creer_pdf", **resultat}],
            "ok": resultat["ok"]}


def _demande_tableau(texte: str) -> dict | None:
    """Reçoit les demandes de tableau simples sans passer par le modèle."""
    t = " ".join(str(texte or "").strip().split())
    minuscule = t.lower()
    if not t or not re.search(r"\b(tableau|table|grille)\b", minuscule):
        return None
    if not re.search(r"\b(crée|cree|creer|créer|fais|faire|réalis|realis|prépar|prepar|"
                     r"construis|produis|génère|generer|donne|donner)\b", minuscule):
        return None
    sujet = "Tableau"
    match = re.search(
        r"\b(?:tableau|table|grille)\s*(?:de|du|des|sur|pour|concernant|concernant)?\s*(.*)$",
        t, re.I)
    if match:
        sujet = re.split(
            r"\s+(?:en|sur|sous forme de?|avec)\s+(?:un\s+|une\s+)?"
            r"(?:excel|word|docx|pdf|document|tableur)\b", match.group(1), maxsplit=1,
            flags=re.I)[0].strip(" ?.!,;:")
    sujet = re.sub(r"^(?:excel|word|docx|pdf|tableur|classeur)\s+(?:pour|sur|de|du|des)\s+",
                   "", sujet, flags=re.I)
    sujet = re.sub(r"^(?:dans|sur)\s+(?:un\s+|une\s+)?(?:document\s+)?"
                   r"(?:word|docx|excel|pdf|tableur)?\s*", "", sujet, flags=re.I).strip(" ?.!,;:")
    if not sujet:
        sujet = "Tableau"
    if re.search(r"\b(word|docx|document word)\b", minuscule):
        format_document = "word"
    else:
        format_document = "excel"
    return {"titre": sujet[:120], "format": format_document}


def _tableau_lignes(texte: str) -> tuple[list[str], list[list[str]]]:
    """Extrait un tableau JSON ou des lignes séparées par tabulation/point-virgule."""
    for candidat in re.findall(r"\[[\s\S]{2,12000}\]", texte or ""):
        try:
            donnees = json.loads(candidat)
        except json.JSONDecodeError:
            continue
        if isinstance(donnees, list) and donnees and isinstance(donnees[0], list):
            return [str(x) for x in donnees[0]], [[str(x) for x in ligne] for ligne in donnees[1:]]
    lignes = []
    for ligne in str(texte or "").splitlines():
        if "\t" in ligne:
            lignes.append([x.strip() for x in ligne.split("\t")])
        elif ";" in ligne:
            lignes.append([x.strip() for x in ligne.split(";")])
    if lignes:
        return lignes[0], lignes[1:]
    return [], []


def _reponse_tableau_autonome(texte: str, garde) -> dict | None:
    t = " ".join(str(texte or "").strip().split())
    demande = _demande_tableau(texte)
    if demande is None:
        return None
    colonnes, lignes = _tableau_lignes(texte)
    sujet = demande["titre"]
    if not colonnes:
        if re.search(r"budget|depense|dépense|revenu", sujet, re.I):
            colonnes, lignes = ["Poste", "Montant"], [["À compléter", ""]]
        elif re.search(r"signes?|math", sujet, re.I):
            colonnes, lignes = ["Étape", "Expression", "Signe", "Justification"], [
                ["1", "À analyser", "", ""], ["2", "Résultat", "", ""]]
        else:
            colonnes, lignes = ["Colonne 1", "Colonne 2", "Colonne 3"], [["À compléter", "", ""]]
    from outils import executer
    from outils.fichiers import _chemin_espace
    # Le nom reste simple et lisible ; les accents sont supprimés proprement.
    base = "tableau_" + re.sub(r"[^a-z0-9]+", "_", sujet.casefold()).strip("_")[:50]
    extension = ".docx" if demande["format"] == "word" else ".xlsx"
    nom = f"{base or 'tableau'}{extension}"
    index = 2
    while _chemin_espace(nom).exists():
        nom = f"{base}_{index}{extension}"
        index += 1
    minuscule = t.lower()
    theme_tableau = "coloré" if re.search(r"couleur|coloré|colore|emoji|émoji", minuscule) else (
        "scolaire" if re.search(r"math|signes?|école|cours", minuscule) else "moderne_sombre")
    spec = {"titre": sujet.title(), "theme": theme_tableau, "motif": "degrade",
            "sections": [{"type": "tableau", "titre": "Tableau", "colonnes": colonnes,
                          "lignes": lignes}]}
    resultat = executer("creer_document", {
        "nom": nom, "format": demande["format"], "spec": json.dumps(spec, ensure_ascii=False),
        "theme": theme_tableau}, garde)
    emplacement = _chemin_espace(nom)
    action = "creer_document"
    return {"reponse": (resultat.get("texte", "Le tableau n'a pas pu être créé.")
                        if not resultat.get("ok", False)
                        else f"Tableau créé : {resultat.get('texte', '')}\n"
                             f"Fichier disponible ici : {emplacement}"),
            "actions": [{"outil": action, **resultat}], "ok": bool(resultat.get("ok", False))}


def _demande_dessin(texte: str) -> dict | None:
    t = " ".join(str(texte or "").strip().split())
    minuscule = t.lower()
    if not re.search(r"\b(dessin|dessiner|schéma|schema|diagramme|emoji|émojis|emotifs?|emoticons?)\b",
                     minuscule):
        return None
    if not re.search(r"\b(crée|cree|creer|créer|fais|faire|réalis|realis|prépar|prepar|"
                     r"construis|produis|génère|generer|dessine|dessiner)\b", minuscule):
        return None
    sujet = re.sub(r"^.*?\b(?:fais|faire|crée|cree|creer|créer|réalis|realis|prépar|prepar|"
                  r"construis|produis|génère|generer|dessine|dessiner)\b", "", t, flags=re.I)
    sujet = re.sub(r"\b(?:un|une|le|la|les)?\s*(?:dessin|schéma|schema|diagramme)\b", " ", sujet,
                  flags=re.I)
    sujet = re.sub(r"\b(?:avec|des|de|du|en)\s+(?:des\s+)?(?:emoji|émojis|emotifs?|emoticons?)\b",
                  "", sujet, flags=re.I)
    sujet = re.sub(r"\b(?:en|sur)\s+(?:un\s+|une\s+)?(?:pdf|word|docx|document)\b", "", sujet,
                  flags=re.I).strip(" ?.!,;:")
    if not sujet:
        sujet = "Mon dessin"
    format_document = "word"
    if re.search(r"\b(pdf)\b", minuscule):
        format_document = "pdf"
    return {"sujet": sujet[:160], "format": format_document}


def _reponse_dessin_autonome(texte: str, garde) -> dict | None:
    demande = _demande_dessin(texte)
    if demande is None:
        return None
    sujet = demande["sujet"]
    art = [
        "✨ ✨ ✨ ✨ ✨",
        f"🎨  {sujet}  🎨",
        "╭────────────────────╮",
        "│  🌟  JIBI  ·  RÊVE  │",
        "│  💡  idées  ·  couleurs  │",
        "│  🚀  pas à pas  ·  ✨  │",
        "╰────────────────────╯",
        "⭐ ⭐ ⭐ ⭐ ⭐",
    ]
    spec = {"titre": f"🎨 {sujet}", "sous_titre": "✨ Petit dessin aux emojis",
            "theme": "coloré", "motif": "degrade",
            "sections": [{"type": "dessin", "titre": "Mon dessin", "elements": art},
                         {"type": "texte", "titre": "Légende",
                          "contenu": f"Voici une petite composition visuelle sur {sujet}."}]}
    from outils import executer
    from outils.fichiers import _chemin_espace
    base = "dessin_" + re.sub(r"[^a-z0-9]+", "_", sujet.casefold()).strip("_")[:50]
    extension = ".docx" if demande["format"] == "word" else ".pdf"
    nom = f"{base or 'dessin'}{extension}"
    index = 2
    while _chemin_espace(nom).exists():
        nom = f"{base}_{index}{extension}"
        index += 1
    resultat = executer("creer_document", {
        "nom": nom, "format": demande["format"], "spec": json.dumps(spec, ensure_ascii=False),
        "theme": "coloré"}, garde)
    emplacement = _chemin_espace(nom)
    return {"reponse": (resultat.get("texte", "Le dessin n'a pas pu être créé.")
                        if not resultat.get("ok", False)
                        else f"Dessin créé : {resultat.get('texte', '')}\n"
                             f"Fichier disponible ici : {emplacement}"),
            "actions": [{"outil": "creer_document", **resultat}],
            "ok": bool(resultat.get("ok", False))}


def _reponse_exporter_document(texte: str, garde) -> dict | None:
    """Copie ou déplace un document vers un dossier PC choisi explicitement."""
    t = " ".join(str(texte or "").strip().split())
    minuscule = t.casefold()
    if re.search(r"tous\s+les\s+dossiers", minuscule):
        return {"reponse": "Dis-moi un seul dossier précis : Téléchargements, Bureau, "
                            "Documents ou un chemin exact. Je ne copie pas le fichier "
                            "partout automatiquement.",
                "actions": [], "ok": False}
    if not re.search(r"\b(copie|copier|déplace|deplacer|mets|met|place|export|non\s+dans)\b",
                     minuscule, re.I):
        return None
    destinations = {
        "téléchargements": "Téléchargements", "telechargements": "Téléchargements",
        "downloads": "Téléchargements", "bureau": "Bureau", "desktop": "Bureau",
        "documents": "Documents", "dossier documents": "Documents",
    }
    destination = next((valeur for alias, valeur in destinations.items()
                        if alias in minuscule), None)
    if destination is None:
        chemin = re.search(r"[A-Za-z]:[\\/][^,;]+", t)
        if chemin:
            destination = chemin.group(0).strip()
    if destination is None:
        return None
    from jibi2 import config
    from outils import executer
    source = None
    nom_fichier = re.search(r"([\wÀ-ÿ ._-]+\.(?:pdf|docx|xlsx|pptx|html|txt|md|json))",
                            t, re.I)
    if nom_fichier:
        candidat = config.DOSSIER_FICHIERS / nom_fichier.group(1).strip()
        if candidat.is_file():
            source = candidat
    if source is None:
        fichiers = [p for p in config.DOSSIER_FICHIERS.rglob("*")
                    if p.is_file() and p.suffix.lower() in
                    {".pdf", ".docx", ".xlsx", ".pptx", ".html", ".txt", ".md", ".json"}]
        if fichiers:
            preferential = [p for p in fichiers
                             if re.search(r"cours|tableau|dessin", p.name, re.I)]
            source = max(preferential or fichiers, key=lambda p: p.stat().st_mtime)
    if source is None:
        return {"reponse": "Je ne trouve aucun document JIBI à copier. "
                            "Crée-le d’abord ou précise son nom.",
                "actions": [], "ok": False}
    operation = "deplacer_document" if re.search(r"\b(déplace|deplacer)\b", minuscule, re.I) else "copier_document"
    resultat = executer(operation, {"nom": source.name, "destination": destination}, garde)
    return {"reponse": resultat.get("texte", "Opération non effectuée."),
            "actions": [{"outil": operation, **resultat}],
            "ok": bool(resultat.get("ok", False))}


def _reponse_livrer_document(texte: str, garde) -> dict | None:
    """Donne le chemin exact et ouvre le dernier document local si demandé."""
    t = " ".join(str(texte or "").strip().split())
    if not re.search(r"\b(donne|livre|ouvrir|ouvre|montre|affiche|retourne)\b", t, re.I):
        return None
    if not re.search(r"\b(document|fichier|cours|tableau|dessin|word|pdf|excel)\b", t, re.I):
        return None
    from jibi2 import config
    from outils import executer
    racine = config.DOSSIER_FICHIERS
    extensions = {".pdf", ".docx", ".xlsx", ".pptx", ".html", ".txt", ".md", ".json"}
    fichiers = [p for p in racine.rglob("*") if p.is_file() and p.suffix.lower() in extensions]
    if not fichiers:
        return {"reponse": "Je ne trouve encore aucun document dans l’espace JIBI. "
                            "Demande-moi d’en créer un.", "actions": [], "ok": False}
    preferential = [p for p in fichiers if re.search(r"cours|tableau|dessin", p.name, re.I)]
    chemin = max(preferential or fichiers, key=lambda p: p.stat().st_mtime)
    resultat = executer("ouvrir_application", {"cible": str(chemin)}, garde)
    return {"reponse": f"Le document est ici : {chemin}\n"
                       f"Tu le trouveras aussi dans Documents → Tous les documents.",
            "actions": [{"outil": "ouvrir_application", **resultat}],
            "ok": bool(resultat.get("ok", True))}


def _reponse_document_autonome(texte: str, garde) -> dict | None:
    """Crée un document simple sans exiger que le modèle fournisse un JSON."""
    t = " ".join((texte or "").strip().split())
    minuscule = t.lower()
    if len(t) > 700 or not re.search(
            r"\b(crée|cree|créer|génère|genere|rédige|redige|préfère|prefere|prépare|prepare|conçois|concois)\b",
            minuscule):
        return None
    if not re.search(r"\b(document|rapport|compte rendu|fiche|lettre|cv|proposition|texte)\b",
                     minuscule):
        return None
    if re.search(r"\b(explique|comment|pourquoi|qu'est-ce|peux-tu|pourrais-tu)\b", minuscule):
        return None
    if re.search(r"\b(avec|via).*\b(css|html|code source)\b", minuscule):
        return None
    format_document = "word" if re.search(r"\b(word|docx|wordprocessing)\b", minuscule) else (
        "excel" if re.search(r"\b(excel|xlsx|tableur|classeur)\b", minuscule) else (
            "powerpoint" if re.search(r"\b(presentation|powerpoint|pptx)\b", minuscule) else "pdf"))
    themes = {
        "scolaire": "scolaire", "école": "scolaire", "prof": "scolaire",
        "sombre": "moderne_sombre", "dark": "moderne_sombre", "moderne": "moderne_sombre",
        "coloré": "colore", "colorful": "colore", "professionnel": "professionnel",
        "enfant": "enfant",
    }
    theme = next((v for k, v in themes.items() if k in minuscule), "moderne_sombre")
    titre = "Document JIBI"
    match = re.search(r"(?:intitulé|intitule|titre|appelé|appele|nommé|appelle)\s+(.+)", t, re.I)
    if match:
        titre = match.group(1).strip(" ?.!,;:")[:180]
    elif re.search(r"\b(compte rendu|rapport|fiche|lettre|cv)\b", minuscule):
        start = re.search(r"\b(compte rendu|rapport|fiche|lettre|cv)\b", t, re.I)
        if start:
            titre = t[start.start():start.start() + 100].strip(" ?.!,;:")
    corps = re.sub(r"^.*?\b(crée|cree|créer|génère|genere|rédige|redige|préfère|prefere|prépare|prepare|conçois|concois)\b\s*"
                   r"(?:un|une|le|la|les)?\s*(?:document|rapport|compte rendu|fiche|lettre|cv|proposition|texte)?\s*"
                   r"(?:sur|concernant|pour|:)?\s*", "", t, flags=re.I).strip(" ?.!,;:")
    if len(corps) < 8 or corps == t:
        corps = t
    spec = {"titre": titre, "theme": theme, "motif": "degrade",
            "sections": [{"type": "texte", "titre": "Contenu", "contenu": corps}]}
    import json as _json
    from outils import executer
    extension = {"pdf": "pdf", "word": "docx", "excel": "xlsx", "powerpoint": "pptx"}[format_document]
    base = "document_jibi"
    nom = f"{base}.{extension}"
    try:
        from outils.fichiers import _chemin_espace
        index = 2
        while _chemin_espace(nom).exists():
            nom = f"{base}_{index}.{extension}"
            index += 1
    except Exception:
        pass
    try:
        resultat = executer("creer_document", {"nom": nom, "format": format_document,
                                               "spec": _json.dumps(spec, ensure_ascii=False),
                                               "theme": theme}, garde)
    except Exception as exc:  # noqa: BLE001
        return {"reponse": f"Création autonome impossible : {str(exc)[:180]}",
                "actions": [], "ok": False}
    emplacement = ""
    try:
        from outils.fichiers import _chemin_espace
        emplacement = f"\nFichier disponible ici : {_chemin_espace(nom)}"
    except Exception:
        pass
    return {"reponse": resultat["texte"] + emplacement,
            "actions": [{"outil": "creer_document", **resultat}],
            "ok": resultat.get("ok", False)}
