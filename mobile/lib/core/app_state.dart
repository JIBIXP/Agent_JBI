import 'dart:convert';
import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';
import '../services/native_bridge.dart';
import '../services/notifications_service.dart';
import '../services/purchases_service.dart';
import '../services/social_service.dart';

/// État global de FocusGuard.
class AppState extends ChangeNotifier {
  // ---------- Sélection d'apps ----------
  final List<BlockedApp> selectedApps = [];

  // ---------- Session ----------
  BlockSession? session;
  Timer? _ticker;

  // ---------- Stats ----------
  final List<SessionRecord> history = [];
  StreakState streak = const StreakState(current: 0, best: 0);

  // ---------- Objectifs / conf ----------
  int dailyGoalMinutes = 60;

  /// Code du groupe de défi social rejoint ('' = aucun).
  String joinedGroup = '';

  void setJoinedGroup(String code) {
    joinedGroup = code;
    _persist();
    notifyListeners();
  }

  /// Durée de blocage choisie sur l'accueil (mémoire vive).
  int pendingDurationMinutes = 60;

  void setPendingDuration(int minutes) {
    pendingDurationMinutes = minutes;
    notifyListeners();
  }

  // ---------- Abonnement ----------
  bool get isPro => PurchasesService.instance.isPro;

  // ---------- Dernière session terminée (écran de fin) ----------
  SessionRecord? _lastFinished;
  SessionRecord? get lastFinished => _lastFinished;

  // ---------- Persistance ----------
  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final sel = prefs.getStringList('selectedApps') ?? [];
    selectedApps
      ..clear()
      ..addAll(sel.map((j) => BlockedApp.fromJson(jsonDecode(j))));
    dailyGoalMinutes = prefs.getInt('dailyGoalMinutes') ?? 60;

    final hist = prefs.getStringList('history') ?? [];
    history
      ..clear()
      ..addAll(hist.map((j) => SessionRecord.fromJson(jsonDecode(j))));

    final streakJson = prefs.getString('streak');
    if (streakJson != null) {
      streak = StreakState.fromJson(jsonDecode(streakJson));
    }

