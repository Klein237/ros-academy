#!/usr/bin/env bash
# Tests des fonctions de scripts/demarrer-local.sh (sans rien démarrer).
set -euo pipefail
DEPOT=$(cd "$(dirname "$0")/../.." && pwd)
DEMARRER_LOCAL_TEST=1 source "$DEPOT/scripts/demarrer-local.sh"
set +e
echecs=0
ok() { printf '  ✔ %s\n' "$1"; }
ko() { printf '  ✘ %s\n' "$1"; echecs=$((echecs + 1)); }
egal() { if [ "$2" = "$3" ]; then ok "$1"; else ko "$1 : attendu « $3 », obtenu « $2 »"; fi; }

echo "labs_possibles"
egal "8 Go" "$(labs_possibles 8)" 2
egal "16 Go" "$(labs_possibles 16)" 6
egal "32 Go (plafonné)" "$(labs_possibles 32)" 6
egal "4 Go (au moins 1)" "$(labs_possibles 4)" 1

echo "generer_env_local"
TMP=$(mktemp -d)
generer_env_local "$DEPOT/deploy/.env.example" "$TMP/.env" "moi@exemple.fr" 3
E="$TMP/.env"
egal "DOMAIN" "$(valeur_env "$E" DOMAIN)" localhost
egal "ADMIN_EMAILS" "$(valeur_env "$E" ADMIN_EMAILS)" moi@exemple.fr
egal "labs" "$(valeur_env "$E" ACTIVE_SERVER_LIMIT)" 3
egal "lien à l'écran" "$(valeur_env "$E" CONNEXION_LIEN_A_L_ECRAN)" 1
egal "pas de dossiers à quota" "$(grep -c '^LAB_HOMES_DIR=' "$E")" 0
egal "pas d'override compose" "$(grep -c '^COMPOSE_FILE=' "$E")" 0
for cle in JWT_SECRET JUPYTERHUB_CRYPT_KEY HUB_ADMIN_TOKEN POSTGRES_PASSWORD GRAFANA_ADMIN_PASSWORD; do
  v=$(valeur_env "$E" "$cle")
  if [[ $v =~ ^[0-9a-f]{64}$ ]]; then ok "$cle généré"; else ko "$cle : « $v »"; fi
done
egal "secrets distincts" "$(for c in JWT_SECRET HUB_ADMIN_TOKEN POSTGRES_PASSWORD; do valeur_env "$E" $c; done | sort -u | wc -l | tr -d ' ')" 3
egal "droits" "$(stat -c %a "$E" 2>/dev/null || stat -f %Lp "$E")" 600
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  if (cd "$DEPOT/deploy" && docker compose --env-file "$E" config --quiet 2>"$TMP/err"); then ok "docker compose config"; else ko "docker compose config : $(head -3 "$TMP/err")"; fi
fi

echo "maj_env"
maj_env "$E" DOMAIN essai-rapide.trycloudflare.com
maj_env "$E" SMTP_FROM "'ROS Academy <moi@exemple.fr>'"
maj_env "$E" COMPOSE_FILE docker-compose.yml:docker-compose.internet.yml
egal "remplace" "$(valeur_env "$E" DOMAIN)" essai-rapide.trycloudflare.com
egal "une seule ligne" "$(grep -c '^DOMAIN=' "$E")" 1
egal "valeur entre apostrophes" "$(valeur_env "$E" SMTP_FROM)" "'ROS Academy <moi@exemple.fr>'"
# shellcheck disable=SC1090
egal "deploy/.env reste lisible par le shell" "$( (set -a; . "$E"; echo "$SMTP_FROM") 2>&1)" "ROS Academy <moi@exemple.fr>"
egal "droits gardés" "$(stat -c %a "$E" 2>/dev/null || stat -f %Lp "$E")" 600
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  if (cd "$DEPOT/deploy" && docker compose --env-file "$E" config 2>"$TMP/err" >"$TMP/config"); then ok "docker compose config (tunnel)"; else ko "docker compose config (tunnel) : $(head -3 "$TMP/err")"; fi
  egal "Caddy en HTTP derrière le tunnel" "$(grep -c 'DOMAIN: http://$' "$TMP/config")" 1
  egal "service du tunnel" "$(grep -c 'cloudflare/cloudflared:' "$TMP/config")" 1
  if grep -q "SMTP_FROM: ROS Academy <moi@exemple.fr>" "$TMP/config"; then ok "expéditeur transmis tel quel"; else ko "expéditeur : $(grep SMTP_FROM "$TMP/config" | head -1)"; fi
fi
maj_env "$E" COMPOSE_FILE ""
egal "valeur vide : ligne supprimée" "$(grep -c '^COMPOSE_FILE=' "$E")" 0

echo "adresse_tunnel"
JOURNAL='tunnel-1  | 2026-10-02T22:17:03Z INF Requesting new quick Tunnel on trycloudflare.com...
tunnel-1  | 2026-10-02T22:17:05Z INF |  https://lot-pixel-quiet-river.trycloudflare.com                    |'
egal "adresse lue dans le journal" "$(adresse_tunnel <<<"$JOURNAL")" https://lot-pixel-quiet-river.trycloudflare.com
egal "pas encore d'adresse" "$(adresse_tunnel <<<'tunnel-1 | Requesting new quick Tunnel on trycloudflare.com...')" ""

