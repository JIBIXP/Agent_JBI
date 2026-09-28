import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Notifications locales (fin de session, fin d'essai).
class NotificationsService {
  static final NotificationsService instance = NotificationsService._();
  NotificationsService._();

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;

  Future<void> ensureInit() async {
    if (_ready) return;
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings();
    await _plugin.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );
    _ready = true;
  }

  Future<void> notifySessionEnd({required bool earlyStop, required int minutes}) async {
    await ensureInit();
    const androidDetails = AndroidNotificationDetails(
      'session_end',
      'Fin de session',
      channelDescription: 'Notifications quand une session de blocage se termine',
      importance: Importance.high,
      priority: Priority.high,
    );
    const details = NotificationDetails(android: androidDetails, iOS: DarwinNotificationDetails());

    final title = earlyStop ? 'Session interrompue' : 'Bravo ! 🎉';
    final body = earlyStop
        ? 'Tu as tenu $minutes min avant d\'arrêter. Prochaine fois plus loin ?'
        : 'Tu as résisté $minutes min sans réseaux sociaux. Ton streak te remercie.';
    await _plugin.show(1, title, body, details);
  }

  Future<void> notifyTrialEnding({required int daysLeft}) async {
    await ensureInit();
    const androidDetails = AndroidNotificationDetails(
      'trial',
      'Fin d\'essai',
      channelDescription: 'Rappel avant la fin de l\'essai gratuit',
      importance: Importance.high,
      priority: Priority.high,
    );
    const details = NotificationDetails(android: androidDetails, iOS: DarwinNotificationDetails());
    await _plugin.show(
      2,
      'Essai bientôt terminé',
      'Il te reste $daysLeft jour(s) d\'essai gratuit. Tu peux annuler à tout moment.',
      details,
    );
  }
}
