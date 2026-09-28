import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../widgets/focus_background.dart';
import '../../core/theme.dart';

/// Page Confidentialité : rassure sur les données (RGPD).
class PrivacyScreen extends StatelessWidget {
  final VoidCallback onAck;
  const PrivacyScreen({super.key, required this.onAck});

  Future<void> _ack() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('privacyAck', true);
    onAck();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FocusBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 24),
                Text(
                  'Confidentialité',
                  style: Theme.of(context).textTheme.displayMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Ce que FocusGuard ne fait PAS',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(height: 32),
                const _PrivacyItem(
                  icon: Icons.visibility_off,
                  title: 'Aucun contenu lu',
                  text: 'FocusGuard ne voit ni tes messages, ni tes photos, '
                      'ni tes mots de passe. Jamais.',
                ),
                const _PrivacyItem(
                  icon: Icons.phone_android,
                  title: 'Détection système uniquement',
                  text: 'L\'app sait seulement QUAND une app s\'ouvre, '
                      'pas ce que tu fais dedans.',
                ),
                const _PrivacyItem(
                  icon: Icons.lock,
                  title: 'Autorisation officielle',
                  text: 'Le blocage utilise les mécanismes prévus par Apple '
                      'et Google, pas de contournement.',
                ),
                const _PrivacyItem(
                  icon: Icons.delete_outline,
                  title: 'Suppression en un tap',
                  text: 'Toutes tes données sont locales. Désinstalle ou '
                      'appuie sur « Effacer mes données » et tout disparaît.',
                ),
                const Spacer(),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _ack,
                    child: const Text('J\'ai compris'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PrivacyItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String text;

  const _PrivacyItem({
    required this.icon,
    required this.title,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.haloSoft,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: AppColors.textPrimary, size: 22),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontSize: 16)),
                const SizedBox(height: 4),
                Text(text, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
