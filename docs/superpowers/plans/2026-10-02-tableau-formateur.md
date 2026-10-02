# Tableau de bord formateur — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** le formateur voit où en sont ses étudiants et où ils bloquent : chiffres clés, état de chaque module du parcours (réussites, vérifications ratées, indices, QCM), liste des étudiants avec progression et note, fiche détaillée d'un étudiant, export CSV.

**Spec :** « Hors V1 : tableau de bord formateur ». Les données sont déjà en base (Comptes) ; on ajoute le nombre de vérifications par exercice.

**Architecture :** pages servies par Comptes, réservées aux adresses de `ADMIN_EMAILS` (le formateur est l'administrateur, comme pour l'éditeur) :

- `/compte/formateur` : chiffres clés (étudiants inscrits, actifs sur 7 jours, labs en cours, minutes de lab du mois, abonnés pro), tableau des modules, tableau des étudiants (recherche) ;
- `/compte/formateur/etudiants/<id>` : détail par module (tentatives et notes de QCM, vérifications, indices, date de réussite, note) ;
- `/compte/formateur/etudiants.csv` : export (tableur).

**Indicateurs par module :** étudiants qui l'ont commencé (QCM tenté, indice demandé ou exercice vérifié), exercice réussi (taux), « bloqués » (exercice tenté au moins 3 fois sans réussite), vérifications moyennes avant réussite, indices demandés (1, 2, 3), meilleure note de QCM moyenne, note moyenne des modules terminés.

## Global Constraints

- Accès : session Comptes + adresse dans `ADMIN_EMAILS` ; sinon 403 (ou connexion). Les administrateurs ne sont pas comptés comme étudiants.
- Pas de JavaScript (CSP stricte) : la recherche est un formulaire `GET` ; les taux sont des barres d'une seule teinte avec la valeur écrite.
- Export CSV : séparateur `;` et BOM UTF-8 (ouverture directe dans un tableur français) ; cellules commençant par `= + - @` préfixées d'une apostrophe (injection de formules).

### Task 1 : Données

- [x] `exercises.verifications` (migration `0003`), incrémenté à chaque vérification.

### Task 2 : Calculs et pages

- [x] `formateur.py` (requêtes groupées, calcul des notes par `grading`) ; tests sur un jeu de données construit (taux, bloqués, moyennes, note finale, dernière activité, admins exclus).
- [x] Pages, export CSV, lien depuis « Mon compte » ; tests (accès refusé, recherche, CSV sûr).

### Task 3 : E2E

- [x] Le formateur voit l'étudiant d'un e2e (QCM, indice, vérification ratée) dans le tableau et sa fiche ; un étudiant est refusé.

## Écarts constatés pendant l'implémentation

- **Barres sans style en ligne** : la CSP de Comptes refuse les attributs `style=` ; les taux utilisent `<progress>` (une seule teinte, la valeur toujours écrite à côté).
- **e2e** : la vérification ratée (indicateur « bloqués ») est couverte par les tests de Comptes ; l'e2e suit un étudiant avec une tentative de QCM et un indice, la fiche et l'export.
- Rendu vérifié en clair, en sombre et à 390 px de large (les tableaux défilent dans leur cadre).
