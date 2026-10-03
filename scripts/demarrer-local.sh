#!/usr/bin/env bash
# ROS Academy sur votre ordinateur (Linux, macOS, ou Windows avec WSL2), pour essayer :
#
#   scripts/demarrer-local.sh            démarre (la première fois : configuration et image ROS)
#   scripts/demarrer-local.sh arreter    arrête tout (vos données sont gardées)
#   scripts/demarrer-local.sh lien       affiche le dernier lien de connexion (si vous l'avez manqué)
#   scripts/demarrer-local.sh effacer    arrête et efface toutes les données locales
#
# Options : --admin ADRESSE (votre adresse, administrateur et formateur), --non-interactif,
#   --internet : essai ouvert à tous, par un tunnel Cloudflare gratuit et sans compte, sur une
#     adresse https://<mots-au-hasard>.trycloudflare.com qui disparaît à l'arrêt (voir
#     deploy/README.md) ; les liens de connexion partent alors par e-mail (SMTP demandé la première fois)
#   --local : revenir à https://localhost seulement
#
# Prérequis : Docker (Docker Desktop sur macOS et Windows) avec au moins 8 Go de mémoire,
# et les ports 80 et 443 libres. Par défaut, le site est servi sur https://localhost avec un
# certificat local (le navigateur demande de l'accepter une fois). Sans serveur d'e-mail, le
# lien de connexion s'affiche directement sur la page.
set -euo pipefail

RACINE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=scripts/lib-image-ros.sh
. "$RACINE/scripts/lib-image-ros.sh"
DEPLOY="$RACINE/deploy"
ENV_FILE="$DEPLOY/.env"
ADMIN="" INTERACTIF=1 COMMANDE=demarrer
MODE=""   # internet, local, ou vide : garder celui de deploy/.env

etape() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
attention() { printf '   \033[33m⚠ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

compose() { (cd "$DEPLOY" && docker compose "$@"); }
valeur_env() { sed -n "s/^$2=//p" "$1" | tail -1; }

# Remplace (ou ajoute) CLE=VALEUR dans un fichier .env ; VALEUR vide : supprime la ligne
maj_env() {  # maj_env FICHIER CLE VALEUR
  local tmp
  tmp=$(mktemp)
  awk -v cle="$2" -v val="$3" '
    index($0, cle "=") == 1 { if (!fait && val != "") print cle "=" val; fait = 1; next }
    { print }
    END { if (!fait && val != "") print cle "=" val }
  ' "$1" > "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$1"
}

# Adresse publique du tunnel, lue dans son journal (la dernière : le tunnel en cours)
adresse_tunnel() {
  grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
}

# Labs simultanés d'après la mémoire donnée à Docker : ~1,5 Go par lab, 4 Go pour la plateforme
labs_possibles() {  # labs_possibles MEMOIRE_GO
  local n=$(( ($1 - 4) * 2 / 3 ))
  [ "$n" -lt 1 ] && n=1
  [ "$n" -gt 6 ] && n=6   # un ordinateur sert aussi à autre chose
  echo "$n"
}

# deploy/.env pour un essai local, à partir de .env.example (portable : pas de sed -i, absent de macOS)
generer_env_local() {  # generer_env_local EXEMPLE SORTIE ADMIN LABS
  local exemple=$1 sortie=$2 admin=$3 labs=$4 tmp
  tmp=$(mktemp)
  awk -v admin="$admin" -v labs="$labs" \
      -v s1="$(openssl rand -hex 32)" -v s2="$(openssl rand -hex 32)" -v s3="$(openssl rand -hex 32)" \
      -v s4="$(openssl rand -hex 32)" -v s5="$(openssl rand -hex 32)" '
    /^JWT_SECRET=/ { print "JWT_SECRET=" s1; next }
    /^JUPYTERHUB_CRYPT_KEY=/ { print "JUPYTERHUB_CRYPT_KEY=" s2; next }
    /^HUB_ADMIN_TOKEN=/ { print "HUB_ADMIN_TOKEN=" s3; next }
    /^POSTGRES_PASSWORD=/ { print "POSTGRES_PASSWORD=" s4; next }
    /^GRAFANA_ADMIN_PASSWORD=/ { print "GRAFANA_ADMIN_PASSWORD=" s5; next }
    /^DOMAIN=/ { print "DOMAIN=localhost"; next }
    /^ADMIN_EMAILS=/ { print "ADMIN_EMAILS=" admin; next }
    /^ACTIVE_SERVER_LIMIT=/ { print "ACTIVE_SERVER_LIMIT=" labs; next }
    /^CONNEXION_LIEN_A_L_ECRAN=/ { print "CONNEXION_LIEN_A_L_ECRAN=1"; next }
    /^VEILLE_SEUIL_DISQUE=/ { print "VEILLE_SEUIL_DISQUE=95"; next }   # un PC a souvent un disque bien rempli
    { print }
  ' "$exemple" > "$tmp"
  if grep -q '^[A-Z_]*=remplacer' "$tmp"; then
    rm -f "$tmp"
    fail "valeur d'exemple non remplacée dans .env"
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$sortie"
}

lire_options() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --admin) ADMIN=$2; shift 2 ;;
      --non-interactif) INTERACTIF=0; shift ;;
      --internet) MODE=internet; shift ;;
      --local) MODE=local; shift ;;
      demarrer|arreter|lien|effacer) COMMANDE=$1; shift ;;
      -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
      *) fail "argument inconnu : $1 (--help)" ;;
    esac
  done
}

