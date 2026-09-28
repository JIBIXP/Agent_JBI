import 'dart:math';

import '../core/models.dart';

/// Moteur de suggestions intelligentes.
/// V1 : heuristiques locales sur l'historique des sessions.
/// (Extensible : brancher un LLM ou Mixpanel plus tard.)
class InsightsService {
  /// Détecte les créneaux où l'utilisateur cède le plus souvent
  /// (arrêts anticipés) et propose des horaires de blocage.
  static List<BlockingSuggestion> suggestions(List<SessionRecord> history) {
    if (history.length < 3) return [];

    // Regroupe les arrêts anticipés par heure de la journée.
    final weakHours = <int, int>{};
    for (final r in history) {
      final h = r.endedAt.hour;
      weakHours[h] = (weakHours[h] ?? 0) + 1;
    }

    // Trie par fréquence décroissante, garde les 2 pires créneaux.
    final sorted = weakHours.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final worst = sorted.take(2).where((e) => e.value >= 2).toList();

    return worst.map((e) {
      final start = e.key;
      final end = (start + 1) % 24;
      String hh(int h) => h.toString().padLeft(2, '0');
      return BlockingSuggestion(
        title: 'Blocage suggéré : ${hh(start)}:00 → ${hh(end)}:00',
        reason: 'Tu abandonnes souvent tes sessions vers ${hh(start)}h. '
            'Bloquer à cette heure pourrait doubler ton temps de focus.',
      );
    }).toList();
  }

  /// Score de risque d'usage compulsif pour aujourd'hui (0-100).
  static int riskScore(List<SessionRecord> history) {
    if (history.isEmpty) return 0;
    final today = DateTime.now();
    final todaySessions = history
        .where((r) =>
            r.endedAt.year == today.year &&
            r.endedAt.month == today.month &&
            r.endedAt.day == today.day)
        .toList();
    final earlyStops = todaySessions.length;
    final avgMinutes = todaySessions.isEmpty
        ? 0
        : todaySessions.fold(0, (s, r) => s + r.minutes) ~/ todaySessions.length;
    return min(100, earlyStops * 20 + (60 - min(60, avgMinutes)));
  }
}

/// Suggestion affichée sur l'écran principal.
class BlockingSuggestion {
  final String title;
  final String reason;

  const BlockingSuggestion({required this.title, required this.reason});
}
