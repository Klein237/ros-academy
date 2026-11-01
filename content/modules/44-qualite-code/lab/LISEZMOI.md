# Workspace du module « Qualité du code et revue »

Le package C++ `vitesse` du cours y est prêt : la fonction `borner()`, son test gtest et les tests de qualité d'`ament_lint_common`. Lancez `colcon build`, puis `colcon test --packages-select vitesse` et `colcon test-result --verbose`. Essayez aussi les linters un par un : `ament_cpplint src/vitesse`, `ament_uncrustify src/vitesse`.
