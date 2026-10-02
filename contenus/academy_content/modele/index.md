---
titre: Nouveau module
resume: Résumé en une ou deux phrases, affiché dans la liste du parcours.
duree: 1 h
---
# Nouveau module

**Objectifs :**

- premier objectif ;
- deuxième objectif.

## 1. Le concept

Expliquez le concept en quelques paragraphes.

## 2. Le lab guidé

Un bloc de code avec `fichier=chemin` contient un fichier complet du lab guidé : il reçoit un bouton « Ouvrir dans le lab », et les tests de publication vérifient que le lab compile avec ce fichier.

```bash
cd ~/ws/MODULE
colcon build --symlink-install
source install/setup.bash
```

Deux blocs `python` et `cpp` qui se suivent s'affichent en onglets.