verifier_docker() {
  command -v docker >/dev/null || fail "Docker introuvable : installez Docker Desktop (macOS, Windows) ou Docker Engine (Linux)"
  docker compose version >/dev/null 2>&1 || fail "docker compose introuvable (Docker Compose v2 requis)"
  docker info >/dev/null 2>&1 || fail "Docker ne répond pas : démarrez Docker Desktop (ou sudo systemctl start docker)"
  command -v openssl >/dev/null || fail "openssl introuvable"
  command -v curl >/dev/null || fail "curl introuvable"
  MEMOIRE_GO=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 / 1024 ))
  info "Docker $(docker version --format '{{.Server.Version}}'), $MEMOIRE_GO Go de mémoire pour Docker"
  if [ "$MEMOIRE_GO" -lt 7 ]; then
    attention "moins de 8 Go pour Docker : augmentez-la (Docker Desktop → Settings → Resources) ; un seul lab à la fois"
  fi
}

configurer() {
  etape "Configuration"
  if [ -f "$ENV_FILE" ]; then
    info "deploy/.env existe déjà : gardé (supprimez-le, ou « effacer », pour repartir de zéro)"
    ADMIN=$(valeur_env "$ENV_FILE" ADMIN_EMAILS)
    return
  fi
  if [ -z "$ADMIN" ]; then
    [ "$INTERACTIF" = 1 ] || fail "--admin ADRESSE requis en mode non interactif"
    read -r -p "   Votre adresse e-mail (compte administrateur et formateur) : " ADMIN
  fi
  [[ $ADMIN =~ ^[^@[:space:]]+@[^@[:space:]]+$ ]] || fail "adresse invalide : $ADMIN"
  local labs
  labs=$(labs_possibles "$MEMOIRE_GO")
  generer_env_local "$DEPLOY/.env.example" "$ENV_FILE" "$ADMIN" "$labs"
  info "deploy/.env créé : localhost, $labs lab(s) simultané(s), lien de connexion affiché à l'écran"
}

