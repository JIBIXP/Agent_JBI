# Activer le mode défi social (Firebase) — 15 minutes

Le code est déjà intégré. Sans ces étapes, l'app fonctionne parfaitement en
local (le mode défi affiche juste « Firebase non configuré »).

## 1. Créer le projet Firebase

1. Va sur https://console.firebase.google.com → **Ajouter un projet**
   (ex : `focusguard-prod`).
2. **Firestore Database** → Créer → mode production → région `europe-west`.
3. **Authentication** → Commencer → fournisseur **Google** → Activer
   (choisis un e-mail de support).

## 2. Enregistrer l'app Android

1. Vue d'ensemble du projet → **icône Android** → package :
   `com.focusguard.app`
2. **SHA-1 obligatoire** pour Google Sign-In. Récupère-le :
   ```powershell
   cd mobile\android
   .\gradlew signingReport 2>$null | Select-String "SHA1"
   ```
   (si Gradle demande le JDK : il est déjà configuré via gradle.properties)
3. Télécharge `google-services.json` → place-le dans `mobile/android/app/`.

## 3. Générer la config Flutter

```powershell
# Une seule fois :
dart pub global activate flutterfire_cli

cd mobile
flutterfire configure
# → choisis le projet focusguard-prod, plateforme android uniquement
# → cela remplace lib/firebase_options_stub.dart par le vrai fichier
```

## 4. Coller les règles de sécurité

Firebase Console → Firestore → **Règles** → copie le contenu de
`firestore.rules` (à la racine de mobile/) → Publier.

Ces règles garantissent : chacun n'écrit que son score, pseudo ≤ 25 caractères,
minutes plausibles (≤ 7 jours), classement lisible uniquement par les membres.

## 5. Rebuild avec le flag d'activation

```powershell
flutter build apk --release --dart-define=FIREBASE_AVAILABLE=true
```

> Si tu buildes sans le flag, le mode défi reste désactivé (comportement
> actuel) — utile pour les tests hors ligne.

L'APK final sort toujours dans
`C:\Users\ulric\gradle-build\focusguard\app\outputs\flutter-apk\`
et une copie `FocusGuard.apk` est posée sur le Bureau par SETUP-WINDOWS.ps1.

## 6. Tester

1. Installe l'APK → onboarding → « Continuer avec Google » → choisis ton compte.
2. Onglet **Défis** → « Créer un groupe » → un code à 6 caractères s'affiche.
3. Envoie le code à un ami (il installe l'app, se connecte, « Rejoindre »).
4. Chaque session terminée met à jour le classement **en temps réel**
   (stream Firestore, sans pull-to-refresh).

## Coût

Le plan gratuit **Spark** de Firebase suffit largement au lancement :
- Firestore : 1 Go stocké, 50k lectures/jour — un groupe de 20 amis qui
  bloque 3×/jour ≈ quelques centaines de lectures/jour.
- Auth Google : illimité gratuit.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| « Connexion impossible » au sign-in | SHA-1 absent de Firebase Console, ou google-services.json manquant |
| `UnsupportedError: Firebase non configuré` | build sans `--dart-define=FIREBASE_AVAILABLE=true` |
| Code de groupe refusé | vérifier majuscules ; le code fait exactement 6 caractères |
| Classement figé | règles Firestore non publiées, ou pas membre du groupe |
