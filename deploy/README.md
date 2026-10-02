# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32`, `DOMAIN` par le domaine, et renseigner `ADMIN_EMAILS`, le SMTP et, si souhaité, GitHub / Google (voir « Comptes » ci-dessous).
3. Dossiers des étudiants limités à 1 Go (voir « Espace disque des étudiants ») : `sudo apt install xfsprogs`, puis `sudo scripts/preparer-hote.sh --image /var/lib/ros-academy/homes.img --taille 200G` (ou `--partition /dev/sdX1`), et ajouter à `.env` les deux lignes `LAB_HOMES_DIR` et `COMPOSE_FILE` affichées par le script.
4. `cd deploy && docker compose up -d --build` (construit aussi le Lab UI dans l'image Caddy : Node n'est pas nécessaire sur le serveur), puis, toujours depuis `deploy/` : `set -a; . ./.env; set +a; BASE_URL=https://$DOMAIN ../scripts/wait_for_hub.sh`

## Comptes des étudiants (service Comptes)
- **Connexion** sur `/connexion` : lien magique par e-mail (toujours disponible), GitHub et Google (affichés quand `GITHUB_CLIENT_*` / `GOOGLE_CLIENT_*` sont renseignés ; URL de retour `https://<domaine>/connexion/github/retour` et `…/google/retour`). Un compte = une adresse e-mail vérifiée : GitHub puis Google sous la même adresse ouvrent le même compte.
- **Sans SMTP** (`SMTP_HOST` vide), le lien de connexion est écrit dans `docker compose logs comptes` : pratique en développement, à ne pas laisser en production.
- **Lab** : les boutons « Ouvrir le lab » du site passent par `/compte/lab`, qui vérifie le quota du mois (formule `free` : 600 min ; `pro` : sans limite) puis émet le jeton court du Hub. Le Lab UI prévient 5 min avant la fin du quota ; à zéro, Comptes arrête le serveur et le Hub refuse tout nouveau démarrage (`COMPTES_URL`, vérifié avant chaque démarrage).
- **Progression** : QCM (2 tentatives, la meilleure est gardée), indices (−15 % chacun) et réussite des exercices sont enregistrés dans Postgres (volume `postgres-data`) ; notes sur `/compte/resultats`. Les corrections, indices et explications ne sortent de Contenus que par Comptes : Caddy bloque ces routes internes et Contenus exige un secret dérivé de `JWT_SECRET`.
- **Serveur plein** : le Lab UI prend un ticket dans la file de Comptes et affiche la position ; le démarrage est retenté quand le tour arrive.
- **Administration** : une adresse de `ADMIN_EMAILS` connectée ouvre l'éditeur depuis « Mon compte » (`/compte/admin`).
- **Certificats** : un parcours terminé avec une note finale d'au moins `CERTIFICAT_NOTE_MIN` (10/20) donne droit à un certificat, demandé depuis la page Résultats (l'étudiant saisit le nom à imprimer). Il fige le nom, la note, la mention (≥ 12 Assez bien, ≥ 14 Bien, ≥ 16 Très bien) et les notes des modules. PDF : `/certificats/<numéro>.pdf` ; vérification publique (sans adresse e-mail) : `/certificats/<numéro>`, imprimée sur le PDF avec un QR code. Le formateur peut révoquer un certificat depuis la fiche de l'étudiant (fraude, erreur) : la page publique l'affiche alors comme révoqué et le PDF n'est plus servi.
- **Tableau de bord formateur** (`/compte/formateur`, adresses de `ADMIN_EMAILS`, lien dans « Mon compte ») : chiffres clés (inscrits, actifs sur 7 jours, labs en cours, minutes du mois, parcours terminés, abonnés pro) ; par module : étudiants qui l'ont commencé, exercice réussi, « bloqués » (3 vérifications ratées ou plus), vérifications avant réussite, indices demandés, QCM et note moyens ; liste des étudiants (recherche, du plus récemment actif) avec fiche détaillée ; export CSV pour un tableur (`;`, UTF-8).
- Changer la formule d'un étudiant : `docker compose exec postgres psql -U comptes -d comptes -c "UPDATE users SET formule='pro' WHERE email='…'"`.
- Sauvegarde : `docker compose exec postgres pg_dump -U comptes comptes > comptes.sql`.

