import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import '../widgets/focus_background.dart';
import 'session_screen.dart';

/// Écran de lancement de session : récap apps + durée + mode de sortie.
class AppSelectScreen extends StatefulWidget {
  const AppSelectScreen({super.key});

  @override
  State<AppSelectScreen> createState() => _AppSelectScreenState();
}

class _AppSelectScreenState extends State<AppSelectScreen> {
  StrictMode _strict = StrictMode.normal;
  late int _minutes;

  @override
  void initState() {
    super.initState();
    _minutes = context.read<AppState>().pendingDurationMinutes;
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return FocusBackground(
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Prêt à bloquer', style: Theme.of(context).textTheme.displayMedium),
              const SizedBox(height: 24),
              Text('APPS', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: state.selectedApps
                    .map((a) => Chip(
                          label: Text('${a.emoji} ${a.label}'),
                          backgroundColor: AppColors.deepPurple,
                          side: const BorderSide(color: Color(0x22FFFFFF)),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
              Text('DURÉE : $_minutes MIN', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 24),
              Text('MODE DE SORTIE', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 12),
              ...StrictMode.values.map((m) => RadioListTile<StrictMode>(
                    title: Text(_strictLabel(m)),
                    value: m,
                    groupValue: _strict,
                    onChanged: (v) => setState(() => _strict = v!),
                    activeColor: AppColors.halo,
                  )),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () {
                    state.pendingDurationMinutes = _minutes;
                    state.startSession(
                      kind: SessionKind.classic,
                      durationMinutes: _minutes,
                      strict: _strict,
                    );
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(builder: (_) => const SessionScreen()),
                      (r) => false,
                    );
                  },
                  child: Text('Lancer le blocage ($_minutes min)'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _strictLabel(StrictMode m) {
    switch (m) {
      case StrictMode.normal:
        return 'Normal — arrêt libre';
      case StrictMode.friction10s:
        return 'Urgence — friction de 10 secondes';
      case StrictMode.locked:
        return 'Verrouillé — impossible d\'arrêter avant la fin';
    }
  }
}
