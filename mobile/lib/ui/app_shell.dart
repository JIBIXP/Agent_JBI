import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/purchases_service.dart';
import 'screens/onboarding_screen.dart';
import 'screens/privacy_screen.dart';
import 'screens/paywall_screen.dart';
import 'screens/home_screen.dart';

/// Coquille de l'app : gère le flux de navigation initial.
/// L'étape d'onboarding est persistée dans SharedPreferences.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  bool _loading = true;
  bool _onboardingDone = false;
  bool _privacyAck = false;
  bool _pro = false;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _onboardingDone = prefs.getBool('onboardingDone') ?? false;
      _privacyAck = prefs.getBool('privacyAck') ?? false;
      _pro = PurchasesService.instance.isPro;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_onboardingDone) {
      return OnboardingScreen(onDone: () => setState(() => _onboardingDone = true));
    }
    if (!_privacyAck) {
      return PrivacyScreen(onAck: () => setState(() => _privacyAck = true));
    }
    if (!_pro) {
      return PaywallScreen(
        onSubscribed: () => setState(() => _pro = true),
        onSkip: () => setState(() => _pro = true),
      );
    }
    return const HomeScreen();
  }
}