## Abonnement pro (Stripe)
Formule `pro` : lab sans limite de minutes, conteneur 2 vCPU / 4 Go. Proposée sur `/compte/abonnement` seulement quand les trois variables `STRIPE_*` sont renseignées.
1. Dans Stripe (mode test d'abord) : créer un produit « ROS Academy pro » et un **prix récurrent mensuel** (9 €) ; copier son identifiant `price_…` dans `STRIPE_PRICE_ID`.
2. Activer et configurer le **portail client** (Paramètres → Facturation → Portail client) : résiliation, mise à jour de la carte, factures.
3. Déclarer le **webhook** `https://<domaine>/api/comptes/stripe/webhook` avec les événements `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted` ; copier son secret `whsec_…` dans `STRIPE_WEBHOOK_SECRET`, et la clé secrète dans `STRIPE_SECRET_KEY`.
4. `docker compose up -d comptes`. Tester avec la carte `4242 4242 4242 4242` ; en local, `stripe listen --forward-to https://localhost/api/comptes/stripe/webhook` remplace l'étape 3.
- Stripe fait foi : chaque événement est vérifié (signature), puis l'abonnement est relu auprès de Stripe. `active`, `trialing` et `past_due` (paiement en cours de relance) donnent la formule pro ; une résiliation prend effet à la fin de la période payée.
- La nouvelle formule s'applique au conteneur à la prochaine ouverture du lab.
- Avant d'ouvrir les paiements au public : TVA (Stripe Tax) et conditions générales de vente.
- **Tests sans compte Stripe** : `deploy/docker-compose.stripe-simule.yml` ajoute un faux Stripe (`comptes/tests/fake_stripe.py` : API, page de paiement, portail client, webhooks signés) et y branche Comptes (`STRIPE_API_BASE`, `STRIPE_REDIRECT_ORIGINS`, à ne jamais définir en production). `docker compose -f docker-compose.yml -f docker-compose.stripe-simule.yml up -d comptes fake-stripe`, puis `cd lab-ui && npx playwright test --grep @stripe`.

## Tester un accès étudiant sans compte (diagnostic)
Le parcours normal passe par `/connexion`. Pour tester le Hub seul, un jeton peut être émis à la main :
```bash
set -a; . deploy/.env; set +a
pip install PyJWT==2.9.0
TOKEN=$(python scripts/mint_token.py --sub essai --plan free)
echo "https://$DOMAIN/hub/jwt_login?token=$TOKEN"
```
Ouvrir le lien : connexion, redirection vers le Lab UI (`/lab/`), écran d'attente pendant le démarrage du conteneur, puis terminal, éditeur et vue 2D. Pour ouvrir directement un fichier ou un dossier (bouton « Ouvrir dans le lab » du site), ajouter `&next=` avec l'URL encodée de `/lab/?open=ws/module-02/talker.py&dossier=ws/module-02`.

Vérifier aussi la session par l'API :
```bash
# démarrer le serveur de l'étudiant
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai/server
# vérifier qu'il est prêt (servers."".ready == true)
curl -sk -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai
# créer un terminal dans le conteneur
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/user/essai/api/terminals
```

## Formations (service Contenus)
- Le site des formations est servi à la racine (`/`, `/parcours/…`, `/modules/…`). Son contenu vit dans un dépôt Git, dans le volume `contenus-data`, initialisé au premier démarrage avec le parcours « ROS 2 Fondamentaux » du dossier `content/`.
- **Éditer** : connectez-vous avec une adresse de `ADMIN_EMAILS`, puis « Mon compte » → « Éditer les formations » (la session de l'éditeur dure 12 h). En secours, un lien administrateur valable 5 minutes peut être émis à la main :
  ```bash
  set -a; . deploy/.env; set +a
  echo "https://$DOMAIN/admin/login?token=$(python scripts/mint_token.py --sub moi --role admin)"
  ```
  L'éditeur permet de modifier chaque fichier d'un module (aperçu en direct), le QCM en formulaire, l'ordre et les coefficients des parcours, de créer un module à partir d'un modèle, et de restaurer une version antérieure. Le **guide de rédaction** est dans l'éditeur (`/admin/guide/`).
- **Publier** : les étudiants ne voient une modification qu'après « Publier le brouillon », qui teste chaque module modifié dans un conteneur `ros-lab` sans réseau. Une publication refusée affiche le journal des tests et laisse la version en ligne intacte.
- **Sauvegarde** : `CONTENT_GIT_REMOTE` (facultatif) pousse les branches `brouillon` et `publie` vers un dépôt distant à chaque publication ; l'URL doit être accessible en écriture depuis le conteneur. Sinon, sauvegardez le volume `contenus-data`.
- Tester les modules hors de la plateforme : `ROS_LAB_IMAGE=ros-lab:0.1.0 python scripts/test_modules.py [module…]` (dépendances : `pip install -r contenus/requirements.txt`).

## Lab UI
- Servi par Caddy sous `/lab/`, sur la même origine que le Hub. Après `/hub/jwt_login`, la page demande à `/hub/lab_token` un jeton d'une heure limité au serveur de l'étudiant.
- Le Lab UI arrête lui-même le conteneur après 20 min sans interaction dans la page (avertissement 5 min avant) ; le culler du Hub reste le filet de sécurité quand l'onglet est fermé.
- Développement : `cd lab-ui && npm ci && npm test` (tests unitaires), `npm run dev` (serveur Vite), `npm run build`.
- Tests de bout en bout, contre un déploiement lancé : `set -a; . deploy/.env; set +a; cd lab-ui && npx playwright test --grep-invert @limit`.
- Robot simulé pour la vue 2D : `academy-diffbot` dans un terminal (`/cmd_vel` → `/odom`).

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Journaux et alertes
- **Journaux** : `https://<domaine>/admin/journaux/` (lien « Journaux » de l'éditeur ; même session que l'éditeur, administrateur seulement). Grafana affiche le tableau de bord « Plateforme » : volume par service, erreurs de la dernière heure, alertes de la veille, recherche dans tous les journaux et dans ceux des labs des étudiants (étiquettes `service`, `conteneur`, `etudiant`). Loki les garde 30 jours (volume `loki-data`), y compris ceux des conteneurs étudiants arrêtés.
- Exemples de recherche (Explore, source Loki) : `{service="comptes"} |= "Quota épuisé"`, `{service="lab", etudiant="u42"}`, `{service="hub"} |~ "(?i)error"`.
- **Alertes** : le service `veille` vérifie toutes les 15 s le CPU (moyenne sur 5 min), la mémoire et le disque de l'hôte, ainsi que Hub, Comptes, Contenus et Loki (alerte après 3 échecs de suite). E-mail aux `ADMIN_EMAILS` par le SMTP de Comptes à l'entrée en alerte, rappel toutes les 6 h, message au retour à la normale (5 points sous le seuil). Seuils : `VEILLE_SEUIL_CPU`, `VEILLE_SEUIL_MEMOIRE`, `VEILLE_SEUIL_DISQUE` (80 %). Sans SMTP, les alertes ne sont que dans les journaux.
- Les journaux Docker de chaque conteneur sont limités en taille sur le disque (l'historique est dans Loki).

## Test de charge
Avant chaque ouverture de session ou d'atelier (spec : 30 à 40 sessions simultanées), sur le serveur :
```bash
set -a; . deploy/.env; set +a
pip install requests websocket-client PyJWT
python scripts/charge.py --sessions 35 --limite $ACTIVE_SERVER_LIMIT --duree 300
```
Le script ouvre les sessions en même temps (pire cas), lance `ros2 topic list` dans chacune, simule une activité (une commande par session toutes les 30 s), vérifie qu'une session de plus est refusée (HTTP 429 : file d'attente), puis nettoie tout. Il échoue si une session ne fonctionne pas ou si le 95e centile de démarrage dépasse `--max-demarrage` (120 s). Suivre en parallèle le tableau de bord « Plateforme » et les alertes de la veille.

Mesure de référence (2 octobre 2026, machine de 4 vCPU / 16 Go, plus petite que le serveur visé) : 35 sessions sur 35 fonctionnelles, démarrage simultané en 66 s (médiane) et 70 s (max), 35 % de mémoire utilisée, 36ᵉ session refusée. La CI rejoue une version réduite (8 sessions).

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité, démarrages refusés pour quota.
- `docker compose logs comptes` : liens de connexion (sans SMTP), arrêts pour quota (`Quota épuisé : serveur de u… arrêté`), erreurs d'envoi d'e-mail. Pas de journal d'accès : il contiendrait les liens de connexion.
- `docker ps --filter name=jupyter-` : sessions actives.

## Espace disque des étudiants

- **Dossier personnel limité à 1 Go** (fichiers et workspaces ; 200 000 fichiers au plus) : chaque étudiant a un dossier `LAB_HOMES_DIR/<nom>` sur un XFS monté avec les quotas de projet, monté en `/home/etudiant` dans son lab. `scripts/preparer-hote.sh` prépare l'hôte une fois : image disque creuse (seul l'espace écrit est consommé) ou partition dédiée, montée au démarrage par `/etc/fstab`, et limite par défaut de tous les projets (`--quota`, `--inodes`). Le Hub rattache chaque nouveau dossier à son projet (10000 + id pour `u<id>`) sans droit particulier ; il refuse de démarrer si `LAB_HOMES_DIR` n'est pas un XFS avec `prjquota`.
- Dans le lab, `df -h ~` affiche la limite ; au-delà, l'écriture échoue (« No space left on device ») et l'étudiant libère de la place (`build/`, `log/` de colcon par exemple).
- Occupation : `sudo xfs_quota -x -c 'report -p -h' /srv/ros-academy/homes` ; changer la limite : relancer le script avec `--quota 2g`, ou pour un seul étudiant `sudo xfs_quota -x -c 'limit -p bhard=2g 10042' /srv/ros-academy/homes`.
- **Passer des volumes Docker aux dossiers à quota** (déploiement existant) : labs arrêtés, `sudo scripts/migrer-volumes.sh /srv/ros-academy/homes` copie chaque volume `ros-lab-home-u<id>` dans son dossier et le rattache à son projet ; les volumes sont gardés jusqu'à leur suppression manuelle.
- **Reste du conteneur** : la racine est en lecture seule ; `/tmp` (512 Mo) et `/var/tmp` (64 Mo) sont des tmpfs comptés dans la mémoire du lab. Un étudiant ne peut donc plus remplir le disque de l'hôte.
- Sans `LAB_HOMES_DIR` (développement), les dossiers sont des volumes Docker `ros-lab-home-<nom>`, sans limite de taille.

## Réseau des labs

Chaque étudiant a son propre réseau Docker (`ros-lab-<nom>`, `internal` : pas d'Internet), créé au démarrage de son lab et supprimé à l'arrêt. Seul le Hub le rejoint : un étudiant atteint l'API du Hub, mais pas les conteneurs des autres étudiants. Les sous-réseaux sont pris dans `LAB_SUBNETS` (par défaut `10.213.0.0/16`, découpé en /28, soit 4096 labs simultanés au plus) : choisir une plage qui ne recouvre aucun réseau de l'hôte. Au redémarrage, le Hub rejoint les réseaux des labs encore en cours et supprime les réseaux orphelins.

- `docker network ls --filter label=ros-academy.reseau-etudiant` : réseaux des labs en cours.

## Limites connues
- Le service Contenus monte la socket Docker pour tester les modules à la publication : comme le Hub, sa compromission équivaut à un accès root à l'hôte. Seul l'administrateur y a accès (jeton `role: admin`).
- `check.sh` est lisible depuis le conteneur de l'étudiant (`~/.academy/<module>`) : il sait ce qui est testé, ce qui est voulu (c'est le diagnostic qui est noté). Le modifier ne sert à rien (voir ci-dessous).
- Les serveurs étudiants (`/user/<nom>/`) partagent l'origine du Lab UI et un étudiant peut y servir n'importe quel fichier. Caddy leur impose `Content-Security-Policy: sandbox` : ces pages ont une origine opaque et ne peuvent lire ni les cookies du Hub, ni `/hub/lab_token`, ni les autres serveurs. Ne pas retirer cet en-tête ; à terme, des sous-domaines par étudiant (`subdomain_host`) supprimeraient le partage d'origine.
- Le jeton du Lab UI passe dans l'URL des WebSockets (`JUPYTERHUB_ALLOW_TOKEN_IN_URL=1`) : un navigateur ne peut pas y mettre d'en-tête. Il est limité au serveur de l'étudiant et expire en 1 h ; ne pas activer de journal d'accès Caddy qui enregistrerait les URL complètes.
- **Vérification des exercices hors du conteneur** : « Vérifier » fait lancer par Contenus le `check.sh` **publié** dans un conteneur `ros-lab` neuf (sans réseau, non-root, 1 vCPU / 2 Go), sur une copie du workspace de l'étudiant lue dans son volume monté en lecture seule (sans `build/`, `install/`, `log/` : tout est recompilé ; 200 Mo au plus). Seule cette vérification enregistre la réussite ; ni un `check.sh` modifié, ni une requête du navigateur ne le peuvent. Au plus `VERIFICATIONS_MAX` (4) vérifications en même temps. Un étudiant peut encore écrire un code qui trompe le test sans corriger la panne : c'est aux auteurs des modules d'écrire des `check.sh` qui testent le comportement, pas la forme.
- Les minutes de lab sont relevées chaque minute auprès du Hub : un serveur prêt compte une minute entière, et un étudiant hors quota peut garder son lab jusqu'au relevé suivant (une minute au plus).
- La limite de 1 Go par étudiant n'est appliquée qu'avec `LAB_HOMES_DIR` (hôte préparé par `scripts/preparer-hote.sh`).
- Sur certaines versions de Docker, un réseau `internal` laisse quand même les conteneurs joindre l'hôte via l'adresse de la passerelle du bridge : les services de l'hôte écoutant sur 0.0.0.0 (sshd, bases de données, supervision) peuvent alors être atteints depuis le code des étudiants. L'opérateur doit lier ces services à des interfaces précises, ou rejeter le trafic des réseaux étudiants vers l'hôte. Leurs bridges s'appellent tous `rl-<n>` : une seule règle suffit, `iptables -I INPUT -i rl-+ -j DROP` (à rendre persistante, par exemple avec `iptables-persistent`).
- Alloy (collecte des journaux) monte la socket Docker : comme le Hub et Contenus, sa compromission équivaut à un accès root à l'hôte. Il n'est joignable par aucun autre conteneur (réseau `journaux`, interne, sans port).
- Alloy découvre un nouveau conteneur en quelques secondes : les journaux d'un lab arrêté moins de ~10 s après son démarrage peuvent manquer.
- Le Hub s'exécute en root avec accès à la socket Docker (inhérent à DockerSpawner) : sa compromission équivaut à un accès root à l'hôte.
- Si l'hôte a du swap, Docker autorise par défaut chaque lab à en utiliser autant que sa mémoire : prévoir un swap de taille raisonnable (ou aucun).
