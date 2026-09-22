# JIBI 2 — le nouvel assistant local, écrit de zéro

**Ce projet n'a aucun fichier en commun avec l'ancien JIBI** : nouvelle
structure, nouveau code, nouveaux noms. Seules les habitudes restent :
Ollama pour le cerveau, tout tourne sur ton PC, configuration par `.env`.

```
JIBI2/
├── run.py               ← point d'entrée unique (fenêtre, console, mains-libres)
├── docteur.py           ← vérifie tout + --installer-voix + --modele
├── .env                 ← configuration (modèle, voix, sécurité)
├── jibi2/               ← le noyau
│   ├── config.py          lecture .env (sans dépendance), chemins
│   ├── llm.py             client Ollama (think off, streaming, erreurs en français)
│   ├── assistant.py       le cerveau : JSON outil/réponse + relance corrective
│   ├── memoire.py         SQLite : sessions, messages, notes, faits
│   ├── evolution.py       auto-amélioration : proposer, tester, valider, CHANGELOG
│   ├── labo.py            bac à sable (10 s, processus séparé) + analyse du code de JIBI
│   ├── planificateur.py   workflows programmés (« chaque jour à 08:00 »)
│   └── securite.py        RIEN de risqué sans ton autorisation
├── outils/              ← 67 outils (15 catégories), jeu adaptatif : noyau 20 + extension par mots-clés
│   ├── fichiers.py (8)  systeme.py (10)  applications.py (2)  web.py (2)
│   ├── notes.py (4)     memoire_faits.py (2)  calcul.py (1)  rappels.py (3)
│   ├── workflows.py (4) : routines, exécutables à heure fixe (« ⏰ 08:00 »)
│   ├── vision.py (1)    : voir_ecran — capture + modèle de vision CPU (moondream)
│   ├── documents.py (2) : creer_pdf + creer_word — vrais documents, sans dépendance
│   ├── méta auto-amélioration : proposer_nouvel_outil, lister_erreurs,
│   │     lire_code_outil, tester_proposition, lancer_verification
│   └── perso/           ← tes outils + ceux validés de JIBI
├── audio/               ← la voix
│   ├── parole.py          Piper local (fr) → pyttsx3 en secours
│   ├── ecoute.py          faster-whisper local → Google en secours

├── interface/
│   ├── bureau.py          LA BOULE : orbe animée (repos/écoute/réflexion/parole),
│   │                      streaming, rappels, autorisations, ⟳ reprise de session,
│   │                      ✍️ dictée en continu (dis « envoie » pour partir) — Tkinter pur
│   └── terminal.py        console avec /commandes
├── CHANGELOG.md          ← journal des évolutions (tenu par JIBI lui-même)
├── modeles/voix/        ← voix Piper (.onnx) — docteur.py --installer-voix
└── donnees/             ← créée au 1er lancement : mémo SQLite, fichiers,
                           corbeille, propositions, cache voix, journal
```

## Installation (une fois)

```
1.Installer Ollama (https://ollama.com) puis :  ollama pull qwen3.5:4b
2. pip install -r requirements.txt
3. python docteur.py --installer-voix     ← voix française (~63 Mo)
4. python docteur.py                      ← relance jusqu'à 0 ❌
```

**JIBI 2 est réglé pour un PC SANS GPU : tout tourne sur le CPU.**
- Modèle : `qwen3.5:4b` si ≥ 16 Go de RAM, sinon `qwen3.5:2b`
  (`python docteur.py --modele`). `JIBI_LLM_THINK=0` est essentiel sur CPU.
- Micro : whisper `small` en `int8` (défaut). Évite `medium`, très lent sans GPU.
- Voix : Piper tourne très bien sur CPU (~1 s de synthèse pour 5 s d'audio).
Ollama doit être récent (≥ 0.12) pour qwen3.5.

## Usage

```
python run.py                    la boule (fenêtre de bureau)
python run.py --console          console
python run.py --console --voix   console + JIBI parle
python run.py --mains-libres     « jibi, quelle heure est-il ? » au micro
                                 (wake-word neuronal si openwakeword installé)
```

Exemples : « quelle heure est-il ? » · « calcule 144/12 » · « prends note
que je dois appeler le garage » · « retiens que ma ville est Rennes » ·
« cherche le prix d'une 4070 sur le web » · « ouvre la calculatrice » ·
« liste mes notes » · « rappelle-moi dans 15 minutes de sortir le four » ·
« quels fichiers ai-je dans mon espace ? » · « regarde mon écran, quelle
application est ouverte ? » · « crée une routine du matin à 8 h qui me
donne l'heure et mes notes » (elle s'exécutera toute seule chaque jour) ·
« tes outils ont eu des erreurs ? analyse, propose et teste une correction ».

