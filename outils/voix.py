"""Changement de voix de JIBI — lui-même peut le faire (pas le noyau).

Les voix sont des fichiers Piper dans modeles/voix/ : les ajouter ou en
choisir une autre n'est pas « toucher au noyau » (pas de permission).
siwis = femme (voix d'origine) ; tom / upmc / gilles = voix masculines.
Le réglage vit dans le .env (PIPER_MODELE), écrit proprement ligne par
ligne — rien d'autre n'est modifié.
"""
from __future__ import annotations

from outils import outil


def _ecrire_env(cle: str, valeur: str) -> None:
    """Met à jour UNE ligne du .env sans toucher au reste (données sacrées)."""
    from jibi2 import config
    chemin = config.RACINE / ".env"
    if not chemin.exists():
        lignes: list[str] = []
        separation = "\n"
    else:
        brut = chemin.read_bytes()
        separation = "\r\n" if b"\r\n" in brut else "\n"
        lignes = brut.decode("utf-8", errors="replace").splitlines()
    nouveau = f"{cle}={valeur}"
    remplace = False
    for i, ligne in enumerate(lignes):
        if ligne.split("=", 1)[0].strip() == cle:
            lignes[i] = nouveau
            remplace = True
            break
    if not remplace:
        lignes.append(nouveau)
    chemin.write_bytes((separation.join(lignes) + separation).encode("utf-8"))


@outil("changer_voix",
       "Change LA VOIX de JIBI (sans redémarrer) : siwis (femme), tom (homme), "
       "upmc (homme), gilles (homme, léger). Sans nom : liste les voix et dit "
       "laquelle parle. Une voix absente est téléchargée automatiquement "
       "(~20-65 Mo, HuggingFace officiel) puis activée.",
       parametres={"nom": {"type": "str",
                           "description": "siwis | tom | upmc | gilles (vide = lister)"}},
       categorie="design", risque="moyen",
       exemple="mets une voix masculine → nom=tom")
def changer_voix(nom: str = "") -> str:
    from audio import parole
    n = (nom or "").strip().lower()
    if n in ("", "liste", "quelles voix"):
        actuelle = parole.voix_actuelle()
        installees = parole.voix_installees()
        catalogue = " ; ".join(
            f"{v} ({infos['sexe']}{'' if v in installees else ', à télécharger'})"
            for v, infos in parole.CATALOGUE_VOIX.items())
        return f"Voix actuelle : {actuelle}. Disponibles : {catalogue}."
    if n not in parole.CATALOGUE_VOIX:
        return (f"Voix « {n} » inconnue. Choisis parmi : "
                + ", ".join(parole.CATALOGUE_VOIX) + ".")
    infos = parole.CATALOGUE_VOIX[n]
    try:
        chemin = parole.telecharger_voix(n)
    except Exception as e:  # noqa: BLE001
        return (f"Téléchargement de la voix {n} impossible ({str(e)[:80]}). "
                "Vérifie la connexion internet, ou remets un fichier .onnx "
                "dans modeles/voix/ à la main.")
    _ecrire_env("PIPER_MODELE", str(chemin))
    parole.recharger()
    return (f"Voix {n} ({infos['sexe']}) activée — je te parle maintenant "
            "avec, sans redémarrage.")