    final sess = prefs.getString('session');
    if (sess != null && sess.isNotEmpty) {
      _restoreSession(jsonDecode(sess));
    }
    joinedGroup = prefs.getString(SocialService.joinedGroupPrefKey) ?? '';
    _startTicker();
    notifyListeners();
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(
        'selectedApps', selectedApps.map((a) => jsonEncode(a.toJson())).toList());
    await prefs.setInt('dailyGoalMinutes', dailyGoalMinutes);
    await prefs.setStringList(
        'history', history.take(200).map((r) => jsonEncode(r.toJson())).toList());
    await prefs.setString('streak', jsonEncode(streak.toJson()));
    await prefs.setString(SocialService.joinedGroupPrefKey, joinedGroup);
    await prefs.setString(
        'session', session == null ? '' : jsonEncode(_sessionToJson()));
  }

  Map<String, dynamic> _sessionToJson() => {
        'kind': session!.kind.name,
        'apps': session!.apps.map((a) => a.toJson()).toList(),
        'strict': session!.strict.name,
        'startedAt': session!.startedAt.toIso8601String(),
        'endsAt': session!.endsAt.toIso8601String(),
      };

  void _restoreSession(Map<String, dynamic> json) {
    final endsAt = DateTime.parse(json['endsAt']);
    if (endsAt.isBefore(DateTime.now())) {
      return; // session expirée pendant l'arrêt de l'app : on l'ignore
    }
    session = BlockSession(
      kind: SessionKind.values
          .firstWhere((k) => k.name == json['kind'], orElse: () => SessionKind.classic),
      apps: (json['apps'] as List).map((a) => BlockedApp.fromJson(a)).toList(),
      strict: StrictMode.values
          .firstWhere((s) => s.name == json['strict'], orElse: () => StrictMode.normal),
      startedAt: DateTime.parse(json['startedAt']),
      endsAt: endsAt,
    );
  }

  // ---------- Sélection ----------
  void toggleApp(BlockedApp app) {
    if (selectedApps.contains(app)) {
      selectedApps.remove(app);
    } else {
      selectedApps.add(app);
    }
    _persist();
    notifyListeners();
  }

  void setGoal(int minutes) {
    dailyGoalMinutes = minutes;
    _persist();
    notifyListeners();
  }

  // ---------- Session ----------
  void startSession({
    required SessionKind kind,
    required int durationMinutes,
    required StrictMode strict,
  }) {
    final now = DateTime.now();
    final session0 = BlockSession(
      kind: kind,
      apps: List.from(selectedApps),
      strict: strict,
      startedAt: now,
      endsAt: now.add(Duration(minutes: durationMinutes)),
    );
    session = session0;
    NativeBridge.startBlocking(
      packages: session!.apps.map((a) => a.packageName).toList(),
      endsAtMs: session!.endsAt.millisecondsSinceEpoch,
      strict: strict == StrictMode.locked,
    );
    _startTicker();
    _persist();
    notifyListeners();
  }

  void _startTicker() {
    _ticker?.cancel();
    if (session == null) return;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
  }

  void _tick() {
    if (session == null) return;
    if (session!.remainingSeconds <= 0) {
      _finishSession(earlyStop: false);
      return;
    }
    notifyListeners();
  }

  void pausePomodoro() {
    if (session == null || session!.pausedAt != null) return;
    session!.pausedAt = DateTime.now();
    session!.remainingBeforePause = session!.endsAt.difference(session!.pausedAt!).inSeconds;
    notifyListeners();
  }

  void resumePomodoro() {
    if (session == null || session!.pausedAt == null) return;
    final pausedFor = DateTime.now().difference(session!.pausedAt!).inSeconds;
    session!.endsAt = session!.endsAt.add(Duration(seconds: pausedFor));
    session!.pausedAt = null;
    notifyListeners();
  }

  /// Arrêt anticipé — refusé en mode verrouillé, friction 10 s en mode urgence.
  Future<bool> stopEarly() async {
    if (session == null) return false;
    if (session!.strict == StrictMode.locked) return false;
    if (session!.strict == StrictMode.friction10s) {
      final ok = await NativeBridge.showFrictionDialog();
      if (!ok) return false;
    }
    _finishSession(earlyStop: true);
    return true;
  }

  void _finishSession({required bool earlyStop}) {
    final s = session;
    if (s == null) return;
    _ticker?.cancel();
    session = null;

    final minutes = earlyStop
        ? max(1, DateTime.now().difference(s.startedAt).inMinutes)
        : max(1, DateTime.now().difference(s.startedAt).inMinutes);
    final record = SessionRecord(
      endedAt: DateTime.now(),
      minutes: minutes,
      appPackages: s.apps.map((a) => a.packageName).toList(),
      kind: s.kind,
    );
    history.insert(0, record);
    _updateStreak();

    NativeBridge.stopBlocking();
    NotificationsService.instance.notifySessionEnd(earlyStop: earlyStop, minutes: minutes);
    // Défi social : publie le total hebdo dans le classement du groupe.
    if (joinedGroup.isNotEmpty) {
      SocialService.instance.publishMinutes(joinedGroup, weeklyFocusMinutes());
    }
    _lastFinished = record;
    _persist();
    notifyListeners();
  }

  // ---------- Stats ----------
  int weeklyFocusMinutes() {
    final weekAgo = DateTime.now().subtract(const Duration(days: 7));
    return history
        .where((r) => r.endedAt.isAfter(weekAgo))
        .fold(0, (sum, r) => sum + r.minutes);
  }

  Map<String, int> weeklyMinutesPerApp() {
    final weekAgo = DateTime.now().subtract(const Duration(days: 7));
    final map = <String, int>{};
    for (final r in history.where((r) => r.endedAt.isAfter(weekAgo))) {
      final per = max(1, r.appPackages.length);
      for (final p in r.appPackages) {
        map[p] = (map[p] ?? 0) + (r.minutes ~/ per);
      }
    }
    return map;
  }

  List<double> last7DaysFocus() {
    final result = List<double>.filled(7, 0);
    final today = DateTime.now();
    for (final r in history) {
      final diff = today.difference(r.endedAt).inDays;
      if (diff >= 0 && diff < 7) {
        result[6 - diff] += r.minutes.toDouble();
      }
    }
    return result;
  }

  void _updateStreak() {
    final today = DateTime.now();
    final todayMinutes = history
        .where((r) =>
            r.endedAt.year == today.year &&
            r.endedAt.month == today.month &&
            r.endedAt.day == today.day)
        .fold(0, (sum, r) => sum + r.minutes);
    if (todayMinutes < dailyGoalMinutes) return;

    final last = streak.lastGoalDay;
    final alreadyToday = last != null &&
        last.year == today.year &&
        last.month == today.month &&
        last.day == today.day;
    if (alreadyToday) return;

    final yesterday = today.subtract(const Duration(days: 1));
    final continues = last != null &&
        last.year == yesterday.year &&
        last.month == yesterday.month &&
        last.day == yesterday.day;
    final newCurrent = continues ? streak.current + 1 : 1;
    streak = StreakState(
      current: newCurrent,
      best: max(streak.best, newCurrent),
      lastGoalDay: today,
    );
  }

  // ---------- Abonnement ----------
  /// Renvoie true si l'abonnement Pro est actif après l'achat.
  Future<bool> buyPro() async {
    final ok = await PurchasesService.instance.purchase();
    notifyListeners();
    return ok;
  }

  Future<void> restorePurchases() async {
    await PurchasesService.instance.restore();
    notifyListeners();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }
}