echo "configurer_acces"
mkdir -p "$TMP/deploy"
generer_env_local "$DEPOT/deploy/.env.example" "$TMP/deploy/.env" moi@exemple.fr 2
(
  ENV_FILE="$TMP/deploy/.env" INTERACTIF=0 MODE=internet
  maj_env "$ENV_FILE" SMTP_HOST smtp.exemple.fr
  configurer_acces >/dev/null
  echo "$(valeur_env "$ENV_FILE" COMPOSE_FILE)|$(valeur_env "$ENV_FILE" CONNEXION_LIEN_A_L_ECRAN)"
  maj_env "$ENV_FILE" DOMAIN lot-pixel-quiet-river.trycloudflare.com   # posé par ouvrir_tunnel
  MODE="" configurer_acces >/dev/null; echo "$MODE"   # mode gardé dans deploy/.env
  MODE=local; configurer_acces >/dev/null
  echo "$(valeur_env "$ENV_FILE" DOMAIN)|$(grep -c '^COMPOSE_FILE=' "$ENV_FILE")|$(valeur_env "$ENV_FILE" CONNEXION_LIEN_A_L_ECRAN)"
) > "$TMP/acces" 2>&1
egal "--internet : tunnel, lien par e-mail" "$(sed -n 1p "$TMP/acces")" "docker-compose.yml:docker-compose.internet.yml|0"
egal "mode gardé au démarrage suivant" "$(sed -n 2p "$TMP/acces")" internet
egal "--local : retour à localhost" "$(sed -n 3p "$TMP/acces")" "localhost|0|1"
(
  ENV_FILE="$TMP/deploy/.env" INTERACTIF=0 MODE=internet
  maj_env "$ENV_FILE" SMTP_HOST ""
  configurer_acces
) >/dev/null 2>&1 && ko "Internet sans SMTP accepté" || ok "Internet sans SMTP refusé en mode non interactif"

echo "ouvrir_tunnel (faux docker compose)"
(
  ENV_FILE="$TMP/deploy/.env" ECHECS_AVANT_ADRESSE=2 LANCEMENTS=0
  sleep() { :; }
  # simule cloudflared : refusé deux fois par Cloudflare, puis une adresse
  compose() {
    case "$1" in
      up) LANCEMENTS=$((LANCEMENTS + 1)) ;;
      logs) if [ "$LANCEMENTS" -gt "$ECHECS_AVANT_ADRESSE" ]; then echo "tunnel-1 | INF |  https://essai-ok.trycloudflare.com  |"; else echo "tunnel-1 | failed to parse quick Tunnel ID: invalid UUID length: 0"; fi ;;
      ps) [ "$LANCEMENTS" -gt "$ECHECS_AVANT_ADRESSE" ] || echo arrete ;;
    esac
  }
  set -euo pipefail   # comme dans le script : « pas encore d'adresse » ne doit pas l'arrêter
  ouvrir_tunnel >/dev/null 2>&1
  set +e
  echo "$LANCEMENTS|$(valeur_env "$ENV_FILE" DOMAIN)"
  ECHECS_AVANT_ADRESSE=99 LANCEMENTS=0
  ( ouvrir_tunnel >/dev/null 2>&1 ) && echo accepte || echo refuse
) > "$TMP/tunnel" 2>&1
egal "nouvel essai quand Cloudflare refuse" "$(sed -n 1p "$TMP/tunnel")" "3|essai-ok.trycloudflare.com"
egal "abandon après trois refus" "$(sed -n 2p "$TMP/tunnel")" refuse

echo "fonctions appelées"
# toute fonction appelée dans le script y est définie (une suppression par erreur casse le démarrage)
manque=""
for f in $(grep -oE '^ *[a-z_]+( |$)' "$DEPOT/scripts/demarrer-local.sh" | tr -d ' ' | sort -u); do
  grep -qE "^ *$f\(\) \{" "$DEPOT/scripts/demarrer-local.sh" "$DEPOT/scripts/lib-image-ros.sh" && continue
  command -v "$f" >/dev/null 2>&1 || type "$f" >/dev/null 2>&1 || manque="$manque $f"
done
egal "aucune fonction manquante" "$manque" ""

echo "lire_options"
lire_options arreter --admin a@b.fr --non-interactif
egal "commande" "$COMMANDE" arreter
egal "admin" "$ADMIN" a@b.fr
( lire_options inconnu ) >/dev/null 2>&1 && ko "argument inconnu accepté" || ok "argument inconnu refusé"
lire_options --internet
egal "--internet" "$MODE" internet
lire_options --local
egal "--local" "$MODE" local

rm -rf "$TMP"
[ "$echecs" = 0 ] && echo "TOUS LES TESTS DU DÉMARRAGE LOCAL PASSENT" || { echo "$echecs échec(s)"; exit 1; }
