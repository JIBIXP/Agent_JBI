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
│   ├── evolution.py       auto-amélioration : proposer, tester, activer, CHANGELOG
│   ├── autonomie.py       cycle d'apprentissage web + noyau transactionnel
│   ├── sources.py         recherche web publique + provenance des sources
│   ├── progression.py     jauge d'évolution partagée par le bureau et le panneau
│   ├── audit.py           journal append-only et chaîne de hachage
│   ├── labo.py            bac à sable (10 s, processus séparé) + politique AST
│   ├── planificateur.py   workflows programmés (« chaque jour à 08:00 »)
│   └── securite.py        garde des actions sensibles + autonomie du code
├── outils/              ← 111 outils (18 catégories), jeu adaptatif : noyau 24 + extension par mots-clés
│   ├── fichiers.py (8)  systeme.py (10)  applications.py (2)  web.py (5)
│   ├── notes.py (4)     memoire_faits.py (2)  calcul.py (1)  rappels.py (3)
│   ├── workflows.py (4) : routines, exécutables à heure fixe (« ⏰ 08:00 »)
│   ├── vision.py (2)    : voir_ecran / voir_image — capture ou image locale + modèle de vision CPU (moondream)
│   ├── navigateur.py (7): Browser Use local + recherche vidéo/musique/site + navigation autonome
│   ├── documents.py (2) : creer_pdf + creer_word — vrais documents, sans dépendance
│   ├── analyse.py (3)   : analyser_fichier + analyser_dossier + recherche PC
│   ├── bureautique.py (3): créer/analyser Excel + analyse de documents
│   ├── localisation.py (2): position approximative et lieux proches
│   ├── traduction.py (2): traduire + langues_disponibles — 16 langues, Ollama ou dictionnaire de base
│   ├── imports.py (2)   : importer_fichier, importer_image — import sécurisé PC → JIBI
│   └── __init__.py      : registre NOYAU (24 outils) + DOMAINES (patterns contextuels)
├── interface/           ← bureau.py (barre auto-étendue, icônes), terminal.py (commandes /)
│   ├── signaux.py (3)   : tableau de santé, réseau et vérifications winget
│   ├── méta auto-amélioration : proposer_nouvel_outil, lister_erreurs,
│   │     lire_code_outil, lire_code_noyau, tester_proposition, lancer_verification,
│   │     modifier_noyau, ameliorer_autonomement, configurer_autonomie,
│   │     consulter_audit
│   └── perso/           ← tes outils + ceux validés de JIBI
├── audio/               ← la voix
│   ├── parole.py          Piper local (fr) → pyttsx3 en secours
│   ├── ecoute.py          faster-whisper local → Google en secours

├── interface/
│   ├── theme.py           palette, polices, espacements et metrics UI
│   ├── bureau.py          barre latérale rétractable + zone principale : orbe animée,
│   │                      chat, voix, bibliothèque intégrée, sessions et documents — Tkinter pur
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
« cherche le prix d'une 4070 sur le web » · « ouvre mon compte Google » ·
« ouvre la calculatrice » · « liste mes notes » · « rappelle-moi dans
15 minutes de sortir le four » · « tes outils ont eu des erreurs ? analyse,
propose, teste et active une correction » · « améliore-toi sur les rappels ».

Dans la console :
- `/autonomie` — état de l'apprentissage autonome ;
- `/autonomie on 04:00` — active un cycle quotidien à 4 h ;
- `/ameliorer` — lance un cycle immédiat ;
- `/tester`, `/valider`, `/retirer`, `/verif` — pilotage des propositions.

