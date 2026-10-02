#!/usr/bin/env bash
# Installe ROS Academy sur un serveur Ubuntu (22.04 ou 24.04), depuis le dépôt cloné :
#
#   git clone https://github.com/Klein237/ros-academy.git && cd ros-academy
#   sudo scripts/installer-serveur.sh
#
# Le script pose les questions qui manquent (domaine, adresse de l'administrateur, SMTP),
# puis : Docker et outils, pare-feu des labs, image ROS, dossiers des étudiants limités
# à 1 Go, deploy/.env (secrets générés), démarrage, vérifications et e-mail de test.
# Il est rejouable : un deploy/.env existant est gardé tel quel (secrets compris).
#
# Options (sans elles, le script les demande) :
#   --domaine NOM          ex. academy.mon-domaine.fr (DNS de type A vers ce serveur)
#   --admin ADRESSE        administrateur et formateur (ADMIN_EMAILS)
#   --smtp-host HÔTE --smtp-port PORT --smtp-user UTILISATEUR --smtp-password MDP --smtp-from EXPÉDITEUR
#   --sans-smtp            pas d'e-mail (les liens de connexion restent dans les journaux)
#   --homes-taille TAILLE  image disque des dossiers étudiants (défaut : 100G, creuse)
#   --sessions N           labs simultanés (défaut : calculé d'après le processeur et la mémoire)
#   --editeur-nom NOM --editeur-adresse ADRESSE --hebergeur TEXTE   mentions légales (modifiables ensuite)
#   --env CLÉ=VALEUR       ligne ajoutée à deploy/.env (répétable)
#   --non-interactif       ne rien demander : échoue si une valeur obligatoire manque
#   -h, --help
set -euo pipefail

RACINE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib-image-ros.sh
. "$RACINE/scripts/lib-image-ros.sh"
DEPLOY="$RACINE/deploy"
ENV_FILE="$DEPLOY/.env"
HOMES_IMG=/var/lib/ros-academy/homes.img
HOMES_DIR=/srv/ros-academy/homes

DOMAINE="" ADMIN="" SMTP_HOST="" SMTP_PORT="" SMTP_USER="" SMTP_PASSWORD="" SMTP_FROM=""
SANS_SMTP=0 HOMES_TAILLE=100G SESSIONS="" INTERACTIF=1
EDITEUR_NOM="" EDITEUR_ADRESSE="" HEBERGEUR=""
EXTRA_ENV=()

