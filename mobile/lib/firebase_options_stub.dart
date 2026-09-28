// Options Firebase par défaut : le projet n'est pas encore configuré.
//
// Après `flutterfire configure`, ce fichier est automatiquement remplacé par
// le vrai fichier généré (qui exporte DefaultFirebaseOptions.currentPlatform),
// et --dart-define=FIREBASE_AVAILABLE=true active le mode social.
//
// Tant que FIREBASE_AVAILABLE n'est pas défini, SocialService reste
// silencieux : aucune requête réseau, l'app tourne en mode 100 % local.

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform => throw UnsupportedError(
        'Firebase non configuré : lance `flutterfire configure` '
        '(voir FIREBASE-SETUP.md) puis rebuild avec '
        '--dart-define=FIREBASE_AVAILABLE=true.',
      );
}
