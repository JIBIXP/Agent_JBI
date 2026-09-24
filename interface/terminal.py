"""Console de JIBI 2 — simple, en français, avec commandes slash."""
from __future__ import annotations

import contextlib
import threading

BANNIERE = r"""
   ╔══════════════════════════════════════════╗
   ║   J I B I   2  —  assistant local        ║
   ║   Ollama + voix, tout reste sur ton PC   ║
   ╚══════════════════════════════════════════╝
"""


def confirmer_console(nom_outil: str, detail: str) -> bool:
    print(f"\nAction sensible demandée\n    {detail}")
    try:
        return input("    Confirmer ? (o/N) ").strip().lower() in ("o", "oui", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _etat_modele(client, ok: bool) -> str:
    """Texte de statut à afficher à côté du nom du modèle (banni des ternaires imbriqués)."""
    if not ok:
        return "  Ollama éteint"
    if client.modele_present():
        return "  prêt"
    return "  absent (ollama pull " + client.modele + ")"


def _afficher_entete(client, ok: bool, memoire, voix_on: bool, ecoute) -> None:
    print(BANNIERE)
    print(f"   Modèle   : {client.modele}{_etat_modele(client, ok)}")
    print(f"   Mémoire  : {memoire.chemin}")
    print(f"   Voix     : {'on' if voix_on else 'off'}  (/voix on)   Micro : {'disponible' if ecoute.micro_disponible() else 'indisponible'}")
    print("   Commandes : /aide /outils /bilan /signaux /workflows /sessions /notes /propositions "
          "/autonomie [on|off HH:MM] /ameliorer [objectif] /tester <nom> /valider <nom> "
          "/retirer <nom> /verif /micro /voix on|off /nouvelle /quitter "
           "/verrouiller_noyau /déverrouiller_noyau /basculer_noyau "
           "/basculer_deplacement /gestionnaire_fichiers "
            "/configurer_deplacement")


class _Signal:
    """Ce que la boucle principale doit faire après une commande slash."""
    ARRETER = "arreter"          # /quitter, /exit, /q
    CONTINUER = "continuer"      # ne pas interroger JIBI ce tour-ci
    POURSUIVRE = "poursuivre"    # continuer normalement (interroger JIBI)


def _traiter_slash(commande: str, argument: str, texte: str, *, assistant, memoire,
                    evolution, ecoute, voix_on: bool) -> tuple[str, bool, str]:
    """Exécute une commande slash. Renvoie (signal, voix_on, texte) à jour."""
    if commande in ("/quitter", "/exit", "/q"):
        return _Signal.ARRETER, voix_on, texte

    if commande == "/aide":
        print("Parle simplement à JIBI. Commandes : /outils (liste), /bilan (santé des "
              "outils), /workflows (routines), /sessions, /notes, /propositions, "
              "/autonomie [on|off HH:MM] (apprentissage planifié), /ameliorer [objectif] "
              "(cycle immédiat), /signaux (santé du PC), /tester <nom> (bac à sable), /valider <nom> (activer), "
              "/retirer <nom> (désactiver/restaurer), /verif (tests internes), /micro (parler), "
              "/voix on|off, /nouvelle, /quitter.")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/outils":
        from outils import OUTILS
        par_categorie: dict[str, list[str]] = {}
        for o in OUTILS.values():
            par_categorie.setdefault(o.categorie, []).append(f"{o.nom} [{o.risque}]")
        for cat, noms in sorted(par_categorie.items()):
            print(f"  {cat} : " + ", ".join(noms))
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/sessions":
        for sid, titre, n in memoire.lister_sessions():
            print(f"  #{sid} — {titre} ({n} message{'s' if n > 1 else ''})")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/notes":
        for n, t, h in memoire.lister_notes(15):
            print(f"  n°{n} — {t}  ({h})")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/propositions":
        print(evolution.lister_propositions())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/bilan":
        print(evolution.bilan())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/signaux":
        from outils import signaux
        print(signaux.tableau_signaux())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/workflows":
        from outils import workflows
        print(workflows.lister())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/tester":
        from jibi2 import labo
        argument = argument.strip().removesuffix(".py")
        if not argument:
            print("   Usage : /tester <nom>")
        else:
            print(labo.tester_proposition(argument)["resume"])
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/retirer":
        print(evolution.retirer(argument))
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/verif":
        print(evolution.lancer_verification())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/autonomie":
        from jibi2 import autonomie
        parties = argument.strip().split()
        if parties and parties[0].lower() in ("on", "off"):
            actif = parties[0].lower() == "on"
            heure = parties[1] if len(parties) > 1 else ""
            try:
                print(autonomie.configurer(actif, heure))
            except ValueError as e:
                print(f"   Autonomie : {e}")
        else:
            print(autonomie.statut())
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/ameliorer":
        from jibi2 import autonomie
        print("   JIBI démarre un cycle d'amélioration...")
        try:
            print(autonomie.executer_cycle(assistant, argument.strip(), force=True))
        except Exception as e:
            print(f"   Cycle impossible : {e}")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/valider":
        print(evolution.valider(argument))
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/micro":
        print("   Micro actif — parle, puis observe le silence.")
        entendu = ecoute.ecouter_phrase()
        if entendu:
            print(f"   tu as dit : {entendu}")
            return _Signal.POURSUIVRE, voix_on, entendu
        print("   (rien entendu : " + (ecoute.ERREUR_DERNIERE or "silence") + ")")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/voix":
        voix_on = argument.strip().lower() in ("on", "1", "oui")
        print(f"   Voix : {'on' if voix_on else 'off'}")
        return _Signal.CONTINUER, voix_on, texte

    if commande in ("/verrouiller_noyau", "/déverrouiller_noyau",
                    "/basculer_noyau"):
        from jibi2 import config as _config
        if commande == "/basculer_noyau":
            nouvelle = _config.basculer_noyau()
            if nouvelle == "0":
                print("   [VERROUILL] Noyau verrouillÉ — les modifications du code "
                      "demandent une confirmation.")
            else:
                print("   🔓 Noyau DÉVERROUILLÉ — les modifications du code "
                      "sont autorisées (avec confirmation à chaque fois).")
        elif commande == "/verrouiller_noyau":
            _config._cache = None
            # Forcer l'écriture à 0
            _env = _config.FICHIER_ENV
            if _env.exists():
                contenu = _env.read_text(encoding="utf-8", errors="replace")
                lignes = contenu.splitlines()
                nouvelles = []
                trouve = False
                for ligne in lignes:
                    if ligne.strip().startswith("JIBI_AUTONOMIE_NOYAU"):
                        nouvelles.append("JIBI_AUTONOMIE_NOYAU=0")
                        trouve = True
                    else:
                        nouvelles.append(ligne)
                if not trouve:
                    nouvelles.append("JIBI_AUTONOMIE_NOYAU=0")
                _env.write_text("\n".join(nouvelles) + "\n",
                                  encoding="utf-8")
            _config._cache = None
            print("   [VERROUILL] Noyau verrouillÉ — les modifications du code "
                  "demandent une confirmation.")
        else:  # /déverrouiller_noyau
            _env = _config.FICHIER_ENV
            if _env.exists():
                contenu = _env.read_text(encoding="utf-8", errors="replace")
                lignes = contenu.splitlines()
                nouvelles = []
                trouve = False
                for ligne in lignes:
                    if ligne.strip().startswith("JIBI_AUTONOMIE_NOYAU"):
                        nouvelles.append("JIBI_AUTONOMIE_NOYAU=1")
                        trouve = True
                    else:
                        nouvelles.append(ligne)
                if not trouve:
                    nouvelles.append("JIBI_AUTONOMIE_NOYAU=1")
                _env.write_text("\n".join(nouvelles) + "\n",
                                  encoding="utf-8")
            _config._cache = None
            print("   🔓 Noyau DÉVERROUILLÉ — les modifications du code "
                  "sont autorisées (avec confirmation à chaque fois).")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/basculer_deplacement":
        import config as _config
        ancien = _config.valeur_bool("CONFIRMER_DEPLACEMENT")
        nouvelle = _config.basculer_deplacement()
        self._maj_deplacement_bouton()
        if nouvelle == "0":
            print("   [AUTO] Deplacement AUTOMATIQUE — plus de confirmation demandee.")
        else:
            print("   [CONFIRMATION] Deplacement avec confirmation.")
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/gestionnaire_fichiers":
        from outils.fichiers import gestionnaire_fichiers
        arg = argument.strip().removesuffix(".py")
        print(gestionnaire_fichiers(arg or "lister"))
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/configurer_deplacement":
        from outils.fichiers import configurer_deplacement
        actif = argument.strip().lower() in ("true", "1", "oui", "on", "auto", "sans")
        print(configurer_deplacement(actif))
        return _Signal.CONTINUER, voix_on, texte

    if commande == "/nouvelle":
        sid = assistant.nouvelle_session()
        print(f"   Nouvelle session #{sid}.")
        return _Signal.CONTINUER, voix_on, texte

    print("   Commande inconnue. /aide pour la liste.")
    return _Signal.CONTINUER, voix_on, texte


def _lire_a_voix_haute(reponse, recu: list[str], lecteur, voix_on: bool, parole) -> None:
    if lecteur is not None:
        if "".join(recu).strip() == reponse["reponse"]:
            lecteur.terminer()
            lecteur.attendre()          # console : on attend la fin de la parole
        else:
            lecteur.couper()            # réponse corrigée : on coupe et on dit la finale
            if not parole.parler(reponse["reponse"]):
                print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "?") + ")")
    elif voix_on and not parole.parler(reponse["reponse"]):
        print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "?") + ")")


