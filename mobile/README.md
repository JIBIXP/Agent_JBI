# FocusGuard 🛡️

**Bloque tes réseaux sociaux. Gagne ta concentration.**

Application mobile iOS + Android (Flutter) qui bloque Instagram, TikTok, X et
Snapchat pendant une durée choisie — pour réviser, travailler, ou casser
l'usage compulsif.

---

## Fonctionnalités MVP (implémentées dans ce repo)

| Fonctionnalité | État |
|---|---|
| Sélection d'apps à bloquer (liste à cocher) | ✅ |
| Minuteur : 15 min / 30 min / 1 h / 2 h | ✅ |
| Mode « Révision » : Pomodoro 25/5 intégré | ✅ |
| Blocage strict (verrouillé) / friction 10 s | ✅ |
| Notification de fin de session | ✅ |
| Statistiques : temps hebdo, apps les plus bloquées | ✅ |
| Série (streak) : jours consécutifs objectif atteint | ✅ |
| Widget écran d'accueil (lancement en un tap) | ✅ Android |
| Détection + écran de blocage natifs | ✅ Android / 📋 iOS (guide) |
| Onboarding cinématique + page Confidentialité | ✅ |
| Paywall : essai 30 jours (RevenueCat) | ✅ (clé à fournir) |

### Différenciation (préparé)
- **IA de suggestion** : détection des heures d'abandon + créneaux de blocage
  proposés (`lib/services/insights_service.dart`) — heuristique v1, extensible LLM.
- **Défi social + récompenses réelles** : à venir (backend Firebase/Supabase).

---

## Stack

- **Flutter/Dart** — UI unique iOS+Android, design « Charbon & Violet »
  cinématique (dégradé violet profond → noir, halo lumineux, boutons pill).
- **Natif Android (Kotlin)** — `AccessibilityService` (détection d'ouverture),
  `BlockActivity` plein écran (shield), `AlarmManager` (fin de session même
  app fermée), widget home screen, App Widgets API.
- **Natif iOS** — FamilyControls + ManagedSettings + DeviceActivity (guide
  détaillé dans `ios/README.md`, à construire sur Mac en Phase 2).
- **RevenueCat** — abonnement unifié (l'essai 30 jours se configure côté
  App Store Connect / Play Console ; rappel de fin d'essai inclus).
- **Aucune donnée sociale lue** : détection système uniquement. RGPD-friendly,
  tout est local, suppression en un tap.

---

## Démarrage rapide (Windows, Phase 1 — Android)

```powershell
cd mobile
powershell -ExecutionPolicy Bypass -File SETUP-WINDOWS.ps1
```

Le script :
1. installe Flutter s'il manque (SDK stable 3.24),
2. lance `flutter doctor` (te dit ce qu'il faut pour Android Studio),
3. `flutter pub get`,
4. compile l'APK.

> **Emplacement de l'APK** : `C:\Users\ulric\gradle-build\focusguard\app\outputs\flutter-apk\app-release.apk`
> (les sorties de build sont volontairement hors de OneDrive, qui verrouille les fichiers ; une copie
> `FocusGuard.apk` est posée sur le Bureau après chaque build). Le JDK utilisé est celui d'Android
> Studio (`org.gradle.java.home` dans `android/gradle.properties`) — le Java système 25 est trop
> récent pour Gradle 8.7.

### Prérequis manuels (une seule fois)
- **Android Studio** (fournit SDK + JDK 17) : https://developer.android.com/studio
- `flutter doctor --android-licenses`
- Pour tester en live : un téléphone Android en mode développeur + USB
  (`flutter run`) — l'émulateur ne montre pas bien le blocage réel.

### Distribution bêta (sans compte développeur)
L'APK release se partage directement (Drive, Telegram, WhatsApp). Sur le
téléphone : « Installer des apps inconnues » → installer. Pour les mises à
jour : redéballer le nouvel APK.

---

## Architecture du code

```
mobile/
├── lib/
│   ├── main.dart                  # bootstrap (notifications, RevenueCat)
│   ├── core/
│   │   ├── theme.dart             # palette sombre + typo Archivo/Inter
│   │   ├── constants.dart         # catalogue Instagram/TikTok/X/Snapchat
│   │   ├── models.dart            # session, stats, streak
│   │   └── app_state.dart         # état global (Provider) + persistance
│   ├── services/
│   │   ├── native_bridge.dart     # MethodChannel → natif
│   │   ├── notifications_service.dart
│   │   ├── purchases_service.dart # RevenueCat
│   │   ├── insights_service.dart  # IA de suggestion (v1 heuristique)
│   │   └── analytics_service.dart # prêt pour Mixpanel
│   └── ui/
│       ├── app_shell.dart         # routing onboarding→privacy→paywall→home
│       ├── widgets/               # FocusBackground, TimerRing
│       └── screens/               # 8 écrans
├── android/app/src/main/kotlin/com/focusguard/app/
│   ├── MainActivity.kt            # MethodChannel + friction 10 s
│   ├── FocusAccessibilityService.kt  # détection ouverture d'app
│   ├── BlockActivity.kt           # écran de blocage plein écran
│   ├── BlockStateStore.kt         # état partagé Dart↔natif
│   ├── SessionAlarmReceiver.kt    # fin de session + notification
│   └── widget/FocusWidgetProvider.kt # widget home
└── ios/README.md                  # guide FamilyControls (Phase 2)
```

---

## Monétisation

- **Freemium** : blocage basique illimité gratuit ; Pro (2–5 €/mois cible
  3,99 €) → stats détaillées, mode groupe, planification, IA avancée.
- **Essai 30 jours** : à configurer dans
  - Play Console → Produits → Abonnements → essai introductif 30 j
  - App Store Connect → Abonnements → Offer Type: Introductory Offer
  - Le paywall affiche déjà « 30 jours offerts » + mention carte/débit.
- **Rappel de fin d'essai** : `NotificationsService.notifyTrialEnding()`
  (à planifier J-3 après première ouverture — notification locale, pas FCM
  nécessaire pour ça).
- Les clés RevenueCat s'injectent au build :
  `flutter build apk --dart-define=REVENUECAT_GOOGLE_KEY=xxxx`

---

## Roadmap

- **Phase 1** (maintenant) : APK Android bêta-testeurs, itération design.
- **Phase 2** : Mac + compte Apple → build iOS (guide `ios/README.md`).
- **Phase 3** : Firebase (auth Google/Apple réelle, Firestore, Cloud Functions
  pour les défis de groupe + classement) et FCM.
- **Phase 4** : récompenses réelles (partenariats dons/cagnottes), IA
  de suggestion servie côté serveur.
