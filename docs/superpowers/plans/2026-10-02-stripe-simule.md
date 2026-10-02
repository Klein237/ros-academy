# Stripe simulé pour les tests de bout en bout — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** tester l'abonnement pro de bout en bout, dans un vrai navigateur et contre le déploiement complet, sans compte Stripe : s'abonner, payer sur la page de paiement, passer en pro (lab sans quota, conteneur 2 vCPU / 4 Go), échec de paiement, résiliation, retour en free.

**Architecture :** un **faux Stripe** (`comptes/tests/fake_stripe.py`, FastAPI) imite la partie de Stripe que Comptes utilise :

- l'API : `POST /v1/checkout/sessions`, `POST /v1/billing_portal/sessions`, `GET /v1/subscriptions/<id>`, `GET /v1/prices/<id>`, avec la clé secrète en `Authorization: Bearer` ;
- les pages hébergées : page de paiement (« Payer », « Annuler ») et portail client (« Résilier à la fin de la période », « Résilier maintenant », « Simuler un échec de paiement ») ;
- les webhooks : `checkout.session.completed` et `customer.subscription.created|updated|deleted`, **signés comme Stripe** (`Stripe-Signature: t=…,v1=…`) et envoyés à Comptes.

Comptes ne change que par deux réglages : `STRIPE_API_BASE` (par défaut `https://api.stripe.com/v1`) et `STRIPE_REDIRECT_ORIGINS` (origines des pages de paiement et du portail, par défaut celles de Stripe). En CI, `deploy/docker-compose.stripe-simule.yml` ajoute le faux Stripe (image de Comptes, fichier monté) et configure Comptes.

## Écart trouvé en préparant le plan

- **CSP `form-action 'self'`** : Chrome applique `form-action` aux redirections qui suivent l'envoi d'un formulaire. « S'abonner » et « Gérer mon abonnement » (formulaires `POST` → redirection 303 vers Stripe) seraient bloqués. Correctif : `form-action 'self' <STRIPE_REDIRECT_ORIGINS>` (par défaut `https://checkout.stripe.com https://billing.stripe.com`). L'e2e l'a reproduit (redirection bloquée, l'étudiant reste sur `/compte/abonnement`) avant le correctif.

## Global Constraints

- Le faux Stripe ne fait pas partie du déploiement de production : il vit dans `tests/` et n'est lancé que par le fichier compose de test.
- Comptes reste inchangé dans son comportement : mêmes vérifications de signature, relecture de l'abonnement, rattachement par `client_reference_id`.

### Task 1 : Faux Stripe

- [x] `comptes/tests/fake_stripe.py` + tests unitaires (signature vérifiable par `verify_signature` de Comptes, cycle de vie des abonnements, clé refusée).

### Task 2 : Comptes configurable et CSP

- [x] `STRIPE_API_BASE`, `STRIPE_REDIRECT_ORIGINS` ; `form-action` élargi aux seules origines de redirection Stripe ; test.

### Task 3 : E2E et CI

- [x] `lab-ui/tests/e2e/stripe.spec.ts` (`@stripe`) : abonnement payé → pro (page, JWT, conteneur 2 vCPU / 4 Go) ; paiement annulé ; échec de paiement (`past_due` : toujours pro, avertissement) ; résiliation à la fin de la période puis immédiate → free.
- [x] `deploy/docker-compose.stripe-simule.yml` ; étape CI « Abonnement (Stripe simulé) ».
