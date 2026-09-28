import 'dart:developer' as developer;

/// Analytics minimaliste. V1 : journalisation locale uniquement.
/// Brancher Mixpanel/Amplitude ici plus tard (clé via --dart-define).
class AnalyticsService {
  static final AnalyticsService instance = AnalyticsService._();
  AnalyticsService._();

  static const _mixpanelKey =
      String.fromEnvironment('MIXPANEL_KEY', defaultValue: '');

  bool get configured => _mixpanelKey.isNotEmpty;

  void track(String event, [Map<String, dynamic>? props]) {
    if (!configured) {
      developer.log('Analytics: $event ${props ?? ''}', name: 'focusguard');
      return;
    }
    // TODO: envoyer vers Mixpanel/Amplitude avec le SDK choisi.
  }
}
