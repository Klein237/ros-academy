## « No executable found »

Une collègue vous confie le package `demo_pkg`, qui contient un nœud `talker` publiant sur `/bavardage`. Le workspace compile sans erreur, le package est bien trouvé… mais le nœud refuse de démarrer :

```bash
cd ~/ws/04-workspace-exercice
source install/setup.bash
ros2 run demo_pkg talker
# No executable found
```

Le code du nœud (`src/demo_pkg/demo_pkg/talker.py`) est correct. Trouvez ce qui empêche `ros2 run` de le lancer, corrigez, recompilez, puis cliquez sur **Vérifier**.
