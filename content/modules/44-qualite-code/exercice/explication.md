## Ce qui bloquait

- **uncrustify** : le style de `borner.cpp` (indentation à quatre espaces, accolades, espaces autour des opérateurs) ne suivait pas celui de ROS 2. `ament_uncrustify --reformat` le corrige en une commande ;
- **cpplint** : la garde `BORNER_H` ne suivait pas le chemin du fichier, il fallait `VITESSE__BORNER_HPP_` ; `using namespace std;` dans un en-tête est interdit ; et `std::max` et `std::min` demandent `<algorithm>`, inclus avant les en-têtes du projet ;
- **copyright** : `test_borner.cpp` n'avait pas l'en-tête de licence ;
- **test_borner** : `borner()` ne bornait pas la marche arrière, `borner(-2.0, 0.5)` renvoyait `-2.0`. C'est le commentaire d'Awa : un relecteur pense au cas limite que l'auteur a oublié.

## La correction de borner()

```cpp
#include <algorithm>

#include "vitesse/borner.hpp"

double borner(double valeur, double maximum)
{
  return std::max(-maximum, std::min(valeur, maximum));
}
```

## À retenir

- les outils vérifient la forme, la revue vérifie le fond : les deux sont nécessaires ;
- le formatage se corrige avec un outil, jamais à la main ;
- un linter ou un test qui échoue se corrige, il ne se désactive pas.
