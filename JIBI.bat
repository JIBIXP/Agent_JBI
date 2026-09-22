@echo off
rem Lanceur de JIBI 2 : double-clique ici (n'utilise pas l'extension
rem Code Runner de VS Code, elle ne lance pas le programme).
rem Options utiles dans PowerShell : python run.py --console / --voix / --mains-libres
title JIBI 2
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python introuvable : installe Python 3.12 depuis python.org puis reessaie.
  pause
  exit /b 1
)
python run.py %*
if errorlevel 1 (
  echo.
  echo JIBI s'est arrete sur une erreur. Copie le message ci-dessus.
  pause
)
