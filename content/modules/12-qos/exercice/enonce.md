## Le superviseur ne voit pas la batterie

Le fabricant du robot a livré le pilote de sa nouvelle batterie, `batterie_node`. Un collègue a écrit `superviseur_node`, qui affiche la charge toutes les deux secondes et donne l'alerte sous 20 %. Le fichier launch démarre les deux nœuds, sans aucune erreur :

```bash
ros2 launch my_pkg supervision.launch.py
# [superviseur_node-2] [WARN] [...] [superviseur_node]: Aucune mesure de batterie reçue
# [superviseur_node-2] [WARN] [...] [superviseur_node]: Aucune mesure de batterie reçue
```

Pourtant, `ros2 topic echo /battery_state` affiche bien les mesures.

Le workspace de l'exercice est `~/ws/12-qos-exercice` (déjà compilé). Le pilote `batterie_node.py` est le code du fabricant : **ne le modifiez pas**. Trouvez pourquoi le superviseur ne reçoit rien, corrigez-le, puis cliquez sur **Vérifier**.
