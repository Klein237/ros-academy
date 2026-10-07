## Le robot arrive… mais le goal échoue

Le serveur d'action `goto` a été ajouté à `diff_drive_node`. Quand on l'essaie, le robot rejoint bien le point demandé — la vue 2D le confirme, le feedback aussi — mais le client annonce un échec :

```bash
ros2 action send_goal --feedback /goto my_interface/action/Goto "{target: {x: 1.0, y: 0.5}}"
# ...
# Result:
#     reached: true
# Goal finished with status: ABORTED
```

Le code qui pilote l'équipe de robots considère le trajet comme raté et relance sans fin.

Le workspace de l'exercice est `~/ws/07-action-exercice` (déjà compilé). Trouvez pourquoi le goal se termine en `ABORTED`, corrigez, puis cliquez sur **Vérifier**.
