## Indice 1

Commencez par ce qui se corrige tout seul : `ament_uncrustify --reformat src/vitesse` remet le style aux normes. Relancez ensuite `colcon test` : il reste moins de messages, et chacun est plus facile à lire.

## Indice 2

Pour la licence, copiez l'en-tête de `borner.cpp`, qui est correct, en haut de `test_borner.cpp`. Pour la garde d'en-tête, cpplint vous donne le nom attendu dans son message : `VITESSE__BORNER_HPP_`, avec le même nom en commentaire après `#endif`. Supprimez `using namespace std;` et l'include qui ne sert à rien.

## Indice 3

Le test `MarcheArriere` échoue : `borner()` ne borne que vers le haut. `std::max(-maximum, std::min(valeur, maximum))` borne des deux côtés. `std::max` et `std::min` viennent de `<algorithm>` : incluez-le, avant `"vitesse/borner.hpp"`, sinon cpplint le signale. Lancez `ament_uncrustify --reformat` une dernière fois.
