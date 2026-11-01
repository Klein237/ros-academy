## Le robot s'arrête sans raison dans l'allée 3

Le 1er novembre, le robot de livraison s'est arrêté plusieurs fois dans l'allée 3, sans obstacle devant lui. L'équipe a enregistré son lidar pendant 10 secondes : l'enregistrement est dans `src/arret_urgence/test/donnees/allee3`. Pendant ces 10 secondes, une seule vraie raison de s'arrêter : une personne traverse devant le robot, de **4 à 6 s**.

```bash
cd ~/ws/42-rejeu-donnees-exercice
source install/setup.bash
ros2 bag info src/arret_urgence/test/donnees/allee3
ros2 run arret_urgence arret_urgence                       # terminal 1
ros2 bag play src/arret_urgence/test/donnees/allee3        # terminal 2
ros2 topic echo /arret                                     # terminal 3 : des arrêts en dehors de 4 à 6 s ?
```

Votre mission, en trois temps :

1. **reproduire** le bug en rejouant l'enregistrement, et trouver sa cause dans les données ;
2. écrire, dans `src/arret_urgence/test/test_rejeu.py`, un **test de non-régression** qui échoue avec le code actuel. Le fichier contient déjà `lire_scans()`, qui lit l'enregistrement ;
3. **corriger** `obstacle_proche()` dans `src/arret_urgence/arret_urgence/detection.py`, sans changer sa signature, et vérifier que vos tests passent.

La vérification rejoue l'allée 3 sur votre `detection.py` : le robot doit s'arrêter pendant que la personne traverse, et seulement à ce moment-là. Elle lance aussi vos tests sur votre correction, où ils doivent réussir, puis sur la version d'origine de `detection.py`, où ils doivent échouer. Quand c'est prêt, cliquez sur **Vérifier**.
