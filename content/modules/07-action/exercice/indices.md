## Indice 1

Regardez les messages du nœud dans son terminal au moment où le goal se termine : rclpy affiche un avertissement.

## Indice 2

Un goal a un **état** (accepté, en cours, réussi, annulé, abandonné) distinct du **résultat** renvoyé. Qui fait passer le goal à l'état « réussi » dans `execute_callback` ?

## Indice 3

Avant de renvoyer le résultat quand la cible est atteinte, il faut appeler `goal_handle.succeed()`. Sans cet appel, rclpy considère que le goal a été abandonné (`ABORTED`).