Streaming : la réponse s'affiche mot à mot pendant la génération
(JIBI_FLUX=1 par défaut ; mets 0 dans le .env pour l'ancien comportement).
Mains-libres : après une réponse, tu enchaînes sans redire « jibi »
pendant 60 s (JIBI_FENETRE_SUIVI). « stop » ou « au revoir » termine.

## Sécurité — ce que JIBI ne peut pas faire tout seul

- Les **écritures de fichiers** restent dans `donnees/fichiers/`
  (le reste du PC est lisible seulement, outil par outil, à risque « moyen »).
- Les actions **à risque élevé** (`executer_commande`, `eteindre_pc`)
  demandent ta confirmation (`CONFIRMER_RISQUES=1`, défaut).
- La suppression = **corbeille** `donnees/corbeille/` (récupérable).
- Les outils **proposés par JIBI** ne s'exécutent qu'après
  `/valider <nom>` — et il faut quand même les relire.

## Auto-amélioration — JIBI propose, tu disposes

Un cycle en 4 temps, tout en local, rien d'automatique :

1. **DÉTECTER** — chaque échec d'outil est noté dans
   `donnees/journal/erreurs.jsonl` (sans jamais faire planter JIBI).
2. **ANALYSER** — JIBI peut relire le journal (outil `lister_erreurs`)
   et son propre code (outil `lire_code_outil`).
3. **PROPOSER** — JIBI écrit un outil nouveau **ou une correction**
   (même nom qu'un outil existant) dans `donnees/propositions/` :
   le code reste inactif, blacklisté (`subprocess`, `os.system`…).
4. **DÉCIDER** — dans la console :
   - `/bilan`          → outils actifs, propositions en attente, erreurs
   - `/propositions`   → lire les propositions
   - `/valider <nom>`  → activer (l'ancienne version part dans
     `donnees/historique_outils/`)
   - `/retirer <nom>`  → désactiver ; si la proposition masquait un outil
     intégré, l'original est restauré tel quel

Exemple de demande qui déclenche le cycle : « tes outils ont eu des
erreurs ? analyse et propose une correction » — puis tu relis le fichier
proposé et tu fais `/valider`.

## Commandes console

`/aide /outils /bilan /workflows /sessions /notes /propositions
/valider <nom> /retirer <nom> /micro /voix on|off /nouvelle /quitter`

## Feuille de route (prochaines briques possibles)

1. Modèle wake-word personnalisé « jibi » : `python docteur.py --installer-wake`
   installe le modèle officiel « hey jarvis » ; pour un vrai « jibi », entraîne
   un modèle avec la recette openWakeWord (~30 min, Colab) et dépose le .onnx
   dans modeles/wake/ — JIBI le chargera tout seul.
2. Niveaux de risque N1/N2/N3 par outil (aujourd'hui : faible/moyen/élevé).
3. La boule réagit à la voix (visualisation du niveau sonore en direct).

## Assistance Chrome & lumière amaran (ADD 23)
- **Assistance Chrome** : double-clique `CHROME_JIBI.bat` (profil dédié « ChromeJIBI », port 9222 — depuis Chrome 136 le profil par défaut refuse le débogage). Puis : « quels onglets sont ouverts ? », « résume cette page », « passe sur l'onglet YouTube », « ferme l'onglet 2 » (confirmation demandée). Aucune donnée ne sort du PC, jamais de mot de passe, jamais de clic à ta place. JIBI lance Chrome tout seul si le port ne répond pas.
- **Lumière amaran** : matériel une fois — ESP32 (~5 €) flashé avec wesbos/amaran-BLE-control, puis `JIBI_AMARAN_URL=http://ip-esp32:2708` dans le .env. Ensuite : « allume la key light à 60 % », « amaran en 5600 kelvin », « éteins la lumière vidéo ». (Godox TL60/DMX : à venir, même chez Jarvis.)

## Panneau web, souris & jeux (ADD 24 — adapté de Jarvis)
- **Panneau web local** : lancé automatiquement par run.py → http://127.0.0.1:8756 (127.0.0.1 UNIQUEMENT, rien ne sort du PC). Page HTML discutée au clavier, état du modèle, raccourcis. « ouvre le panneau » marche aussi à la voix. Port : JIBI_PANNEAU_PORT dans le .env.
- **Souris** (Windows, ctypes natif) : « déplace la souris à 90, 95 » (pourcentages d'écran), « fais défiler vers le bas » ; le CLIC est confirmé par toi à chaque fois. Combine avec voir_ecran pour viser.
- **Jeux 100 % locaux** : « lance un dé », « pile ou face », « on joue à pierre feuille ciseaux, je joue pierre », « commence le nombre mystère »… c'est 50, plus grand ? 🎲

## Version & mise à jour (ADD 26)
- Le fichier **VERSION** donne ta version (« es-tu à jour ? » → outil verifier_mise_a_jour).
- **Auto-amélioration des outils** : JIBI propose (proposer_nouvel_outil) → teste en bac à sable (tester_proposition, sécurité + SHA-256) → **TOI valides** → activé. Retour arrière : « retire l'outil X ». Tout est tracé dans le CHANGELOG.
- **Mise à jour de JIBI lui-même : jamais automatique** (il ne remplace pas son noyau tout seul). Pour vérifier à distance : héberge un fichier texte avec la dernière version et mets l'URL dans JIBI_VERSION_URL (.env). Procédure : nouveau zip → remplacer le dossier en gardant donnees/ et modeles/voix/.

## Autonomie graduée (ADD 27) — LA règle demandée
- **Seul, sans demander** : créer/tester/**activer** ses outils (proposer → tester → activer_proposition), ajouter des fonctionnalités, changer son design (personnaliser_design : couleurs de l'orbe et du panneau — `donnees/design.json`, survit aux mises à jour). « reset le design » = retour à l'origine.
- **Le noyau (jibi2/, outils intégrés, interface, run.py, docteur.py, tests) → TOUJOURS une permission** : la boîte « Puis-je le faire ? » s'affiche avec la raison. Si accepté : sauvegarde auto + tests relancés + **retour arrière automatique si les tests cassent**. « restaure le fichier X » pour revenir en arrière.
- **Jamais touchable** : `.env` (secrets), `donnees/` (tes données), `modeles/` (modèles), tout chemin hors du dossier JIBI.

## Voix au choix & parole fluide (ADD 28)
- **Changer de voix** : dis « change ta voix » ou « mets une voix masculine » → JIBI télécharge et active tout seul. Voix : **siwis (femme, actuelle)**, **tom (homme)**, upmc (homme), gilles (homme, léger). Effet immédiat, sans redémarrage (outil changer_voix).
- **Parole au fil de l'eau** : JIBI parle **dès la première phrase complète** pendant que le modèle écrit la suite (avant : il attendait la réponse entière avant de synthétiser). Premier mot audible en ~2-3 s au lieu de 5-12 s.
- Réglage fin : PIPER_MODELE dans le .env (vide = première voix du dossier).

## Si JIBI est lent chez toi (ADD 29)
1. `python docteur.py --vitesse` → chronomètre RÉEL (chargement, tokens/s, pré-remplissage) + conseils.
2. Levier n°1 : `ollama pull qwen3.5:2b` puis `python docteur.py --vitesse --adopte` → chronomètre tous tes modèles et bascule le .env sur le plus rapide, tout seul.
3. Fais « nouvelle session » de temps en temps (l'historique est déjà compressé, mais une session fraîche aide).
4. Réglages fins : JIBI_LLM_MAX (plafond de génération), JIBI_LLM_CTX (fenêtre de contexte) dans le .env.

## Lancer JIBI
- **Double-clique sur `JIBI.bat`** (à la racine) — c'est tout.
- Ou dans PowerShell : `cd C:\Users\ulric\Downloads\JIBI2_nouveau` puis `python run.py` (options : `--console`, `--voix`, `--mains-libres`).
- ⚠️ N'utilise pas l'extension Code Runner de VS Code pour lancer JIBI : son fichier temporaire n'exécute rien (juste un `echo.`).
- Chronomètre/vitesse : `python docteur.py --vitesse`.

## Apprendre sur le web (ADD 31)
Dis-lui par exemple :
- « cherche sur le web comment calculer une distance entre deux mots, fabrique-toi l'outil, teste-le et active-le » → il cherche, écrit l'outil, le teste en bac à sable, l'active SEUL et te cite la source ;
- « ajoute la fonctionnalité X à ton code » → il prépare la modification et, comme c'est le noyau, la boîte « Puis-je le faire ? » s'affiche ; si les tests cassent après, retour arrière automatique.
Garde-fous : scan sécurité (refuse subprocess/suppression…), bac à sable 10 s, SHA-256, tout réversible (« retire l'outil X » / « restaure le fichier Y »).
