import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_state.dart';
import '../../core/theme.dart';
import '../../services/social_service.dart';
import '../widgets/focus_background.dart';

/// Mode défi social : groupe d'amis, classement du temps résisté.
class ChallengesScreen extends StatefulWidget {
  const ChallengesScreen({super.key});

  @override
  State<ChallengesScreen> createState() => _ChallengesScreenState();
}

class _ChallengesScreenState extends State<ChallengesScreen> {
  final _codeCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _codeCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;
    setState(() => _busy = true);
    final code = await SocialService.instance.createGroup(name);
    if (!mounted) return;
    setState(() => _busy = false);
    if (code.isNotEmpty) {
      context.read<AppState>().setJoinedGroup(code);
    } else {
      _snack('Firebase non configuré — voir FIREBASE-SETUP.md');
    }
  }

  Future<void> _join() async {
    final code = _codeCtrl.text.trim();
    if (code.isEmpty) return;
    setState(() => _busy = true);
    final ok = await SocialService.instance.joinGroup(code);
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      context.read<AppState>().setJoinedGroup(code.toUpperCase());
    } else {
      _snack('Code invalide ou Firebase non configuré');
    }
  }

  Future<void> _signIn() async {
    setState(() => _busy = true);
    final ok = await SocialService.instance.signInWithGoogle();
    if (!mounted) return;
    setState(() => _busy = false);
    if (!ok) _snack('Connexion impossible');
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final social = SocialService.instance;
    final state = context.watch<AppState>();
    final groupCode = state.joinedGroup;

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
                Text('Défis', style: Theme.of(context).textTheme.displayMedium),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Bloque en groupe. Celui qui résiste le plus gagne.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),

            // ---------- Non connecté ----------
            if (!social.signedIn) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      const Icon(Icons.groups, size: 48, color: AppColors.halo),
                      const SizedBox(height: 12),
                      Text(
                        'Connecte-toi pour défier tes amis',
                        style: Theme.of(context).textTheme.titleLarge,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Seul ton pseudo et tes minutes de focus sont partagés. '
                        'Aucun accès à tes apps ni à tes contacts.',
                        style: Theme.of(context).textTheme.bodyMedium,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: _busy ? null : _signIn,
                          icon: const Icon(Icons.g_mobiledata, size: 28),
                          label: const Text('Continuer avec Google'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ]

            // ---------- Connecté, sans groupe ----------
            else if (groupCode.isEmpty) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Créer un groupe',
                          style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _nameCtrl,
                        style: const TextStyle(color: Colors.white),
                        decoration: const InputDecoration(
                          hintText: 'Nom du groupe (ex : Révisons à 5)',
                          hintStyle: TextStyle(color: AppColors.textFaint),
                          enabledBorder: OutlineInputBorder(
                            borderRadius:
                                BorderRadius.all(Radius.circular(14)),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: _busy ? null : _create,
                          child: const Text('Créer et obtenir un code'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Rejoindre avec un code',
                          style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _codeCtrl,
                        textCapitalization: TextCapitalization.characters,
                        style: const TextStyle(
                            color: Colors.white, letterSpacing: 4),
                        decoration: const InputDecoration(
                          hintText: 'Ex : 7KD9M2',
                          hintStyle: TextStyle(color: AppColors.textFaint),
                          enabledBorder: OutlineInputBorder(
                            borderRadius:
                                BorderRadius.all(Radius.circular(14)),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton(
                          onPressed: _busy ? null : _join,
                          child: const Text('Rejoindre le groupe'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ]

            // ---------- Connecté, avec groupe : classement ----------
            else ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 20, vertical: 16),
                  child: Row(
                    children: [
                      const Icon(Icons.emoji_events,
                          color: AppColors.warning),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Groupe actif',
                                style: Theme.of(context).textTheme.labelSmall),
                            Text(
                              '$groupCode · ${state.weeklyFocusMinutes()} min cette semaine',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(fontSize: 16),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.logout,
                            color: AppColors.textSecondary),
                        tooltip: 'Quitter le groupe',
                        onPressed: () {
                          SocialService.instance.leaveGroup(groupCode);
                          context.read<AppState>().setJoinedGroup('');
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _Leaderboard(
                code: groupCode,
                myMinutes: state.weeklyFocusMinutes(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Classement temps réel avec podium top 3.
class _Leaderboard extends StatelessWidget {
  final String code;
  final int myMinutes;

  const _Leaderboard({required this.code, required this.myMinutes});

  @override
  Widget build(BuildContext context) {
    final stream = SocialService.instance.leaderboard(code);

    if (stream == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            'Classement indisponible : Firebase non configuré '
            '(voir FIREBASE-SETUP.md).',
            style: TextStyle(color: AppColors.textSecondary),
          ),
        ),
      );
    }

    return StreamBuilder<List<ScoreEntry>>(
      stream: stream,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
          );
        }
        final entries = snap.data ?? const <ScoreEntry>[];
        final myUid = SocialService.instance.user?.uid ?? '';

        // Toujours m'inclure, même si ma sync n'a pas encore eu lieu.
        final list = List<ScoreEntry>.from(entries);
        if (!list.any((e) => e.uid == myUid)) {
          list.add(ScoreEntry(
              uid: myUid,
              name: SocialService.instance.displayName,
              minutesWeek: myMinutes));
          list.sort((a, b) => b.minutesWeek.compareTo(a.minutesWeek));
        }

        return Column(
          children: [
            // Podium top 3
            if (list.length >= 2)
              _Podium(top3: list.take(3).toList()),
            const SizedBox(height: 16),
            // Liste complète
            ...list.asMap().entries.map((e) {
              final rank = e.key + 1;
              final entry = e.value;
              final me = entry.uid == myUid;
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                decoration: BoxDecoration(
                  color: me ? AppColors.haloSoft : AppColors.deepPurple,
                  borderRadius: BorderRadius.circular(18),
                  border: me
                      ? Border.all(color: AppColors.halo)
                      : Border.all(color: const Color(0x11FFFFFF)),
                ),
                child: Row(
                  children: [
                    Text('$rank',
                        style: const TextStyle(
                            color: AppColors.textFaint, fontSize: 16)),
                    const SizedBox(width: 14),
                    CircleAvatar(
                      radius: 14,
                      backgroundColor: AppColors.halo,
                      child: Text(
                        entry.name.isNotEmpty
                            ? entry.name[0].toUpperCase()
                            : '?',
                        style: const TextStyle(
                            color: Colors.white, fontSize: 13),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        me ? 'Toi (${entry.name})' : entry.name,
                        style: const TextStyle(
                            color: Colors.white, fontWeight: FontWeight.w600),
                      ),
                    ),
                    Text('${entry.minutesWeek} min',
                        style: const TextStyle(
                            color: AppColors.textSecondary)),
                  ],
                ),
              );
            }),
          ],
        );
      },
    );
  }
}

/// Podium : 2e, 1er, 3e.
class _Podium extends StatelessWidget {
  final List<ScoreEntry> top3;
  const _Podium({required this.top3});

  @override
  Widget build(BuildContext context) {
    final medals = ['🥇', '🥈', '🥉'];
    // Ordre visuel : 2e, 1er, 3e
    final order = top3.length >= 3 ? [1, 0, 2] : [0, 1];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        for (final i in order)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Column(
              children: [
                CircleAvatar(
                  radius: i == 0 ? 30 : 24,
                  backgroundColor: AppColors.halo,
                  child: Text(
                    top3[i].name.isNotEmpty
                        ? top3[i].name[0].toUpperCase()
                        : '?',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: i == 0 ? 22 : 17,
                        fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 6),
                Text(medals[i], style: const TextStyle(fontSize: 18)),
                Text('${top3[i].minutesWeek} min',
                    style: const TextStyle(
                        color: AppColors.textSecondary, fontSize: 12)),
              ],
            ),
          ),
      ],
    );
  }
}
