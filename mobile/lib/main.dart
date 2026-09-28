import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/app_state.dart';
import 'core/theme.dart';
import 'services/purchases_service.dart';
import 'services/social_service.dart';
import 'ui/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // RevenueCat (silencieux si aucune clé n'est fournie au build)
  await PurchasesService.instance.init();
  // Défi social (silencieux tant que Firebase n'est pas configuré)
  await SocialService.instance.init();

  runApp(const FocusGuardApp());
}

class FocusGuardApp extends StatelessWidget {
  const FocusGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppState()..load(),
      child: MaterialApp(
        title: 'FocusGuard',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark(),
        home: const AppShell(),
      ),
    );
  }
}
