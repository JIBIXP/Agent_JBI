import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../services/insights_service.dart';
import '../widgets/focus_background.dart';
import '../widgets/timer_ring.dart';
import 'app_select_screen.dart';
import 'challenges_screen.dart';
import 'revision_setup_screen.dart';
import 'session_screen.dart';
import 'stats_screen.dart';

/// Écran principal : minuteur, apps, lancement, stats rapides.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    if (state.session != null) {
      return const SessionScreen();
    }

    return FocusBackground(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('FocusGuard', style: Theme.of(context).textTheme.titleLarge),
                      Text(_greeting(), style: Theme.of(context).textTheme.bodyMedium),
                    ],
                  ),
                  // Badge streak
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppColors.deepPurple,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppColors.haloSoft),
                    ),
                    child: Row(
                      children: [
                        const Text('🔥', style: TextStyle(fontSize: 16)),
                        const SizedBox(width: 6),
                        Text(
                          '${state.streak.current}',
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Minuteur central (état repos)
              Center(
                child: TimerRing(
                  progress: 0,
                  centerText: _fmt(state.dailyGoalMinutes),
                  subtitle: 'OBJECTIF DU JOUR',
                ),
              ),
              const SizedBox(height: 32),

              // Suggestions IA
              ...InsightsService.suggestions(state.history).map(
                (s) => Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    leading: const Icon(Icons.psychology, color: AppColors.halo),
                    title: Text(s.title,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                    subtitle: Text(s.reason, style: const TextStyle(fontSize: 12)),
                    dense: true,
                  ),
                ),
              ),

              // Apps sélectionnées
              Text('APPS BLOQUÉES', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ...allApps.map((app) {
                    final selected = state.selectedApps.contains(app);
                    return FilterChip(
                      label: Text('${app.emoji} ${app.label}'),
                      selected: selected,
                      onSelected: (_) => state.toggleApp(app),
                      checkmarkColor: Colors.white,
                      backgroundColor: AppColors.deepPurple,
                      selectedColor: AppColors.halo,
                      labelStyle: TextStyle(
                        color: selected ? Colors.white : AppColors.textSecondary,
                        fontWeight: FontWeight.w600,
                      ),
                      shape: const StadiumBorder(side: BorderSide(color: Color(0x22FFFFFF))),
                    );
                  }),
                ],
              ),
              const SizedBox(height: 24),

              // Choix de durée
              Text('DURÉE', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [15, 30, 60, 120].map((min) {
                  final selected = state.pendingDurationMinutes == min;
                  return ChoiceChip(
                    label: Text(min >= 60 ? '${min ~/ 60}h' : '$min min'),
                    selected: selected,
                    onSelected: (_) => state.setPendingDuration(min),
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

              // Boutons d'action
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: state.selectedApps.isEmpty
                      ? null
                      : () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const AppSelectScreen()),
                          );
                        },
                  child: const Text('Bloquer maintenant'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: state.selectedApps.isEmpty
                      ? null
                      : () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const RevisionSetupScreen()),
                          );
                        },
                  icon: const Icon(Icons.menu_book),
                  label: const Text('Mode Révision (Pomodoro)'),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const StatsScreen()),
                        );
                      },
                      child: const Text('Statistiques'),
                    ),
                  ),
                  Expanded(
                    child: TextButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const ChallengesScreen()),
                        );
                      },
                      icon: const Icon(Icons.emoji_events, size: 18),
                      label: const Text('Défis'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const QuickStats(),
            ],
          ),
        ),
      ),
    );
  }

  String _greeting() {
    final h = DateTime.now().hour;
    if (h < 12) return 'Bon matin. Prêt à te concentrer ?';
    if (h < 18) return 'Bon après-midi. Un blocage ?';
    return 'Bonsoir. Protégeons ta soirée.';
  }

  String _fmt(int min) {
    if (min >= 60) {
      final h = min ~/ 60;
      final rest = min % 60;
      return rest == 0 ? '$h h' : '$h h $rest';
    }
    return '$min min';
  }
}

/// Petit widget de stats rapides (temps économisé cette semaine).
class QuickStats extends StatelessWidget {
  const QuickStats({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Row(
      children: [
        _StatCard(label: 'Cette semaine', value: '${state.weeklyFocusMinutes()} min'),
        const SizedBox(width: 12),
        _StatCard(label: 'Meilleure série', value: '${state.streak.best} j'),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  const _StatCard({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.deepPurple,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 6),
            Text(value, style: Theme.of(context).textTheme.titleLarge),
          ],
        ),
      ),
    );
  }
}
