## Ce qui se passait

Dans `execute_callback`, la branche « cible atteinte » renvoyait bien `Goto.Result(reached=True, …)`, mais sans appeler `goal_handle.succeed()`. L'**état** du goal et le **résultat** sont deux choses distinctes : l'état dit au client comment l'exécution s'est terminée. Quand `execute_callback` se termine sans avoir fixé l'état, rclpy le passe à `ABORTED` et l'écrit dans les journaux du nœud (*Goal state not set, assuming aborted*).

## Comment le diagnostiquer

- `ros2 action send_goal` affiche le statut final : `ABORTED` alors que `reached: true` ;
- les journaux du serveur contiennent l'avertissement de rclpy ;
- relisez chaque sortie de `execute_callback` : chacune doit appeler `succeed()`, `abort()` ou `canceled()`.

## Comment l'éviter

- Une règle simple : chaque `return` de `execute_callback` est précédé d'un changement d'état explicite ;
- testez les trois issues (réussite, annulation, échec) avec `ros2 action send_goal`, et pas seulement la réussite.
