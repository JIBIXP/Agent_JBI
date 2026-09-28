// Modèles de données principaux de FocusGuard.

/// Une app sélectionnée pour le blocage.
class BlockedApp {
  final String packageName;
  final String label;
  final String emoji;

  const BlockedApp({
    required this.packageName,
    required this.label,
    required this.emoji,
  });

  Map<String, dynamic> toJson() => {
        'packageName': packageName,
        'label': label,
        'emoji': emoji,
      };

  factory BlockedApp.fromJson(Map<String, dynamic> json) => BlockedApp(
        packageName: json['packageName'] as String,
        label: json['label'] as String,
        emoji: json['emoji'] as String? ?? '📱',
      );

  @override
  bool operator ==(Object other) =>
      other is BlockedApp && other.packageName == packageName;

  @override
  int get hashCode => packageName.hashCode;
}

/// Type de session.
enum SessionKind { classic, revision }

/// Mode de sortie de session.
enum StrictMode { normal, friction10s, locked }

/// État d'une session en cours.
class BlockSession {
  final SessionKind kind;
  final List<BlockedApp> apps;
  final StrictMode strict;
  final DateTime startedAt;
  DateTime endsAt;
  DateTime? pausedAt;

  // remainingBeforePause est figé pendant une pause (Pomodoro).
  int remainingBeforePause = 0;

  BlockSession({
    required this.kind,
    required this.apps,
    required this.strict,
    required this.startedAt,
    required this.endsAt,
    this.pausedAt,
  });

  /// Durée totale planifiée, en minutes.
  int get durationMinutes => endsAt.difference(startedAt).inMinutes;

  /// Pomodoro : 25 min focus par cycle (pour affichage futur).
  int get focusSeconds => kind == SessionKind.revision ? 25 * 60 : durationMinutes * 60;

  int get totalSeconds {
    final raw = endsAt.difference(startedAt).inSeconds;
    return raw < 1 ? 1 : raw;
  }

  int get remainingSeconds {
    if (pausedAt != null) return remainingBeforePause;
    final left = endsAt.difference(DateTime.now()).inSeconds;
    return left < 0 ? 0 : left;
  }

  double get progress {
    final total = totalSeconds;
    if (total <= 0) return 0.0;
    return (1.0 - remainingSeconds / total).clamp(0.0, 1.0);
  }
}

/// Statistique quotidienne (temps économisé = temps de blocage réussi).
class DailyStat {
  final DateTime day;
  final int focusMinutes;
  final Map<String, int> minutesPerApp;

  const DailyStat({
    required this.day,
    required this.focusMinutes,
    required this.minutesPerApp,
  });

  Map<String, dynamic> toJson() => {
        'day': day.toIso8601String(),
        'focusMinutes': focusMinutes,
        'minutesPerApp': minutesPerApp,
      };

  factory DailyStat.fromJson(Map<String, dynamic> json) => DailyStat(
        day: DateTime.parse(json['day'] as String),
        focusMinutes: json['focusMinutes'] as int,
        minutesPerApp: (json['minutesPerApp'] as Map<String, dynamic>)
            .map((k, v) => MapEntry(k, v as int)),
      );
}

/// Série de jours consécutifs avec objectif atteint.
class StreakState {
  final int current;
  final int best;
  final DateTime? lastGoalDay;

  const StreakState({
    required this.current,
    required this.best,
    this.lastGoalDay,
  });

  StreakState copyWith({int? current, int? best, DateTime? lastGoalDay}) =>
      StreakState(
        current: current ?? this.current,
        best: best ?? this.best,
        lastGoalDay: lastGoalDay ?? this.lastGoalDay,
      );

  Map<String, dynamic> toJson() => {
        'current': current,
        'best': best,
        'lastGoalDay': lastGoalDay?.toIso8601String(),
      };

  factory StreakState.fromJson(Map<String, dynamic> json) => StreakState(
        current: json['current'] as int? ?? 0,
        best: json['best'] as int? ?? 0,
        lastGoalDay: json['lastGoalDay'] != null
            ? DateTime.parse(json['lastGoalDay'] as String)
            : null,
      );
}

/// Point de l'historique des sessions terminées (pour stats hebdo).
class SessionRecord {
  final DateTime endedAt;
  final int minutes;
  final List<String> appPackages;
  final SessionKind kind;

  const SessionRecord({
    required this.endedAt,
    required this.minutes,
    required this.appPackages,
    required this.kind,
  });

  Map<String, dynamic> toJson() => {
        'endedAt': endedAt.toIso8601String(),
        'minutes': minutes,
        'apps': appPackages,
        'kind': kind.name,
      };

  factory SessionRecord.fromJson(Map<String, dynamic> json) => SessionRecord(
        endedAt: DateTime.parse(json['endedAt'] as String),
        minutes: json['minutes'] as int,
        appPackages: (json['apps'] as List).cast<String>(),
        kind: SessionKind.values.firstWhere(
          (k) => k.name == json['kind'],
          orElse: () => SessionKind.classic,
        ),
      );
}