Streaming : la réponse s'affiche mot à mot pendant la génération
(JIBI_FLUX=1 par défaut ; mets 0 dans le .env pour l'ancien comportement).
Mains-libres : après une réponse, tu enchaînes sans redire « jibi »
pendant 60 s (JIBI_FENETRE_SUIVI). « stop » ou « au revoir » termine.

## Sécurité — autonomie de code activée

- Les écritures utilisateur restent dans `donnees/fichiers/` ; `.env`,
  `donnees/`, `modeles/` et tout chemin extérieur au projet ne sont jamais
  modifiables par l'auto-amélioration.
- `JIBI_MODIFICATION_AUTO=1` autorise JIBI à modifier **et restaurer** son
  propre code sans redemander à chaque fois. Chaque écriture est atomique,
  sauvegardée, vérifiée et rollbackée si la suite de tests échoue.
- Les actions système dangereuses (`executer_commande`, `eteindre_pc`, etc.)
  conservent leur confirmation habituelle.
- Un outil généré est filtré par AST : un seul décorateur, aucun import
  système/réseau/fichier, aucun `eval`/`exec`/`open`, pas de boucle infinie.
  Le test est ensuite exécuté dans un worker séparé, sans secrets hérités.
- Les pages web sont marquées « données non fiables » : leur contenu ne peut
  jamais autoriser une action. Les URL loopback, privées et metadata sont
  refusées pour l'apprentissage autonome.
- La suppression de fichiers utilisateur passe par la corbeille.

## Auto-amélioration — recherche → code → test → application

Le cycle peut être demandé avec « améliore-toi » ou lancé automatiquement :

1. **DÉTECTER** — les erreurs d'outils sont enregistrées dans
   `donnees/journal/erreurs.jsonl` ;
2. **RECHERCHER** — JIBI consulte des sources web publiques et les traite
   comme des données non fiables ;
3. **PROPOSER** — il crée un outil pur dans `donnees/propositions/`, ou
   prépare une correction du noyau via `lire_code_noyau` ;
4. **TESTER** — syntaxe, politique AST, worker isolé, cas d'essai et suite
   complète du projet ;
5. **APPLIQUER** — un outil sûr peut être activé automatiquement ; une
   modification du noyau est sauvegardée puis appliquée sans confirmation
   quand `JIBI_MODIFICATION_AUTO=1`, avec retour arrière automatique.

Pour une improvement qui exige un outil avec fichier, réseau, processus ou
une API particulière, JIBI passe par le noyau ou attend une validation
humaine : les tests ne valent jamais permission.

Dans la console :
- `/bilan` → outils, propositions et erreurs ;
- `/propositions` → lire les artefacts en attente ;
- `/valider <nom>` / `/retirer <nom>` → gestion manuelle ;
- `/ameliorer [objectif]` → cycle immédiat ;
- `/autonomie on|off HH:MM` → cycle quotidien.

## Commandes console

`/aide /outils /bilan /signaux /workflows /sessions /notes /propositions
/tester <nom> /valider <nom> /retirer <nom> /verif /autonomie [on|off HH:MM]
/ameliorer [objectif] /micro /voix on|off /nouvelle /quitter`

## Feuille de route (prochaines briques possibles)

1. Modèle wake-word personnalisé « jibi » : `python docteur.py --installer-wake`
   installe le modèle officiel « hey jarvis » ; pour un vrai « jibi », entraîne
   un modèle avec la recette openWakeWord (~30 min, Colab) et dépose le .onnx
   dans modeles/wake/ — JIBI le chargera tout seul.
2. Niveaux de risque N1/N2/N3 par outil (aujourd'hui : faible/moyen/élevé).
3. La boule réagit à la voix (visualisation du niveau sonore en direct).

## Assistance Chrome & lumière amaran (ADD 23)
- **Compte Google / ChromeJIBI** : double-clique `CHROME_JIBI.bat`. Il ouvre
  Google dans un profil dédié (`%LOCALAPPDATA%\\JIBI2\\ChromeJIBI`,
  port 9333). Connecte-toi **toi-même une fois** si tu le souhaites ; JIBI ne lit jamais le mot de
  passe, les cookies ou le code 2FA. Ensuite, dis « ouvre mon compte Google » :
  l'outil `ouvrir_compte_chrome` retrouve le profil et affiche l'onglet de session.
  Depuis Chrome 136, le profil Chrome par défaut refuse le débogage distant ;
  JIBI ne copie donc pas tes cookies vers un autre profil.
- **Assistance Chrome** : « quels onglets sont ouverts ? », « cherche Claude IA
  avec Chrome en arrière-plan » (vrai Chrome headless local, sans fenêtre ;
  repli ChromeJIBI non affiché si Google bloque la session temporaire ;
  `JIBI_CHROME_SEARCH_BACKGROUND=1` par défaut),
  « ouvre Chrome et montre les résultats » (`chercher_dans_chrome`, visible),
  « résume cette page », « passe sur l'onglet YouTube », « ferme l'onglet 2 »
  (confirmation demandée). JIBI ne fait pas de clic ni de saisie à ta place et
  ne contourne jamais un CAPTCHA.
- **Lumière amaran** : matériel une fois — ESP32 (~5 €) flashé avec
  wesbos/amaran-BLE-control, puis `JIBI_AMARAN_URL=http://ip-esp32:2708` dans
  le .env. Ensuite : « allume la key light à 60 % », « amaran en 5600 kelvin »,
  « éteins la lumière vidéo ».

## Navigation Browser Use locale

Browser Use est installé et fonctionne avec Chrome local + Ollama, sans
`BROWSER_USE_API_KEY`, sans proxy cloud et sans télémétrie. Le profil Chrome
utilisé par l'agent est temporaire : aucun cookie ni état de connexion n'est
réutilisé par ce mode.

- « ouvre cette page avec Browser Use et résume-la » (`lire_site_browser`) ;
- « navigue sur ce site et trouve les informations sur… » (`naviguer_browser_use`) ;
- « cherche une vidéo de… » (`chercher_video`) ;
- « trouve ce morceau / cet artiste » (`chercher_music`) ;
- « trouve le site officiel de… » (`chercher_site`).

Le mode Browser Use reste en **lecture seule** : il ne saisit pas de
formulaire, ne se connecte pas, ne paie rien et ne confirme aucun envoi ou
suppression. `JIBI_BROWSER_HEADLESS=0` garde la fenêtre visible pour la navigation générale ;
la recherche Google dédiée utilise toutefois un Chrome headless local sans
fenêtre. `JIBI_BROWSER_VISION=0` évite les captures et laisse le DOM/local Ollama
plus léger. Les recherches de vidéos, musiques et sites ne téléchargent pas les
médias et ne contournent aucun DRM ou paywall.

## Documents JIBI

Les documents suivent une chaîne stable : JIBI remplit une spécification JSON,
choisit un thème (`sobre`, `coloré`, `scolaire`, `moderne_sombre`,
`professionnel` ou `enfant`), produit un HTML/CSS protégé puis le convertit en
PDF avec Chromium headless local. Le HTML source est conservé à côté du PDF.
Les formats Word et Excel passent respectivement par `python-docx` et
`openpyxl` ; PowerPoint utilise `python-pptx`. Un générateur de secours
standard reste disponible pour les PDF et Word.

Demande un modèle avec :

```text
Donne-moi un exemple de document JIBI.
```

Les exemples complets sont dans `docs/exemples_documents.json`. Dans
l'onglet **Documents**, le bouton **Importer document / image** copie les
fichiers choisis dans `donnees/fichiers/imports` ; ils peuvent ensuite être
analysés ou utilisés dans un nouveau document.

Pour une demande comme « fais un petit cours sur les tableaux de signes sous
forme de document Word », JIBI lance automatiquement une recherche Google
headless locale, se replie sur une recherche HTTP silencieuse si nécessaire,
lit quelques pages publiques, rédige un résumé puis crée le Word. Il n’est
pas nécessaire de demander explicitement « cherche sur Google » ; aucune
authentification, aucun formulaire et aucune publication ne sont effectués.

Les tableaux sont créés de façon structurée ; par exemple, «crée un tableau Excel pour mon budget» ou «crée un tableau dans un document Word». Une section de type `tableau` utilise `colonnes` et `lignes`. JIBI peut aussi créer un simple dessin ou diagramme coloré avec des emojis et du texte (par exemple, «fais un dessin avec des emotifs»). Il s’agit d’une illustration locale dans un document, sans générateur d’images distant.

Tu peux ensuite demander «mets le fichier dans Téléchargements» ou «copie-le dans Bureau». JIBI exporte un fichier depuis `donnees/fichiers` vers un dossier précis, avec confirmation, chemin exact et sans écrasement. Il ne copie pas automatiquement le même fichier dans tous les dossiers du PC.

## Panneau web, souris & jeux (ADD 24 — adapté de Jarvis)
- **Barre latérale JIBI** : la fenêtre principale utilise une barre gauche rétractable et
  redimensionnable. Elle contient Nouvelle session, Bibliothèque, Documents, Signaux,
  les sessions récentes et le zoom. La Bibliothèque et les Documents s'affichent dans
  la zone principale avec leurs onglets, sans popup ni nouvelle page.
- **Conversation lisible** : Segoe UI 14, texte blanc cassé sur fond sombre, titres
  blancs et gras, informations secondaires en gris clair. Les messages de JIBI et
  de l'utilisateur ont des marges/fonds distincts ; les sorties système utilisent
  Consolas dans un bloc légèrement plus clair. Les espaces insécables et les
  décodages Windows invalides sont nettoyés avant affichage.
- **Panneau web local** : lancé automatiquement par run.py → http://127.0.0.1:8756
  (127.0.0.1 UNIQUEMENT). Chat écrit, ondes bleues/violettes pendant l'écoute,
  lueur violette pendant la parole, jauge d'évolution, signaux du PC et boutons
  de téléchargement des documents. Si tu demandes « peux-tu faire une recherche
  avec Chrome ? », le sujet bref envoyé juste après est recherché avec Chrome
  headless en arrière-plan, sans afficher Chrome. Dis explicitement « montre la
  page » ou « ouvre Chrome » pour l'afficher. Le champ web utilise aussi une
  zone multiligne auto-extensible et la touche Entrée pour envoyer. Dans la
  fenêtre de bureau, la capsule du bas ne contient que des icônes : parole,
  arrêt, dictée, trombone et envoi ; chaque icône possède une infobulle.
  Le bouton Documents ouvre la liste des fichiers dans la fenêtre principale ;
  il n'ouvre plus un autre onglet. L'icône de parole est un interrupteur simple :
  active quand elle est violette, elle autorise la voix ; décochée, JIBI reste
  muet. « Nouvelle session » nettoie le contexte et l'historique affiché.
  Dans **Bibliothèque → Sessions**, sélectionne une session puis utilise
  **Supprimer la session** ; la même option est disponible sous les sessions
  récentes. Une confirmation est toujours demandée avant la suppression
  définitive de ses messages. Le clic droit sur une session ouvre aussi ce menu.
  Port : `JIBI_PANNEAU_PORT` dans le `.env`.
- **Souris** (Windows, ctypes natif) : « déplace la souris à 90, 95 » (pourcentages d'écran), « fais défiler vers le bas » ; le CLIC est confirmé par toi à chaque fois. Combine avec voir_ecran pour viser.
- **Jeux 100 % locaux** : « lance un dé », « pile ou face », « on joue à pierre feuille ciseaux, je joue pierre », « commence le nombre mystère »… c'est 50, plus grand ? 🎲

## Version & mises à jour
- Le fichier **VERSION** donne ta version (« es-tu à jour ? » → `verifier_mise_a_jour`).
- JIBI peut améliorer son code source en autonomie, mais ne remplace jamais
  automatiquement son installation complète (zip, dépendances ou modèle) :
  cela reste une opération de mise à jour de paquet, distincte d'une
  modification transactionnelle du code.
- `verifier_mises_a_jour_pc` vérifie winget sans installer ;
  `installer_mise_a_jour` demande une confirmation explicite.
- L'auto-amélioration et chaque décision sont tracées dans
  `donnees/journal/audit.jsonl` avec une chaîne de hachage.

## Autonomie du code et des outils
- **Seul, sans demander** : rechercher, analyser, créer/tester/activer un
  outil pur, corriger un outil personnel et personnaliser le design.
- **Noyau** : l'auto-amélioration peut proposer une modification, mais
  `JIBI_AUTONOMIE_NOYAU=0` garde une confirmation humaine obligatoire avant
  d'écrire dans le noyau. `JIBI_MODIFICATION_AUTO=1` active le mode de
  modification, les tests et le retour arrière, mais ne contourne pas cette
  confirmation.
- **Toujours protégé** : `.env` (secrets), `donnees/`, `modeles/`, les
  navigateurs/cookies et tout chemin extérieur au projet.
- Chaque modification du noyau est atomique, sauvegardée, testée et
  automatiquement restaurée si elle casse ; `/restaurer_noyau` reste possible.
- `/autonomie on 04:00` programme le cycle quotidien ; `/ameliorer` le lance
  immédiatement. `JIBI_SIGNAL_ACTIF=1` ajoute une alerte PC quotidienne à
  `JIBI_SIGNAL_HEURE`. La jauge du panneau montre les étapes et le pourcentage.
- L'interface ne montre plus les noms internes de fonctions/outils : elle
  affiche seulement des résolutions en langage naturel. La voix masculine
  **Tom** est active par défaut.


## Voix au choix & parole fluide (ADD 28)
- **Changer de voix** : dis « change ta voix » ou « mets une voix masculine » → JIBI télécharge et active tout seul. Voix : **tom (homme, actuelle)**, siwis (femme), upmc (homme), gilles (homme, léger). Effet immédiat, sans redémarrage (outil changer_voix).
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

## Apprendre sur le web et appliquer au code
Dis-lui par exemple :
- « cherche sur le web comment calculer une distance entre deux mots,
  fabrique-toi l'outil, teste-le et active-le » ;
- « ajoute la fonctionnalité X à ton code » ;
- « cherche des images de chiens et montre-moi leurs sources » ;
- « analyse mes documents et signale-moi les signaux importants » ;
- « crée un tableau Excel avec mon budget » ;
- « où suis-je et trouve une pharmacie près de moi » ;
- « va sur ce site et résume-le ».

- « va sur ce site et résume-le » (`visiter_site`).

La localisation est une estimation de ville via la connexion réseau, pas un
GPS précis ; aucune adresse IP n'est conservée. `JIBI_GEOLOCATION=0` la
désactive complètement.

Pour les images, JIBI peut renvoyer les résultats, leurs sources et licences,
télécharger une image dans l'espace de travail avec `telecharger_image_web`,
puis l'observer avec `voir_image` si le modèle de vision local est installé.

## Nouveautés (dernière mise à jour)

### Transfert de fichiers sans confirmation (`CONFIRMER_DEPLACEMENT=0`)
JIBI peut maintenant déplacer/copier des fichiers vers les dossiers personnels du PC
(Téléchargements, Bureau, Documents, Images, etc.) **sans demander de confirmation**.
- Toggle : `/basculer_deplacement` ou bouton [CONFIRMATION] dans la barre
- Le flag `CONFIRMER_DEPLACEMENT=0` dans `.env` active le mode auto
- `configurer_deplacement` : outil pour JIBI lui-même de basculer ce flag

### Navigation autonome
JIBI peut naviguer sur le web de manière autonome :
- `naviguer_autonome` : recherche Google headless, lit des pages, résume
- `chercher_google_headless` : recherche Chrome locale sans fenêtre visible
- `naviguer_browser_use` : navigation interactive avec raisonnement local
- Les outils web sont dans le NOYAU pour l'accès autonome

### Traduction (`traduire`, `langues_disponibles`)
16 langues supportées : français, anglais, espagnol, allemand, italien,
portugais, chinois, japonais, coréen, arabe, russe, néerlandais, polonais,
turc, vietnamien, thaï.
- Utilise Ollama local, avec fallback par dictionnaire si Ollama indisponible
- Commande : `traduire` ou `/traduire`

### Importation de documents et images
- `importer_fichier` : importe PDF, Word, Excel, images depuis le PC vers JIBI
- `_dossier_pc_valide` accepte tous les dossiers personnels sous `C:\Users\username\`
- `gestionnaire_fichiers` : liste et navigue tous les dossiers du PC
- Images : `voir_image` avec modèle de vision local (moondream)

### Jeu adaptatif étendu
111 outils dans 18 catégories. NOYAU = 24 outils essentiels toujours visibles.
DOMAINES = patterns contextuels qui ajoutent des outils selon le contexte.
- `/configurer_deplacement` : commande slash pour le toggle de confirmation
- `/gestionnaire_fichiers` : gestion des dossiers du PC
- `/traduire` : traduction directe