def _repondre_et_afficher(assistant, texte: str, voix_on: bool, flux_on: bool, parole) -> None:
    print("\nJIBI › ", end="", flush=True)
    recu: list[str] = []
    lecteur = parole.LecteurPhrases() if (voix_on and flux_on) else None

    def sur_delta(morceau: str, _recu=recu, _lecteur=lecteur) -> None:
        _recu.append(morceau)
        print(morceau, end="", flush=True)
        if _lecteur is not None:
            _lecteur.alimenter(morceau)

    try:
        reponse = assistant.repondre(texte, on_chunk=sur_delta if flux_on else None)
    except Exception as e:  # noqa: BLE001 — la console ne doit jamais planter
        reponse = {"reponse": f"Erreur interne : {e}", "actions": [], "ok": False}
    if "".join(recu).strip() != reponse["reponse"]:
        # rien diffusé, OU réponse corrigée après relance → affiche la finale
        if recu:
            print("\n   [réponse corrigée] ", end="")
        print(reponse["reponse"], end="")
    print()
    for a in reponse.get("actions", []):
        print("   Action terminée." if a.get("ok") else "   Action impossible.")
    _lire_a_voix_haute(reponse, recu, lecteur, voix_on, parole)


def lancer(assistant, garde, memoire, voix_on: bool = False, mains_libres: bool = False,
           annonces=None) -> None:
    from audio import ecoute, parole
    from jibi2 import config, evolution
    from jibi2.llm import ClientLLM

    if annonces is not None and not mains_libres:
        def _ecouter_annonces() -> None:
            while True:
                message = annonces.get()
                print(f"\n{message}\ntoi › ", end="", flush=True)
        threading.Thread(target=_ecouter_annonces, daemon=True).start()

    if mains_libres:
        from audio.mains_libres import boucle, confirmer_vocal
        garde.confirmer = confirmer_vocal
        with contextlib.suppress(KeyboardInterrupt):
            boucle(assistant)
        return

    garde.confirmer = confirmer_console

    client = ClientLLM()
    ok, _, _ = client.etat(force=True)
    _afficher_entete(client, ok, memoire, voix_on, ecoute)
    flux_on = config.valeur_bool("JIBI_FLUX")

    while True:
        try:
            texte = input("\ntoi › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texte:
            continue

        if texte.startswith("/"):
            commande, _, argument = texte.partition(" ")
            signal, voix_on, texte = _traiter_slash(
                commande.lower(), argument, texte,
                assistant=assistant, memoire=memoire, evolution=evolution,
                ecoute=ecoute, voix_on=voix_on)
            if signal == _Signal.ARRETER:
                break
            if signal == _Signal.CONTINUER:
                continue

        _repondre_et_afficher(assistant, texte, voix_on, flux_on, parole)