import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/models.dart';
import '../widgets/focus_background.dart';
import '../widgets/timer_ring.dart';

/// Écran de session active : anneau de compte à rebours, sortie contrôlée.
class SessionScreen extends StatefulWidget {
  const SessionScreen({super.key});

  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> {
  bool _frictionRunning = false;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final session = state.session;

    if (session == null) {
      // Session terminée : l'AppState a déjà enregistré le record.
      // HomeScreen reprend la main automatiquement (session == null).
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final total = session.kind == SessionKind.revision ? session.focusSeconds : session.totalSeconds;
    final remaining = session.remainingSeconds;
    final progress = 1.0 - remaining / max(1, total);

    return FocusBackground(
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  session.kind == SessionKind.revision ? 'MODE RÉVISION' : 'SESSION DE FOCUS',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ),
              const Spacer(),
              TimerRing(
                progress: progress,
                centerText: _fmt(remaining),
                subtitle: _appsLabel(session),
              ),
              const Spacer(),
              if (session.kind == SessionKind.revision)
                OutlinedButton(
                  onPressed: () {
                    if (session.pausedAt == null) {
                      state.pausePomodoro();
                    } else {
                      state.resumePomodoro();
                    }
                  },
                  child: Text(session.pausedAt == null ? 'Pause' : 'Reprendre'),
                ),
              const SizedBox(height: 12),
              if (session.strict == StrictMode.locked)
                Text(
                  '🔒 Mode strict : impossible d\'arrêter avant la fin.',
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                )
              else
                OutlinedButton(
                  onPressed: _frictionRunning ? null : () => _tryStop(context, state),
                  child: Text(
                    session.strict == StrictMode.friction10s
                        ? 'Arrêt d\'urgence (10 s de friction)'
                        : 'Arrêter la session',
                  ),
                ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  String _appsLabel(BlockSession session) {
    final n = session.apps.length;
    return '$n app${n > 1 ? 's' : ''} bloquée${n > 1 ? 's' : ''}';
  }

  String _fmt(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  Future<void> _tryStop(BuildContext context, AppState state) async {
    setState(() => _frictionRunning = true);
    await state.stopEarly();
    if (!mounted) return;
    setState(() => _frictionRunning = false);
  }
}