demander_smtp() {
  [ -n "$(valeur_env "$ENV_FILE" SMTP_HOST)" ] && return
  [ "$INTERACTIF" = 1 ] || fail "hors de localhost, les liens de connexion partent par e-mail : renseignez SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD et SMTP_FROM dans deploy/.env (exemples dans le fichier)"
  info "Hors de localhost, les liens de connexion partent par e-mail : il faut un serveur d'envoi."
  info "Exemple Gmail : serveur smtp.gmail.com, port 587, votre adresse, un « mot de passe d'application »"
  info "(compte Google → Sécurité → Validation en deux étapes → Mots de passe des applications)."
  local hote port user pass from
  read -r -p "   Serveur SMTP : " hote
  read -r -p "   Port [587] : " port
  read -r -p "   Identifiant : " user
  read -r -s -p "   Mot de passe : " pass; echo
  read -r -p "   Expéditeur [ROS Academy <$user>] : " from
  [ -n "$hote" ] && [ -n "$user" ] && [ -n "$pass" ] || fail "serveur, identifiant et mot de passe sont nécessaires"
  from=${from:-ROS Academy <$user>}
  # entre apostrophes : ni Docker Compose ni le shell n'interprètent alors $, espaces ou <>
  [[ $pass$from != *"'"* ]] || fail "apostrophe impossible dans le mot de passe ou l'expéditeur"
  maj_env "$ENV_FILE" SMTP_HOST "$hote"
  maj_env "$ENV_FILE" SMTP_PORT "${port:-587}"
  maj_env "$ENV_FILE" SMTP_USER "$user"
  maj_env "$ENV_FILE" SMTP_PASSWORD "'$pass'"
  maj_env "$ENV_FILE" SMTP_FROM "'$from'"
}

# Adresse du site : localhost, ou un tunnel vers Internet (--internet, gardé ensuite dans deploy/.env)
configurer_acces() {
  if [ -z "$MODE" ]; then
    case "$(valeur_env "$ENV_FILE" COMPOSE_FILE)" in *internet*) MODE=internet ;; *) MODE=local ;; esac
  fi
  if [ "$MODE" = local ]; then
    if [ "$(valeur_env "$ENV_FILE" DOMAIN)" != localhost ]; then
      maj_env "$ENV_FILE" DOMAIN localhost
      maj_env "$ENV_FILE" COMPOSE_FILE ""
      maj_env "$ENV_FILE" CONNEXION_LIEN_A_L_ECRAN 1
      info "retour à https://localhost"
    fi
    return
  fi
  etape "Accès par Internet (tunnel Cloudflare)"
  maj_env "$ENV_FILE" COMPOSE_FILE "docker-compose.yml:docker-compose.internet.yml"
  maj_env "$ENV_FILE" CONNEXION_LIEN_A_L_ECRAN 0
  demander_smtp
}

# Démarre le tunnel (et Caddy), puis met son adresse dans DOMAIN : les liens envoyés par e-mail,
# les cookies et les vérifications d'origine l'utilisent. Le tunnel déjà ouvert garde la sienne.
ouvrir_tunnel() {
  local adresse="" essai
  for essai in 1 2 3; do
    compose up -d --build tunnel || fail "démarrage du tunnel impossible"
    info "ouverture du tunnel (essai $essai/3)…"
    for _ in $(seq 1 30); do
      adresse=$(compose logs tunnel 2>/dev/null | adresse_tunnel)
      [ -n "$adresse" ] && break 2
      # le tunnel s'arrête si Cloudflare refuse (service gratuit sans garantie) : nouvel essai
      [ -n "$(compose ps -q --status exited tunnel 2>/dev/null)" ] && break
      sleep 2
    done
    attention "pas d'adresse : $(compose logs --no-log-prefix tunnel 2>/dev/null | grep -v '^ *$' | tail -1)"
    if [ "$essai" -lt 3 ]; then sleep $((essai * 10)); fi
  done
  [ -n "$adresse" ] || fail "Cloudflare n'a pas donné d'adresse (service gratuit sans garantie) : réessayez dans quelques minutes ; détails : cd deploy && docker compose logs tunnel"
  maj_env "$ENV_FILE" DOMAIN "${adresse#https://}"
  info "adresse publique : $adresse"
}