etape() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
attention() { printf '   \033[33m⚠ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

demander() {  # demander VARIABLE "question" [secret]
  local var=$1 question=$2 secret=${3:-} valeur
  [ -n "${!var}" ] && return
  [ "$INTERACTIF" = 1 ] || fail "option manquante pour : $question (mode non interactif)"
  if [ -n "$secret" ]; then read -r -s -p "   $question : " valeur; echo; else read -r -p "   $question : " valeur; fi
  printf -v "$var" '%s' "$valeur"
}

# Labs simultanés : ~1,5 Go de mémoire par lab (2 Go au plus, rarement atteints) en gardant 4 Go
# pour la plateforme, et pas plus de 4 labs par vCPU (mesuré : 35 labs sur 4 vCPU, démarrage lent).
sessions_conseillees() {  # sessions_conseillees MEMOIRE_GO VCPU
  local par_memoire=$(( ($1 - 4) * 2 / 3 )) par_cpu=$(( $2 * 4 ))
  local n=$(( par_memoire < par_cpu ? par_memoire : par_cpu ))
  [ "$n" -lt 2 ] && n=2
  echo "$n"
}

# Valeur d'une clé dans un fichier .env (dernière occurrence)
valeur_env() { sed -n "s/^$2=//p" "$1" | tail -1; }

# deploy/.env à partir de .env.example : secrets générés, réponses du script
generer_env() {  # generer_env EXEMPLE SORTIE
  local exemple=$1 sortie=$2 tmp
  tmp=$(mktemp)
  cp "$exemple" "$tmp"
  for cle in JWT_SECRET JUPYTERHUB_CRYPT_KEY HUB_ADMIN_TOKEN POSTGRES_PASSWORD GRAFANA_ADMIN_PASSWORD; do
    sed -i "s|^$cle=.*|$cle=$(openssl rand -hex 32)|" "$tmp"
  done
  remplacer() { sed -i "s|^$1=.*|$1=$(printf '%s' "$2" | sed 's/[|&\\]/\\&/g')|" "$tmp"; }
  remplacer DOMAIN "$DOMAINE"
  remplacer ADMIN_EMAILS "$ADMIN"
  remplacer ACTIVE_SERVER_LIMIT "$SESSIONS"
  remplacer SMTP_HOST "$SMTP_HOST"
  remplacer SMTP_PORT "${SMTP_PORT:-587}"
  remplacer SMTP_USER "$SMTP_USER"
  remplacer SMTP_PASSWORD "$SMTP_PASSWORD"
  remplacer SMTP_FROM "$SMTP_FROM"
  remplacer CONNEXION_LIEN_A_L_ECRAN 0
  remplacer EDITEUR_NOM "$EDITEUR_NOM"
  remplacer EDITEUR_ADRESSE "$EDITEUR_ADRESSE"
  remplacer HEBERGEUR "$HEBERGEUR"
  # dossiers des étudiants à quota (lignes commentées dans l'exemple)
  sed -i '/^# *LAB_HOMES_DIR=/d; /^# *COMPOSE_FILE=/d' "$tmp"
  {
    echo
    echo "# --- Ajouté par scripts/installer-serveur.sh"
    echo "LAB_HOMES_DIR=$HOMES_DIR"
    echo "COMPOSE_FILE=docker-compose.yml:docker-compose.quotas.yml"
    for ligne in "${EXTRA_ENV[@]}"; do echo "$ligne"; done
  } >> "$tmp"
  local restants
  restants=$(grep '^[A-Z_]*=remplacer' "$tmp" | cut -d= -f1 | tr '\n' ' ' || true)
  if [ -n "$restants" ]; then
    rm -f "$tmp"
    fail "valeur d'exemple non remplacée dans $sortie : $restants"
  fi
  install -m 600 "$tmp" "$sortie"
  rm -f "$tmp"
}

lire_options() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --domaine) DOMAINE=$2; shift 2 ;;
      --admin) ADMIN=$2; shift 2 ;;
      --smtp-host) SMTP_HOST=$2; shift 2 ;;
      --smtp-port) SMTP_PORT=$2; shift 2 ;;
      --smtp-user) SMTP_USER=$2; shift 2 ;;
      --smtp-password) SMTP_PASSWORD=$2; shift 2 ;;
      --smtp-from) SMTP_FROM=$2; shift 2 ;;
      --sans-smtp) SANS_SMTP=1; shift ;;
      --editeur-nom) EDITEUR_NOM=$2; shift 2 ;;
      --editeur-adresse) EDITEUR_ADRESSE=$2; shift 2 ;;
      --hebergeur) HEBERGEUR=$2; shift 2 ;;
      --homes-taille) HOMES_TAILLE=$2; shift 2 ;;
      --sessions) SESSIONS=$2; shift 2 ;;
      --env) [[ $2 =~ ^[A-Z_][A-Z0-9_]*= ]] || fail "--env attend CLÉ=VALEUR : $2"; EXTRA_ENV+=("$2"); shift 2 ;;
      --non-interactif) INTERACTIF=0; shift ;;
      -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
      *) fail "option inconnue : $1 (--help)" ;;
    esac
  done
}

verifier_systeme() {
  etape "Vérifications"
  [ "$(id -u)" = 0 ] || fail "à lancer en root : sudo $0"
  [ -f "$DEPLOY/docker-compose.yml" ] || fail "lancer depuis le dépôt cloné (deploy/ introuvable)"
  . /etc/os-release
  [ "${ID:-}" = ubuntu ] || attention "système $PRETTY_NAME : testé sur Ubuntu 22.04 et 24.04 seulement"
  MEMOIRE_GO=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
  VCPU=$(nproc)
  DISQUE_GO=$(df -BG --output=avail /var/lib | tail -1 | tr -dc '0-9')
  info "$PRETTY_NAME, $VCPU vCPU, $MEMOIRE_GO Go de mémoire, $DISQUE_GO Go libres"
  [ "$MEMOIRE_GO" -ge 7 ] || fail "8 Go de mémoire au minimum (trouvé : $MEMOIRE_GO Go)"
  [ "$DISQUE_GO" -ge 15 ] || fail "15 Go libres au minimum dans /var/lib (trouvé : $DISQUE_GO Go)"
  [ "$DISQUE_GO" -ge 40 ] || attention "moins de 40 Go libres : l'image ROS (~5 Go) et les dossiers des étudiants (1 Go chacun) vont vite le remplir"
}

