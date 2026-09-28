# FocusGuard — Implémentation iOS (Phase 2)

Le projet Flutter est prêt ; la partie iOS nécessite un Mac + compte développeur
Apple (99 $/an) et se compose de trois frameworks officiels (iOS 16+) :

## 1. Autorisation — FamilyControls
```swift
import FamilyControls
// Dans AppDelegate didFinishLaunching :
let center = AuthorizationCenter.shared
Task {
    do {
        try await center.requestAuthorization(for: .individual)
    } catch {
        // L'utilisateur a refusé : désactiver le blocage côté Flutter.
    }
}
```
- Capabilité X : `Family Controls (Distribution)` — à activer dans Signing & Capabilities.

## 2. Blocage visuel — ManagedSettings + Shield
```swift
import ManagedSettings
let store = ManagedSettingsStore(named: .init("focusguard"))
// Début de session :
store.shield.applicationCategories = .categories([
    // catégories choisies via FamilyActivityPicker
])
// Fin de session :
store.shield.clearAll()
```

## 3. Programmation — DeviceActivity
```swift
import DeviceActivity
let schedule = DeviceActivitySchedule(
    intervalStart: DateComponents(hour: now.h, minute: now.m),
    intervalEnd: DateComponents(hour: end.h, minute: end.m),
    repeats: false
)
let monitor = DeviceActivityCenter()
try monitor.startMonitoring(.init("session-1"), during: schedule)
// Extension DeviceActivityMonitor : applique/retire le shield aux rappels.
```

## Sélecteur d'apps
`FamilyActivityPicker` (SwiftUI) remplace le catalogue Android : l'utilisateur
choisit librement ses apps, jetons stockés via `FamilyActivitySelection`
(encodés en Data côté Dart via MethodChannel).

## Résumé du plan d'action iOS
1. Ouvrir `mobile/ios` sur un Mac : `flutter build ios --no-codesign`
2. Ajouter les 3 capabilités + App Group (`group.com.focusguard.app`)
3. Créer la cible `DeviceActivityMonitor` extension
4. Implémenter le bridge MethodChannel `focusguard/native` côté Swift
   (les mêmes méthodes que Android : startBlocking/stopBlocking/…)
5. Tester sur un vrai appareil (les frameworks ne marchent pas au simulateur)
