@echo off
title Installation de JIBI 2
cd /d "%~dp0"
echo.
echo ============================================
echo   Installation de JIBI 2 (tout-en-un)
echo ============================================
echo.
echo === 1/4 : installation des bibliotheques (quelques minutes) ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo === 2/4 : telechargement de la voix francaise (~63 Mo, une fois) ===
python docteur.py --installer-voix
echo.
echo === 3/4 : visite medicale (relance ce script tant qu'il reste des X rouges) ===
python docteur.py
echo.
echo === 4/4 : a telecharger avec Ollama (une fois) ===
echo     ollama pull qwen3.5:4b     (le cerveau, ~3,4 Go)
echo     ollama pull moondream      (optionnel : vision d'ecran, ~1,4 Go)
echo.
echo ============================================
echo   Termine ! Pour lancer JIBI :   python run.py
echo   (la boule apparait, clique dessus pour parler)
echo ============================================
pause
