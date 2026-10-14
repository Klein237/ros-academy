# RoboForge

Plateforme de formation au logiciel robotique, avec ROS 2, entièrement dans le navigateur : des cours, un lab ROS 2 par étudiant (terminal, éditeur, Vue 3D, bureau graphique pour RViz et Gazebo), des exercices tirés de vraies pannes, corrigés automatiquement, des QCM, des notes et un certificat vérifiable.

En ligne : <https://robotforge.cloud>

## Les parcours

| Parcours | Modules | Statut |
|---|---|---|
| Apprendre ROS 2 avec un robot mobile | 14 (`01` à `14`) : Linux, nœuds et topics, services, actions, paramètres, TF2, URDF, Gazebo, QoS, débogage, robot réel | disponible |
| Programmer un bras robotique avec ROS 2 | 4 (`30` à `33`) : bras manipulateur, URDF, cinématique directe et inverse | disponible |
| Docker pour la robotique | 4 (`20` à `23`) : image, Compose et DDS, déploiement | offert avec un certificat |
| Tests, architecture, estimation, planification | — | annoncés |

« Découvrir ROS 2 » (`/decouvrir/`) est une introduction ouverte à tous, sans compte. Les autres parcours s'achètent un par un (accès de 12 mois) une fois l'accès payant activé ; voir [deploy/README.md](deploy/README.md#accès-payant-achat-par-parcours-stripe).

## Architecture

```text
                         navigateur
                             │ HTTPS
                       ┌─────┴─────┐
                       │   Caddy   │  TLS, routage, en-têtes de sécurité,
                       └─────┬─────┘  forward_auth avant le cours d'un module
     ┌──────────────┬────────┼───────────┬──────────────────┐
 Contenus        Comptes    Hub      Lab UI (statique)   Grafana
 cours, éditeur, connexion, JupyterHub  terminal, éditeur, journaux
 tests des       accès,     + Docker-   Vue 3D, bureau
 modules         notes,     Spawner        │
                 Stripe       │            │ rosbridge, terminaux
              Postgres        └──► un conteneur ros-lab par étudiant
                                   (ROS 2 Jazzy, Gazebo Harmonic, sans Internet)
```

| Dossier | Rôle |
|---|---|
| `content/` | Les formations : `modules/<NN-id>/` (cours `index.md`, `qcm.yaml`, `lab/`, `exercice/`) et `parcours/<id>/parcours.yaml`. |
| `contenus/` | Service Contenus (FastAPI, Jinja) : site public, cours, éditeur d'administration avec historique git, publication après tests des modules. |
| `comptes/` | Service Comptes (FastAPI, SQLAlchemy, Postgres, migrations Alembic) : inscription, connexion (mot de passe, GitHub, Google), accès aux parcours, paiement Stripe, quotas de lab, QCM, exercices, notes, certificats, tableau de bord formateur, RGPD. |
| `hub/` | JupyterHub et son spawner : un conteneur par étudiant, limites CPU / mémoire / disque, réseau isolé. |
| `lab-ui/` | Interface du lab (Vite, TypeScript) : terminaux xterm, éditeur Monaco, Vue 3D (three.js, urdf-loader), bureau noVNC. |
| `images/ros-lab/` | Image du conteneur étudiant (ROS 2 Jazzy, Gazebo, rosbridge, outils). |
| `veille/` | Surveillance du serveur (CPU, mémoire, disque, services) et alertes par e-mail. |
| `deploy/` | Docker Compose, Caddyfile, variables (`.env.example`) et [guide de déploiement](deploy/README.md). |
| `scripts/` | Installation du serveur, démarrage local, sauvegardes, tests des modules, schémas des cours. |
| `tests/` | Tests d'intégration (sessions, quotas) et des scripts. |

## Démarrer en local

Il faut Docker (8 Go de mémoire au moins) et les ports 80 et 443 libres.

```bash
git clone https://github.com/Klein237/ros-academy.git && cd ros-academy
scripts/demarrer-local.sh
```

La première fois, le script construit l'image ROS (15 à 40 minutes) et génère `deploy/.env`. Ouvrez ensuite <https://localhost> et acceptez le certificat local. Le lien de confirmation de l'inscription s'affiche à l'écran.

- `scripts/demarrer-local.sh arreter` : arrête, en gardant les données ;
- `scripts/demarrer-local.sh effacer` : efface les données locales ;
- `scripts/demarrer-local.sh --internet` : ouvre le site sur Internet le temps d'un essai (tunnel Cloudflare).

## Mettre en ligne

Sur un serveur Ubuntu avec un nom de domaine :

```bash
sudo scripts/installer-serveur.sh        # installation
git pull && sudo scripts/installer-serveur.sh   # mise à jour
```

Tout le reste (comptes, accès payant et Stripe, sauvegardes, journaux, RGPD, capacité) est dans [deploy/README.md](deploy/README.md).

## Écrire une formation

Les formations s'éditent depuis l'éditeur (« Mon compte » → « Éditer les formations », pour les adresses de `ADMIN_EMAILS`) ou directement dans `content/`. Le format d'un module, des exercices et des QCM est décrit dans le [guide de rédaction](contenus/academy_content/guide.md), aussi affiché dans l'éditeur.

Un module avec exercice est testé dans l'image `ros-lab`, sans réseau, avant chaque publication et dans la CI :

1. `setup.sh` installe l'exercice, avec le bug ;
2. `check.sh` doit échouer ;
3. avec `solution/`, `check.sh` doit réussir ;
4. le lab guidé compile, puis `lab_test.sh` vérifie que ses nœuds démarrent.

```bash
python3 scripts/test_modules.py 05-noeud    # un module ; sans argument : tous (image ros-lab:0.1.0 construite)
python3 scripts/schemas/generer.py          # régénère les schémas SVG des cours
```

## Tests

```bash
# services Python (un environnement par service)
cd contenus && pip install -r requirements-dev.txt && python -m pytest
cd comptes  && pip install -r requirements-dev.txt && python -m pytest
cd hub      && pip install -r requirements-dev.txt && python -m pytest
cd veille   && pip install -r requirements-dev.txt && python -m pytest

# interface du lab
cd lab-ui && npm ci && npm test && npm run build
```

La CI (`.github/workflows/ci.yml`) lance ces tests, puis le démarrage local complet, les tests de tous les modules dans l'image ROS, et les tests de bout en bout Playwright (lab, Vue 3D, comptes, paiement contre un faux Stripe, quotas et capacité).