image_ros() {
  etape "Image ROS des labs"
  local image
  image=$(valeur_env "$ENV_FILE" ROS_LAB_IMAGE)
  image_ros_a_jour "${image:-ros-lab:0.1.0}" "$RACINE/images/ros-lab"
}

demarrer() {
  verifier_docker
  configurer
  configurer_acces
  image_ros
  etape "Démarrage"
  [ "$MODE" = internet ] && ouvrir_tunnel
  DOMAINE=$(valeur_env "$ENV_FILE" DOMAIN)
  compose up -d --build || fail "démarrage impossible (un autre programme utilise peut-être les ports 80 ou 443)"
  info "attente du site…"
  # le site sur ce PC (avec le tunnel, Caddy sert en HTTP le nom public : HTTPS est fait par Cloudflare)
  if [ "$MODE" = internet ]; then
    site() { curl -sf --noproxy '*' -H "Host: $DOMAINE" -H "X-Forwarded-Proto: https" "http://127.0.0.1$1" >/dev/null 2>&1; }
  else
    site() { curl -ksf --noproxy '*' "https://localhost$1" >/dev/null 2>&1; }
  fi
  for _ in $(seq 1 120); do
    site /hub/api && site / && site /connexion && break
    sleep 2
  done
  site /connexion || fail "le site ne répond pas : cd deploy && docker compose logs"
  etape "Prêt"
  if [ "$DOMAINE" = localhost ]; then
    info "Ouvrez https://localhost (acceptez le certificat local la première fois)."
    info "Connexion : « Connexion », votre adresse $ADMIN, puis le bouton « Se connecter » de la page."
  else
    curl -sf -o /dev/null "https://$DOMAINE/connexion" 2>/dev/null \
      || attention "l'adresse publique ne répond pas encore depuis ce PC : réessayez dans une minute"
    info "Adresse publique, à donner à vos testeurs : https://$DOMAINE"
    info "Ouverte à tous tant que le site tourne ; « scripts/demarrer-local.sh arreter » la ferme."
    info "Nouvelle adresse à chaque démarrage. Retour à localhost : scripts/demarrer-local.sh --local"
    info "Connexion : « Connexion », votre adresse : le lien arrive par e-mail."
    info "E-mail de test : cd deploy && docker compose exec comptes python -m academy_comptes.mail $ADMIN"
  fi
  info "Ensuite : un parcours → « Ouvrir le lab » ; « Mon compte » → éditeur et tableau de bord formateur."
  info "Arrêter : scripts/demarrer-local.sh arreter (vos données sont gardées)"
}

case_commande() {
  case "$COMMANDE" in
    demarrer) demarrer ;;
    arreter)
      verifier_docker
      compose down
      info "arrêté ; « scripts/demarrer-local.sh » pour redémarrer"
      ;;
    lien)
      compose logs comptes 2>/dev/null | grep "lien de connexion pour" | tail -1 | sed 's/.*lien de connexion pour/Lien pour/' \
        || info "aucun lien dans les journaux (le lien s'affiche sur la page de connexion)"
      ;;
    effacer)
      verifier_docker
      if [ "$INTERACTIF" = 1 ]; then
        read -r -p "   Effacer comptes, résultats, formations modifiées et fichiers des labs ? [oui/N] " ok
        [ "$ok" = oui ] || { info "rien n'est effacé"; exit 0; }
      fi
      compose down -v
      for v in $(docker volume ls -q --filter name=ros-lab-home-); do docker volume rm "$v" >/dev/null; done
      rm -f "$ENV_FILE"
      info "tout est effacé (l'image ROS est gardée) ; « scripts/demarrer-local.sh » pour repartir de zéro"
      ;;
  esac
}

if [ "${DEMARRER_LOCAL_TEST:-0}" != 1 ]; then
  lire_options "$@"
  case_commande
fi
