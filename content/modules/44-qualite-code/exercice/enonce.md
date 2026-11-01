## La pull request de Sam

Sam propose le package C++ `vitesse` : la fonction `borner()`, qui limite la vitesse envoyée aux moteurs, et son test gtest. Le code compile, mais la CI est rouge. Awa, qui relit la pull request, a laissé trois commentaires :

> **Awa, sur `borner.hpp`** : « `using namespace std;` dans un en-tête s'impose à tous ceux qui l'incluent. Et la garde ne suit pas notre convention. »
>
> **Awa, sur `borner.cpp`** : « Que renvoie `borner(-2.0, 0.5)` ? En marche arrière, le robot ne doit pas dépasser la vitesse maximale non plus. »
>
> **Awa, sur `test_borner.cpp`** : « Il manque la licence en tête de fichier, comme partout dans le dépôt. »

```bash
cd ~/ws/44-qualite-code-exercice
colcon test --packages-select vitesse
colcon test-result --verbose        # tous les problèmes, linter par linter
```

Votre mission : rendre `colcon test` **vert**, en traitant la revue d'Awa et tout ce que signalent les linters et le test unitaire.

Règles de l'équipe, que la vérification contrôle :

- tous les tests doivent avoir tourné : cpplint, uncrustify, copyright, lint_cmake, xmllint, cppcheck et `test_borner` ;
- les trois cas de `test_borner` restent : un test qui dérange se corrige, il ne se supprime pas ;
- aucun linter n'est désactivé ni contourné : pas d'exclusion dans `CMakeLists.txt`, pas de `NOLINT`.

Quand c'est prêt, cliquez sur **Vérifier**.
