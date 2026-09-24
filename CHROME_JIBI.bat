@echo off
rem Chrome + JIBI : ouvre Chrome sur un profil dedie avec port de debogage.
rem Utile pour l'assistance onglets / resume de page. Depuis Chrome 136,
rem Google interdit le debogage distant sur le profil par defaut (securite) :
rem ce raccourci utilise donc un profil separe "ChromeJIBI".
rem Connecte-toi une fois a ton compte Google : c'est memorise dans ce profil,
rem et JIBI ne tape jamais de mot de passe, ne lit aucun cookie et ne gere
rem jamais le code 2FA a ta place.
setlocal
set JIBI_CDP_PORT=9333
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
  echo Chrome introuvable sur ce PC.
  pause
  exit /b 1
)
start "" "%CHROME%" --remote-debugging-port=%JIBI_CDP_PORT% --user-data-dir=%LOCALAPPDATA%\JIBI2\ChromeJIBI --no-first-run --no-default-browser-check https://www.google.com/
echo Chrome pret pour JIBI (Google, profil ChromeJIBI, port %JIBI_CDP_PORT%).
endlocal