questions() {
  etape "Configuration"
  if [ -f "$ENV_FILE" ]; then
    info "deploy/.env existe déjà : il est gardé tel quel (supprimez-le pour tout reconfigurer)."
    DOMAINE=$(valeur_env "$ENV_FILE" DOMAIN)
    ADMIN=$(valeur_env "$ENV_FILE" ADMIN_EMAILS)
    SMTP_HOST=$(valeur_env "$ENV_FILE" SMTP_HOST)
    return
  fi
  demander DOMAINE "Nom de domaine (ex. academy.mon-domaine.fr)"
  [[ $DOMAINE =~ ^[A-Za-z0-9.-]+$ ]] || fail "nom de domaine invalide : $DOMAINE"
  demander ADMIN "Adresse e-mail de l'administrateur"
  [[ $ADMIN =~ ^[^@[:space:]]+@[^@[:space:]]+$ ]] || fail "adresse invalide : $ADMIN"
  if [ "$SANS_SMTP" = 0 ] && [ -z "$SMTP_HOST" ] && [ "$INTERACTIF" = 1 ]; then
    info "Envoi des e-mails (liens de connexion, alertes). Gmail : smtp.gmail.com, port 587,"
    info "mot de passe d'application. Laisser vide pour ne pas en envoyer (liens dans les journaux)."
    read -r -p "   Serveur SMTP : " SMTP_HOST
  fi
  if [ -n "$SMTP_HOST" ]; then
    SMTP_PORT=${SMTP_PORT:-587}
    demander SMTP_USER "Utilisateur SMTP"
    demander SMTP_PASSWORD "Mot de passe SMTP" secret
    SMTP_FROM=${SMTP_FROM:-"ROS Academy <$SMTP_USER>"}
  elif [ "$DOMAINE" != localhost ]; then
    attention "sans SMTP, les étudiants ne recevront pas leur lien de connexion"
  fi
  if [ "$INTERACTIF" = 1 ] && [ -z "$EDITEUR_NOM$EDITEUR_ADRESSE$HEBERGEUR" ]; then
    info "Mentions légales (obligatoires en ligne ; vide = à compléter plus tard dans deploy/.env) :"
    read -r -p "   Éditeur du site (votre nom ou votre société) : " EDITEUR_NOM
    read -r -p "   Adresse de l'éditeur : " EDITEUR_ADRESSE
    read -r -p "   Hébergeur (nom et adresse) : " HEBERGEUR
  fi
  if [ -z "$SESSIONS" ]; then
    SESSIONS=$(sessions_conseillees "$MEMOIRE_GO" "$VCPU")
    info "Labs simultanés : $SESSIONS (d'après $VCPU vCPU et $MEMOIRE_GO Go ; --sessions pour changer)"
  fi
}

verifier_dns() {
  [ "$DOMAINE" = localhost ] && { attention "DOMAIN=localhost : certificat local, pour un essai seulement"; return; }
  local ip_dns ip_locales
  ip_dns=$(getent ahostsv4 "$DOMAINE" | awk 'NR==1 {print $1}')
  ip_locales=$(hostname -I 2>/dev/null || true)
  if [ -z "$ip_dns" ]; then
    attention "$DOMAINE ne résout vers aucune adresse : créez l'enregistrement DNS de type A, sinon le certificat HTTPS échouera"
  elif ! grep -qw "$ip_dns" <<<"$ip_locales"; then
    info "$DOMAINE → $ip_dns (adresse publique ; vérifiez que c'est bien celle de ce serveur)"
  else
    info "$DOMAINE → $ip_dns : ce serveur"
  fi
}

installer_paquets() {
  etape "Paquets"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git xfsprogs openssl curl iptables >/dev/null
  if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    info "Docker déjà installé : $(docker --version)"
  else
    info "Installation de Docker…"
    curl -fsSL https://get.docker.com | sh >/dev/null
  fi
  systemctl enable --now docker >/dev/null 2>&1 || true
}

pare_feu() {
  etape "Pare-feu"
  # Les bridges des labs (rl-<n>) n'atteignent pas les services de l'hôte (sshd, bases…).
  # Un service systemd remet la règle à chaque démarrage (iptables-persistent désinstallerait ufw).
  cat > /etc/systemd/system/ros-academy-pare-feu.service <<'UNIT'
[Unit]
Description=ROS Academy : les labs (bridges rl-*) n'atteignent pas l'hôte
After=network-pre.target docker.service
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'iptables -C INPUT -i rl-+ -j DROP 2>/dev/null || iptables -I INPUT -i rl-+ -j DROP'

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now ros-academy-pare-feu.service >/dev/null 2>&1 \
    || { iptables -C INPUT -i rl-+ -j DROP 2>/dev/null || iptables -I INPUT -i rl-+ -j DROP; }
  iptables -C INPUT -i rl-+ -j DROP 2>/dev/null || fail "règle iptables des labs non posée"
  info "trafic des labs vers l'hôte refusé (iptables -i rl-+, service ros-academy-pare-feu)"
  if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
    info "ufw : ports 80 et 443 ouverts"
  else
    info "ufw inactif : vérifiez que seuls SSH, 80 et 443 sont ouverts chez votre hébergeur"
  fi
}

