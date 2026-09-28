import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../widgets/focus_background.dart';
import '../../core/theme.dart';
import '../../services/social_service.dart';

/// Onboarding cinématique : 3 slides, dots, connexion en bas.
class OnboardingScreen extends StatefulWidget {
  final VoidCallback onDone;
  const OnboardingScreen({super.key, required this.onDone});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _controller = PageController();

  void _onPageChanged(int index) => setState(() => _pageIndex = index);

  int _pageIndex = 0;

  static const _slides = [
    (
      'Reprends\nle contrôle.',
      'Instagram, TikTok, X, Snapchat — bloqués d\'un tap quand tu dois te concentrer.'
    ),
    (
      'Construis\nta série.',
      'Chaque jour où tu atteins ton objectif, ta série grandit. Ne la casse pas.',
    ),
    (
      'Ton temps\na de la valeur.',
      'Le temps de focus économisé devient des points, des dons, des récompenses.',
    ),
  ];

  void _next() {
    if (_pageIndex < _slides.length - 1) {
      _controller.nextPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
      );
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('onboardingDone', true);
    widget.onDone();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FocusBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const Spacer(flex: 2),
                Expanded(
                  flex: 5,
                  child: PageView.builder(
                    controller: _controller,
                    onPageChanged: _onPageChanged,
                    itemCount: _slides.length,
                    itemBuilder: (context, i) => Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          _slides[i].$1,
                          style: Theme.of(context).textTheme.displayLarge,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),
                        Text(
                          _slides[i].$2,
                          style: Theme.of(context).textTheme.bodyMedium,
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
                const Spacer(flex: 1),
                // Dots de pagination
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(_slides.length, (i) {
                    final active = i == _pageIndex;
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: active ? 24 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: active ? AppColors.halo : AppColors.textFaint,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 32),
                // Boutons de connexion
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () async {
                      // Tente la connexion Google (défi social). Si Firebase
                      // n'est pas configuré, on poursuit simplement l'inscription.
                      await SocialService.instance.signInWithGoogle();
                      _next();
                    },
                    icon: const Icon(Icons.g_mobiledata, size: 28),
                    label: const Text('Continuer avec Google'),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _next,
                    icon: const Icon(Icons.apple),
                    label: const Text('Continuer avec Apple'),
                  ),
                ),
                TextButton(
                  onPressed: _next,
                  child: const Text('Passer pour l\'instant'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
