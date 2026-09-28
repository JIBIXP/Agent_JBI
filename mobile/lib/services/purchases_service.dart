import 'package:purchases_flutter/purchases_flutter.dart';

/// Gestion unifiée des achats (StoreKit + Google Play Billing) via RevenueCat.
/// Sans clé API configurée, l'app tourne en mode "gratuit pur" (aucun crash).
class PurchasesService {
  static final PurchasesService instance = PurchasesService._();
  PurchasesService._();

  static const _appleApiKey =
      String.fromEnvironment('REVENUECAT_APPLE_KEY', defaultValue: '');
  static const _googleApiKey =
      String.fromEnvironment('REVENUECAT_GOOGLE_KEY', defaultValue: '');
  static const entitlementPro = 'pro';

  bool isPro = false;

  bool get configured => _appleApiKey.isNotEmpty || _googleApiKey.isNotEmpty;

  Future<void> init() async {
    if (!configured) return;
    try {
      final key = _googleApiKey.isNotEmpty ? _googleApiKey : _appleApiKey;
      await Purchases.setLogLevel(LogLevel.warn);
      final configuration = PurchasesConfiguration(key);
      await Purchases.configure(configuration);
      await refreshEntitlements();
    } catch (_) {
      // Pas de connexion ou clé invalide : on reste en mode gratuit.
    }
  }

  Future<void> refreshEntitlements() async {
    if (!configured) return;
    try {
      final customerInfo = await Purchases.getCustomerInfo();
      isPro = customerInfo.entitlements.all[entitlementPro]?.isActive == true;
    } catch (_) {
      isPro = false;
    }
  }

  /// Lance l'achat. L'essai gratuit 30 jours (carte demandée, débit auto
  /// après 30 jours sauf annulation) se configure dans App Store Connect /
  /// Google Play Console : rien à coder ici.
  Future<bool> purchase() async {
    if (!configured) return false;
    try {
      final offerings = await Purchases.getOfferings();
      final packages = offerings.current?.availablePackages ?? const [];
      if (packages.isEmpty) return false;
      final monthly = offerings.current?.monthly;
      final package = monthly ?? packages.first;
      final customerInfo = await Purchases.purchasePackage(package);
      isPro = customerInfo.entitlements.all[entitlementPro]?.isActive == true;
      return isPro;
    } catch (_) {
      return false;
    }
  }

  Future<void> restore() async {
    if (!configured) return;
    try {
      final customerInfo = await Purchases.restorePurchases();
      isPro = customerInfo.entitlements.all[entitlementPro]?.isActive == true;
    } catch (_) {
      // ignore
    }
  }
}
