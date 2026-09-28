// Défi social : groupes d'amis + classement du temps résisté.
//
// Fonctionne uniquement si le build a été fait avec
// --dart-define=FIREBASE_AVAILABLE=true ET que flutterfire configure a tourné.
// Sinon, `available == false` et toutes les méthodes renvoient des valeurs
// d'échec silencieuses : l'app reste utilisable 100 % hors ligne.

import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../firebase_options_stub.dart';

const _firebaseEnabled = bool.fromEnvironment('FIREBASE_AVAILABLE');

class SocialService {
  static final SocialService instance = SocialService._();
  SocialService._();

  bool _initialized = false;
  bool get available => _firebaseEnabled && _initialized;

  User? get user => _firebaseEnabled ? FirebaseAuth.instance.currentUser : null;
  bool get signedIn => user != null;

  String get displayName =>
      user?.displayName ?? user?.email?.split('@').first ?? 'Moi';

  /// Init au démarrage. Sans clé Firebase, ne lève jamais d'exception.
  Future<void> init() async {
    if (!_firebaseEnabled || _initialized) return;
    try {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );
      _initialized = true;
      debugPrint('SocialService: Firebase initialisé');
    } catch (e) {
      debugPrint('SocialService: Firebase indisponible ($e)');
    }
  }

  // ---------- Auth ----------

  Future<bool> signInWithGoogle() async {
    if (!available) return false;
    try {
      final googleUser = await GoogleSignIn().signIn();
      if (googleUser == null) return false; // annulé
      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );
      await FirebaseAuth.instance.signInWithCredential(credential);
      return true;
    } catch (e) {
      debugPrint('signInWithGoogle: $e');
      return false;
    }
  }

  Future<void> signOut() async {
    if (!_firebaseEnabled) return;
    try {
      await GoogleSignIn().signOut();
      await FirebaseAuth.instance.signOut();
    } catch (_) {}
  }

  // ---------- Groupes ----------

  static String _code() {
    // Code 6 caractères A-Z 0-9 sans ambiguïté.
    const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    final rand = DateTime.now().microsecondsSinceEpoch;
    return List.generate(
      6,
      (i) => alphabet[(rand >> (i * 5)) & 31],
    ).join();
  }

  /// Crée un groupe et renvoie son code de partage. '' = échec silencieux.
  Future<String> createGroup(String name) async {
    if (!signedIn) return '';
    try {
      final code = _code();
      final uid = user!.uid;
      await FirebaseFirestore.instance.collection('groups').doc(code).set({
        'name': name,
        'owner': uid,
        'createdAt': FieldValue.serverTimestamp(),
        'members': {uid: displayName},
      });
      await FirebaseFirestore.instance
          .collection('groups')
          .doc(code)
          .collection('scores')
          .doc(uid)
          .set({
        'name': displayName,
        'minutesWeek': 0,
        'updatedAt': FieldValue.serverTimestamp(),
      });
      return code;
    } catch (e) {
      debugPrint('createGroup: $e');
      return '';
    }
  }

  /// Rejoint un groupe avec son code. true = succès.
  Future<bool> joinGroup(String code) async {
    if (!signedIn) return false;
    final clean = code.trim().toUpperCase();
    if (clean.length != 6) return false;
    try {
      final ref =
          FirebaseFirestore.instance.collection('groups').doc(clean);
      final snap = await ref.get();
      if (!snap.exists) return false;
      final uid = user!.uid;
      await ref.update({'members.$uid': displayName});
      await ref.collection('scores').doc(uid).set({
        'name': displayName,
        'minutesWeek': 0,
        'updatedAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));
      return true;
    } catch (e) {
      debugPrint('joinGroup: $e');
      return false;
    }
  }

  Future<void> leaveGroup(String code) async {
    if (!signedIn) return;
    try {
      final uid = user!.uid;
      await FirebaseFirestore.instance
          .collection('groups')
          .doc(code)
          .update({'members.$uid': FieldValue.delete()});
      await FirebaseFirestore.instance
          .collection('groups')
          .doc(code)
          .collection('scores')
          .doc(uid)
          .delete();
    } catch (_) {}
  }

  /// Le groupe rejoint par l'utilisateur (stocké localement côté UI).
  static const joinedGroupPrefKey = 'joinedGroupCode';

  // ---------- Classement ----------

  /// Stream temps réel du classement d'un groupe (top 50).
  /// Renvoie null si Firebase indisponible.
  Stream<List<ScoreEntry>>? leaderboard(String code) {
    if (!signedIn) return null;
    return FirebaseFirestore.instance
        .collection('groups')
        .doc(code)
        .collection('scores')
        .orderBy('minutesWeek', descending: true)
        .limit(50)
        .snapshots()
        .map((s) => s.docs
            .map((d) => ScoreEntry(
                  uid: d.id,
                  name: d.data()['name'] as String? ?? '?',
                  minutesWeek: d.data()['minutesWeek'] as int? ?? 0,
                ))
            .toList());
  }

  /// Publie les minutes de focus de la semaine (appelé en fin de session).
  Future<void> publishMinutes(String code, int weeklyMinutes) async {
    if (!signedIn || code.isEmpty) return;
    try {
      await FirebaseFirestore.instance
          .collection('groups')
          .doc(code)
          .collection('scores')
          .doc(user!.uid)
          .set({
        'name': displayName,
        'minutesWeek': weeklyMinutes,
        'updatedAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));
    } catch (e) {
      debugPrint('publishMinutes: $e');
    }
  }
}

/// Une ligne du classement.
class ScoreEntry {
  final String uid;
  final String name;
  final int minutesWeek;

  const ScoreEntry({
    required this.uid,
    required this.name,
    required this.minutesWeek,
  });

  bool isMe(String myUid) => uid == myUid;
}
