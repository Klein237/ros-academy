## Ce qui se passait

`yaw_to_quaternion` renvoyait `(0, 0, sin(θ), cos(θ))`. Un quaternion unitaire de rotation d'angle `α` autour d'un axe vaut `(axe · sin(α/2), cos(α/2))` : avec `sin(θ)` et `cos(θ)`, la rotation codée est donc `2θ`. Tant que le robot roule droit (`θ = 0`), rien ne se voit ; après un quart de tour vers `y`, TF2 le croit tourné de `2 × 90° = 180°`, face à `−x`, et place l'obstacle à sa gauche. Le quaternion reste unitaire : aucun outil ne signale d'erreur.

## Comment le diagnostiquer

- `tf2_echo odom base_link` affiche le *yaw* (RPY) : comparez-le à la pose connue du robot, dans plusieurs orientations ;
- une erreur qui **double** l'angle signe un oubli du demi-angle ;
- `/odom` utilisait la même fonction : RViz aurait aussi montré une flèche d'odométrie tournant deux fois trop vite.

## Comment l'éviter

- Ne réécrivez pas la conversion : `tf_transformations.quaternion_from_euler(0, 0, θ)` (paquet `tf_transformations`) ou `scipy.spatial.transform.Rotation` la fournissent, testée ;
- testez les conversions sur des valeurs connues : `θ = π/2` doit donner `z = w ≈ 0.707` ;
- vérifiez un nouveau repère dans RViz en tournant le robot, pas seulement en ligne droite.
