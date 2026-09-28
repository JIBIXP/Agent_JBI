import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Palette "cinématique premium" : violet profond vers noir, halo lumineux.
class AppColors {
  static const deepPurple = Color(0xFF1A1033);
  static const darker = Color(0xFF0B0716);
  static const black = Color(0xFF05030A);
  static const halo = Color(0xFF7C3AED);
  static const haloSoft = Color(0x557C3AED);
  static const textPrimary = Color(0xFFFFFFFF);
  static const textSecondary = Color(0x99FFFFFF);
  static const textFaint = Color(0x55FFFFFF);
  static const success = Color(0xFF34D399);
  static const warning = Color(0xFFFBBF24);
}

class AppTheme {
  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.black,
      colorScheme: base.colorScheme.copyWith(
        primary: AppColors.halo,
        secondary: AppColors.halo,
        surface: AppColors.deepPurple,
        error: const Color(0xFFF87171),
      ),
      textTheme: GoogleFonts.interTextTheme(base.textTheme).copyWith(
        displayLarge: GoogleFonts.archivoBlack(
          textStyle: const TextStyle(
            fontSize: 40,
            fontWeight: FontWeight.w900,
            color: AppColors.textPrimary,
            height: 1.05,
            letterSpacing: -1,
          ),
        ),
        displayMedium: GoogleFonts.archivoBlack(
          textStyle: const TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w900,
            color: AppColors.textPrimary,
            height: 1.1,
          ),
        ),
        titleLarge: const TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: AppColors.textPrimary,
        ),
        bodyMedium: const TextStyle(
          fontSize: 15,
          color: AppColors.textSecondary,
          height: 1.45,
        ),
        labelSmall: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: AppColors.textFaint,
          letterSpacing: 1.2,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: Colors.black,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          side: const BorderSide(color: Color(0x33FFFFFF)),
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
        ),
      ),
      cardTheme: CardTheme(
        color: AppColors.deepPurple,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      ),
      dividerColor: const Color(0x1AFFFFFF),
    );
  }
}
