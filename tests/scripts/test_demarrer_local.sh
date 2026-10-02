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

echo "lire_options"
lire_options arreter --admin a@b.fr --non-interactif
egal "commande" "$COMMANDE" arreter
egal "admin" "$ADMIN" a@b.fr
( lire_options inconnu ) >/dev/null 2>&1 && ko "argument inconnu accepté" || ok "argument inconnu refusé"

rm -rf "$TMP"
[ "$echecs" = 0 ] && echo "TOUS LES TESTS DU DÉMARRAGE LOCAL PASSENT" || { echo "$echecs échec(s)"; exit 1; }
