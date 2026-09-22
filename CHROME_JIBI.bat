@echo off
rem Chrome + JIBI : ouvre Chrome sur un profil dedie avec port de debogage.
rem Utile pour l'assistance onglets / resume de page. Depuis Chrome 136,
rem Google interdit le debogage distant sur le profil par defaut (securite) :
rem ce raccourci utilise donc un profil separe "ChromeJIBI".
rem Connecte-toi une fois aux sites ou tu veux de l'aide : c'est memorise,
rem et JIBI ne tape jamais de mot de passe ni ne clique a ta place.
setlocal
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
  echo Chrome introuvable sur ce PC.
  pause
  exit /b 1
)
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir=%LOCALAPPDATA%\JIBI2\ChromeJIBI --no-first-run --no-default-browser-check
echo Chrome pret pour JIBI (profil ChromeJIBI, port 9222).
endlocal