image_ros() {
  etape "Image ROS des labs"
  local image=""
  [ -f "$ENV_FILE" ] && image=$(valeur_env "$ENV_FILE" ROS_LAB_IMAGE)
  image_ros_a_jour "${image:-ros-lab:0.1.0}" "$RACINE/images/ros-lab" -q >/dev/null
  info "${image:-ros-lab:0.1.0} à jour"
}

dossiers_etudiants() {
  etape "Dossiers des étudiants (1 Go chacun)"
  local sortie
  if ! sortie=$("$RACINE/scripts/preparer-hote.sh" --image "$HOMES_IMG" --taille "$HOMES_TAILLE" \
                 --dossier "$HOMES_DIR" 2>&1); then
    printf '%s\n' "$sortie" | sed 's/^/   /'
    fail "préparation des dossiers des étudiants (XFS) impossible"
  fi
  printf '%s\n' "$sortie" | grep -v "Dans deploy/.env\|LAB_HOMES_DIR=\|COMPOSE_FILE=\|puis : cd deploy\|^Prêt\|^$" \
    | sed 's/^/   /' || true
}

ecrire_env() {
  [ -f "$ENV_FILE" ] && return
  etape "deploy/.env"
  generer_env "$DEPLOY/.env.example" "$ENV_FILE"
  info "créé (droits 600), secrets générés ; à sauvegarder hors du serveur"
}

demarrer() {
  etape "Démarrage"
  (cd "$DEPLOY" && docker compose up -d --build 2>&1 | tail -3 | sed 's/^/   /')
  local url="https://$DOMAINE"
  for _ in $(seq 1 90); do
    curl -ksf "$url/hub/api" >/dev/null && curl -ksf "$url/connexion" >/dev/null && break
    sleep 2
  done
  curl -ksf "$url/hub/api" >/dev/null || fail "le Hub ne répond pas sur $url (docker compose logs hub caddy)"
  curl -ksf "$url/connexion" >/dev/null || fail "Comptes ne répond pas sur $url (docker compose logs comptes)"
  info "Hub, Comptes et site en ligne"
  if [ "$DOMAINE" != localhost ]; then
    if curl -sf "$url/" >/dev/null; then
      info "certificat HTTPS valide"
    else
      attention "certificat HTTPS pas encore valide (DNS ou ports 80/443) : docker compose logs caddy"
    fi
  fi
  if [ -n "$SMTP_HOST" ]; then
    if (cd "$DEPLOY" && docker compose exec -T comptes python -m academy_comptes.mail "${ADMIN%%,*}") | sed 's/^/   /'; then
      info "e-mail de test envoyé à ${ADMIN%%,*}"
    else
      attention "l'e-mail de test a échoué : corrigez SMTP_* dans deploy/.env puis docker compose up -d comptes veille"
    fi
  fi
}

sauvegardes() {
  etape "Sauvegarde quotidienne"
  cat > /etc/systemd/system/ros-academy-sauvegarde.service <<UNIT
[Unit]
Description=ROS Academy : sauvegarde (base, formations, dossiers des étudiants, configuration)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=$RACINE/scripts/sauvegarder.sh
UNIT
  cat > /etc/systemd/system/ros-academy-sauvegarde.timer <<'UNIT'
[Unit]
Description=ROS Academy : sauvegarde tous les jours à 3 h 17

[Timer]
OnCalendar=*-*-* 03:17:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT
  systemctl daemon-reload
  systemctl enable --now ros-academy-sauvegarde.timer >/dev/null 2>&1 || attention "timer de sauvegarde non activé"
  info "tous les jours à 3 h 17 dans /var/backups/ros-academy ($(valeur_env "$ENV_FILE" SAUVEGARDE_JOURS || true) jours gardés)"
  info "copie hors du serveur recommandée : scripts/sauvegarder.sh --copier-vers (deploy/README.md)"
}

resume() {
  etape "Terminé"
  info "Site : https://$DOMAINE"
  info "Administrateur : $ADMIN (« Mon compte » → éditeur, tableau de bord formateur, journaux)"
  info "Avant d'accueillir des étudiants : test de charge (deploy/README.md, « Test de charge »)"
  info "Sauvegarde maintenant : sudo scripts/sauvegarder.sh ; état : systemctl list-timers ros-academy-sauvegarde"
  info "Mise à jour : git pull, puis cd deploy && docker compose up -d --build"
}

main() {
  lire_options "$@"
  verifier_systeme
  questions
  verifier_dns
  installer_paquets
  pare_feu
  image_ros
  dossiers_etudiants
  ecrire_env
  demarrer
  sauvegardes
  resume
}

# INSTALLER_TEST=1 : les fonctions sont chargées sans rien installer (tests)
if [ "${INSTALLER_TEST:-0}" != 1 ]; then
  main "$@"
fi
