import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/constants.dart';
import '../../core/models.dart';
import '../../core/theme.dart';
import '../widgets/focus_background.dart';

/// Statistiques détaillées.
class StatsScreen extends StatelessWidget {
  const StatsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final data = state.last7DaysFocus();
    final perApp = state.weeklyMinutesPerApp();

    return FocusBackground(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => Navigator.pop(context),
                ),
                Text('Statistiques', style: Theme.of(context).textTheme.displayMedium),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              '${state.weeklyFocusMinutes()} min de focus cette semaine',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 24),
            SizedBox(
              height: 200,
              child: BarChart(
                BarChartData(
                  gridData: const FlGridData(show: false),
                  borderData: FlBorderData(show: false),
                  titlesData: const FlTitlesData(show: false),
                  barGroups: List.generate(7, (i) {
                    return BarChartGroupData(
                      x: i,
                      barRods: [
                        BarChartRodData(
                          toY: data[i],
                          color: AppColors.halo,
                          width: 18,
                          borderRadius: BorderRadius.circular(6),
                        ),
                      ],
                    );
                  }),
                ),
              ),
            ),
            const SizedBox(height: 8),
            const Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                Text('J-6', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('J-5', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('J-4', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('J-3', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('J-2', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('Hier', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
                Text('Auj.', style: TextStyle(color: AppColors.textFaint, fontSize: 11)),
              ],
            ),
            const SizedBox(height: 32),
            Text('APPS LES PLUS BLOQUÉES', style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 12),
            if (perApp.isEmpty)
              Text('Aucune session encore enregistrée.',
                  style: Theme.of(context).textTheme.bodyMedium),
            ...perApp.entries.map((e) {
              BlockedApp app = const BlockedApp(packageName: '?', label: 'Inconnue', emoji: '📱');
              for (final a in allApps) {
                if (a.packageName == e.key) app = a;
              }
              return ListTile(
                leading: Text(app.emoji, style: const TextStyle(fontSize: 24)),
                title: Text(app.label, style: const TextStyle(color: Colors.white)),
                trailing: Text('${e.value} min',
                    style: const TextStyle(color: AppColors.textSecondary)),
              );
            }),
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.deepPurple,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  const Text('🔥', style: TextStyle(fontSize: 32)),
                  const SizedBox(width: 16),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Série actuelle : ${state.streak.current} jour(s)',
                          style: Theme.of(context).textTheme.titleLarge),
                      Text('Record : ${state.streak.best} jours',
                          style: Theme.of(context).textTheme.bodyMedium),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
