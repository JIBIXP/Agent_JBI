import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// Fond commun : dégradé violet profond → noir + halo lumineux violet.
class FocusBackground extends StatelessWidget {
  final Widget child;
  final bool showHalo;

  const FocusBackground({
    super.key,
    required this.child,
    this.showHalo = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0.0, -0.9),
          radius: 1.4,
          colors: [
            AppColors.deepPurple,
            AppColors.darker,
            AppColors.black,
          ],
          stops: [0.0, 0.55, 1.0],
        ),
      ),
      child: Stack(
        children: [
          if (showHalo)
            Positioned(
              top: -80,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  width: 320,
                  height: 320,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.haloSoft,
                        blurRadius: 120,
                        spreadRadius: 40,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          child,
        ],
      ),
    );
  }
}
