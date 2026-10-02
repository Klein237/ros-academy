# Certificats de fin de parcours — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** un étudiant qui termine un parcours avec une note finale d'au moins 10/20 obtient un certificat : un PDF à son nom (parcours, note, mention, détail des modules, date) et une page publique de vérification, joignable par l'adresse ou le QR code imprimés sur le PDF. Un employeur peut ainsi contrôler qu'il est authentique.

**Spec :** « Hors V1 : certificats » ; préalable livré : la vérification des exercices hors du conteneur de l'étudiant (les notes sont fiables).

**Architecture (service Comptes) :**

- **Émission** : sur la page Résultats, quand le parcours est terminé et la note ≥ `CERTIFICAT_NOTE_MIN` (10), l'étudiant saisit le nom à imprimer puis « Obtenir mon certificat » (`POST /compte/certificats`, `Origin` vérifié). Le certificat **fige** à cet instant le nom, le parcours, la note, la mention et les notes des modules : il ne change plus, même si le parcours est modifié ensuite. Un seul certificat par étudiant et par parcours.
- **Code** : 16 caractères aléatoires (base 32 sans caractères ambigus), imprévisible ; il sert d'adresse : `/certificats/<code>` (page publique) et `/certificats/<code>.pdf`.
- **Page publique** : nom, parcours, note, mention, date, état (valide ou **révoqué**) ; jamais l'adresse e-mail.
- **PDF** (reportlab, A4 paysage) : nom, parcours, note et mention, modules, date, code, adresse de vérification et QR code.
- **Révocation** (fraude, erreur) : le formateur révoque un certificat depuis la fiche de l'étudiant ; la page publique l'affiche comme révoqué et le PDF n'est plus servi.
- Mentions : ≥ 16 « Très bien », ≥ 14 « Bien », ≥ 12 « Assez bien ».

## Global Constraints

- Nom imprimé : 2 à 80 caractères, lettres (accents compris), espaces, apostrophes, traits d'union et points ; pas de balisage.
- La note figée est celle calculée par le serveur au moment de l'émission, jamais une valeur envoyée par le navigateur.
- Caddy : `/certificats*` → Comptes.

### Task 1 : Données et règles

- [x] Table `certificates` (migration `0004`) ; `certificats.py` : éligibilité, mention, code, émission ; tests.

### Task 2 : Pages et PDF

- [x] Résultats (formulaire), `POST /compte/certificats`, page publique, PDF, révocation par le formateur ; tests (non éligible refusé, double émission, nom invalide, page sans e-mail, PDF lisible avec le nom et le code, révoqué).

### Task 3 : Intégration

- [x] `requirements.txt` (reportlab), Caddy, `CERTIFICAT_NOTE_MIN`, README ; e2e : parcours terminé → certificat → page publique → PDF ; révocation.

## Résultats

- Comptes : 26 tests de certificats (mentions, noms valides et refusés, codes, non-éligibilité, figé à l'émission, une seule émission, page publique sans e-mail, numéro imprimé avec tirets, PDF lu avec pypdf, révocation) ; e2e : parcours terminé → certificat → page publique → PDF.
- Rendu du PDF vérifié visuellement (accents, « œ », deux colonnes de modules, QR code) ; page publique vérifiée dans le navigateur.
