# 🤖 JIBI — assistant personnel local

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](#)

Assistant personnel **100 % local en français** : cerveau Ollama, voix Piper/Whisper,
contrôle du PC, recherche web, documents, domotique… et une **auto-amélioration supervisée**
(sandbox → tests → validation humaine) qui lui permet d'enrichir sa propre boîte à outils.

> 🔎 Documentation complète : **[LISEZMOI.md](LISEZMOI.md)** · Journal des évolutions : **[CHANGELOG.md](CHANGELOG.md)**

## ✨ Ce qu'il sait faire
- 🎙️ **À la voix** : « jibi, … » au micro (faster-whisper), réponses parlées (Piper), mains-libres
- 🧠 **Cerveau local** : Ollama (qwen3.5), streaming mot à mot, zéro cloud obligatoire
- 🧰 **Boîte à outils adaptative** : noyau de 24 outils + extension par mots-clés
  (fichiers, système, notes, rappels, web, Chrome, vision d'écran, PDF/Word/Excel, domotique…)
- 🏗️ **Auto-amélioration supervisée** : il propose du code, JIBI le teste en **bac à sable**
  (10 s, processus séparé, politique AST), puis **toi** tu valides — chaque écriture est
  atomique, hachée SHA-256, rollback si les tests échouent
- 🗓️ **Workflows programmés** : « chaque jour à 08:00, fais X »
- 🌐 **Panneau web local** (127.0.0.1 uniquement) + interface bureau Tkinter
- 🔌 **Serveur MCP** sur `127.0.0.1:8080` : exposé à tout client MCP compatible

## 🚀 Démarrage rapide
```powershell
# 1. Ollama + modèle
#    https://ollama.com  →  ollama pull qwen3.5:4b   (2b si moins de 16 Go de RAM)
# 2. Dépendances
pip install -r requirements.txt
# 3. Vérification complète (jusqu'à 0 ❌)
python docteur.py
# 4. Lancement
python run.py              # fenêtre de bureau
python run.py --console    # console
python run.py --mains-libres   # « jibi, … » au micro
```

## 🛡️ Sécurité
- `.env`, `donnees/`, `modeles/` et tout chemin hors projet : **intouchables** par l'auto-amélioration
- Actions dangereuses (`executer_commande`, `eteindre_pc`…) : **confirmation humaine**
- Suppression de fichiers → **corbeille**, jamais en dur
- Pages web = données non fiables : elles ne peuvent jamais déclencher une action
- Scripts générés : filtrés par AST, testés en sandbox, validés par l'humain

## 📄 Licence
[MIT](LICENSE) — utilisation, modification et redistribution libres avec mention de copyright.
