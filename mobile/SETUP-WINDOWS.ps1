# =============================================================
#  FocusGuard — Installation Flutter + Build APK (Windows)
#  Usage :  powershell -ExecutionPolicy Bypass -File SETUP-WINDOWS.ps1
# =============================================================

$ErrorActionPreference = "Stop"

Write-Host "=== FocusGuard setup ===" -ForegroundColor Magenta

# --- 1. Flutter présent ? ---
$flutterCmd = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $flutterCmd) {
    Write-Host "Flutter absent — installation en cours..." -ForegroundColor Yellow
    $sdkRoot = "$env:USERPROFILE\flutter-sdk"
    $zip = "$env:TEMP\flutter.zip"
    $url = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.3-stable.zip"

    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $env:USERPROFILE -Force
    if (Test-Path $sdkRoot) { Remove-Item -Recurse -Force "$env:USERPROFILE\flutter" -ErrorAction SilentlyContinue }
    Move-Item "$env:USERPROFILE\flutter_windows_3.24.3-stable\flutter" -Destination "$env:USERPROFILE\flutter" -ErrorAction SilentlyContinue

    # Ajouter au PATH de l'utilisateur (permanent)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*flutter\bin*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$env:USERPROFILE\flutter\bin", "User")
    }
    $env:Path += ";$env:USERPROFILE\flutter\bin"
    Write-Host "Flutter installé dans $env:USERPROFILE\flutter" -ForegroundColor Green
}

flutter --version

# --- 2. Docteur : vérifier Android toolchain ---
flutter doctor

Write-Host ""
Write-Host "PRÉREQUIS ANDROID (si 'flutter doctor' se plaint) :" -ForegroundColor Yellow
Write-Host "  1. Installe Android Studio : https://developer.android.com/studio"
Write-Host "  2. Ouvre-le une fois → More Actions → SDK Manager → garde les défauts"
Write-Host "  3. Installe le JDK 17 (fourni avec Android Studio)"
Write-Host "  4. Accepte les licences :  flutter doctor --android-licenses"
Write-Host ""

# --- 3. Dépendances Dart ---
Write-Host "Récupération des dépendances..." -ForegroundColor Cyan
flutter pub get

# --- 4. Génération des fichiers de plateforme (si besoin) ---
if (-not (Test-Path "android\app\src\main\kotlin")) {
    Write-Host "Création de la plateforme android..." -ForegroundColor Cyan
    flutter create --platforms=android --org com.focusguard .
}

# --- 5. Build APK release (distribution bêta directe) ---
# NB : les sorties de build vont dans C:\Users\ulric\gradle-build\focusguard
# (configuré dans android/build.gradle.kts) car OneDrive verrouille les fichiers.
Write-Host "Compilation de l'APK..." -ForegroundColor Cyan
flutter build apk --release

$apk = "C:\Users\ulric\gradle-build\focusguard\app\outputs\flutter-apk\app-release.apk"
if (Test-Path $apk) {
    $size = [math]::Round((Get-Item $apk).Length / 1MB, 1)
    Write-Host ""
    Write-Host "✅ APK prêt : $apk ($size Mo)" -ForegroundColor Green
    Copy-Item $apk "$env:USERPROFILE\OneDrive\Desktop\FocusGuard.apk" -ErrorAction SilentlyContinue
    Write-Host "   → Copie sur le Bureau : FocusGuard.apk" -ForegroundColor Green
    Write-Host "   → Installe-le sur Android (autoriser 'sources inconnues')," -ForegroundColor Green
    Write-Host "     ou distribue-le à tes bêta-testeurs (WhatsApp/Drive/Telegram)." -ForegroundColor Green
} else {
    Write-Host "❌ Build échoué — vérifie les messages ci-dessus." -ForegroundColor Red
}
