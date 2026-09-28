import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import '../widgets/focus_background.dart';
import 'session_screen.dart';

/// Mode Révision : Pomodoro 25/5, nombre de cycles au choix.
class RevisionSetupScreen extends StatefulWidget {
  const RevisionSetupScreen({super.key});

  @override
  State<RevisionSetupScreen> createState() => _RevisionSetupScreenState();
}

class _RevisionSetupScreenState extends State<RevisionSetupScreen> {
  int _cycles = 2; // 1 cycle = 25 min focus + 5 min pause
  StrictMode _strict = StrictMode.normal;

  @override
  Widget build(BuildContext context) {
    final state = context.read<AppState>();
    return FocusBackground(
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Mode Révision', style: Theme.of(context).textTheme.displayMedium),
              const SizedBox(height: 8),
              Text(
                '25 min de focus, 5 min de pause. Répété.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 32),
              Text('CYCLES', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                children: [1, 2, 3, 4, 6].map((c) {
                  final selected = _cycles == c;
                  return ChoiceChip(
                    label: Text('$c × 30 min'),
                    selected: selected,
                    onSelected: (_) => setState(() => _cycles = c),
                    checkmarkColor: Colors.white,
                    backgroundColor: AppColors.deepPurple,
                    selectedColor: AppColors.halo,
                    labelStyle: TextStyle(
                      color: selected ? Colors.white : AppColors.textSecondary,
                      fontWeight: FontWeight.w700,
                    ),
                    shape: const StadiumBorder(side: BorderSide(color: Color(0x22FFFFFF))),
                  );
                }).toList(),
              ),
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
                    state.startSession(
                      kind: SessionKind.revision,
                      durationMinutes: _cycles * 30, // 25 focus + 5 pause par cycle
                      strict: _strict,
                    );
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(builder: (_) => const SessionScreen()),
                      (r) => false,
                    );
                  },
                  child: Text('Lancer ($_cycles × 30 min)'),
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
