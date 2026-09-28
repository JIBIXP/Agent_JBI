import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/theme.dart';
import '../widgets/focus_background.dart';

/// Écran d'abonnement — essai gratuit 30 jours mis en avant.
class PaywallScreen extends StatelessWidget {
  final VoidCallback onSubscribed;
  final VoidCallback onSkip;

  const PaywallScreen({
    super.key,
    required this.onSubscribed,
    required this.onSkip,
  });

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Scaffold(
      body: FocusBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const Spacer(flex: 1),
                Text(
                  '30 jours offerts.',
                  style: Theme.of(context).textTheme.displayMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Puis 3,99 €/mois. Annule quand tu veux.',
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const Spacer(flex: 1),
                const _Perk(icon: Icons.all_inclusive, text: 'Blocage illimité + planification'),
                const _Perk(icon: Icons.leaderboard, text: 'Défis en groupe avec tes amis'),
                const _Perk(icon: Icons.psychology, text: 'Suggestions IA personnalisées'),
                const _Perk(icon: Icons.bar_chart, text: 'Statistiques détaillées'),
                const Spacer(flex: 1),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () async {
                      final ok = await state.buyPro();
                      if (ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Bienvenue dans FocusGuard Pro 🎉')),
                        );
                        onSubscribed();
                      }
                    },
                    child: const Text('Démarrer l\'essai gratuit'),
                  ),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () async {
                    await state.restorePurchases();
                  },
                  child: const Text('Restaurer mes achats'),
                ),
                TextButton(
                  onPressed: onSkip,
                  child: Text(
                    'Continuer en version gratuite',
                    style: TextStyle(color: AppColors.textFaint),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Essai de 30 jours. Carte requise à l\'inscription, '
                  'débit automatique après l\'essai sauf annulation. '
                  'Rappel envoyé 3 jours avant.',
                  style: Theme.of(context).textTheme.labelSmall,
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Perk extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Perk({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, color: AppColors.halo, size: 22),
          const SizedBox(width: 14),
          Expanded(child: Text(text, style: Theme.of(context).textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
