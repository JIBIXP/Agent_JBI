import 'package:flutter/services.dart';

/// Pont vers le code natif Android (Kotlin) et iOS (Swift).
class NativeBridge {
  static const _channel = MethodChannel('focusguard/native');

  /// Démarre le blocage natif des apps jusqu'à endsAtMs.
  static Future<void> startBlocking({
    required List<String> packages,
    required int endsAtMs,
    required bool strict,
  }) async {
    try {
      await _channel.invokeMethod('startBlocking', {
        'packages': packages,
        'endsAtMs': endsAtMs,
        'strict': strict,
      });
    } on PlatformException {
      // En l'absence d'implémentation native (build desktop/web de test),
      // le blocage est simulé côté Dart uniquement.
    }
  }

  static Future<void> stopBlocking() async {
    try {
      await _channel.invokeMethod('stopBlocking');
    } on PlatformException {
      // idem
    }
  }

  /// Ouvre le sélecteur système des apps (iOS FamilyActivityPicker).
  static Future<List<String>> openAppPicker() async {
    try {
      final result = await _channel.invokeMethod<List<dynamic>>('openAppPicker');
      return result?.cast<String>() ?? [];
    } on PlatformException {
      return [];
    }
  }

  /// Vérifie les permissions nécessaires selon la plateforme.
  static Future<bool> hasBlockingPermission() async {
    try {
      return await _channel.invokeMethod<bool>('hasBlockingPermission') ?? false;
    } on PlatformException {
      return false;
    }
  }

  static Future<void> requestBlockingPermission() async {
    try {
      await _channel.invokeMethod('requestBlockingPermission');
    } on PlatformException {
      // ignore
    }
  }

  /// Dialogue de friction (10 secondes obligatoires) en mode urgence.
  static Future<bool> showFrictionDialog() async {
    try {
      return await _channel.invokeMethod<bool>('showFrictionDialog') ?? false;
    } on PlatformException {
      return false;
    }
  }

  /// Mets à jour le widget d'écran d'accueil.
  static Future<void> updateWidget({
    required bool sessionActive,
    required int remainingSeconds,
  }) async {
    try {
      await _channel.invokeMethod('updateWidget', {
        'sessionActive': sessionActive,
        'remainingSeconds': remainingSeconds,
      });
    } on PlatformException {
      // ignore
    }
  }
}
