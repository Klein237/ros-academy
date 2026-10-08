#!/usr/bin/env bash
# Tests des fonctions de scripts/installer-serveur.sh (sans rien installer).
set -euo pipefail
DEPOT=$(cd "$(dirname "$0")/../.." && pwd)
INSTALLER_TEST=1 source "$DEPOT/scripts/installer-serveur.sh"
[ "$RACINE" = "$DEPOT" ] || { echo "RACINE mal calculée : $RACINE"; exit 1; }
set +e
echecs=0
ok() { printf '  ✔ %s\n' "$1"; }
ko() { printf '  ✘ %s\n' "$1"; echecs=$((echecs + 1)); }
egal() { if [ "$2" = "$3" ]; then ok "$1"; else ko "$1 : attendu « $3 », obtenu « $2 »"; fi; }

echo "sessions_conseillees"
egal "4 vCPU / 16 Go" "$(sessions_conseillees 16 4)" 8
egal "8 vCPU / 32 Go" "$(sessions_conseillees 32 8)" 18
egal "16 vCPU / 64 Go" "$(sessions_conseillees 64 16)" 40
egal "2 vCPU / 64 Go (limité par le processeur)" "$(sessions_conseillees 64 2)" 8
egal "minimum 2" "$(sessions_conseillees 7 1)" 2

echo "generer_env"
TMP=$(mktemp -d)
DOMAINE=academy.exemple.fr ADMIN="moi@exemple.fr" SESSIONS=18 SMTP_HOST=smtp.gmail.com SMTP_PORT=587
SMTP_USER=moi@gmail.com SMTP_PASSWORD='abcd efgh|&\ijkl' SMTP_FROM="RoboForge <moi@gmail.com>"
EXTRA_ENV=("VEILLE_SEUIL_DISQUE=1")
EDITEUR_NOM="Klein & Fils" EDITEUR_ADRESSE="1 rue de la Paix, 75002 Paris" HEBERGEUR="Hetzner Online GmbH"
generer_env "$RACINE/deploy/.env.example" "$TMP/.env"
E="$TMP/.env"
egal "DOMAIN" "$(valeur_env "$E" DOMAIN)" academy.exemple.fr
egal "ADMIN_EMAILS" "$(valeur_env "$E" ADMIN_EMAILS)" moi@exemple.fr
egal "ACTIVE_SERVER_LIMIT" "$(valeur_env "$E" ACTIVE_SERVER_LIMIT)" 18
egal "mot de passe SMTP avec caractères spéciaux" "$(valeur_env "$E" SMTP_PASSWORD)" 'abcd efgh|&\ijkl'
egal "SMTP_FROM" "$(valeur_env "$E" SMTP_FROM)" "RoboForge <moi@gmail.com>"
egal "lien à l'écran désactivé" "$(valeur_env "$E" CONNEXION_LIEN_A_L_ECRAN)" 0
egal "dossiers à quota" "$(valeur_env "$E" LAB_HOMES_DIR)" /srv/ros-academy/homes
egal "override compose" "$(valeur_env "$E" COMPOSE_FILE)" docker-compose.yml:docker-compose.quotas.yml
egal "éditeur (caractère &)" "$(valeur_env "$E" EDITEUR_NOM)" "Klein & Fils"
egal "adresse de l'éditeur" "$(valeur_env "$E" EDITEUR_ADRESSE)" "1 rue de la Paix, 75002 Paris"
egal "hébergeur" "$(valeur_env "$E" HEBERGEUR)" "Hetzner Online GmbH"
egal "--env ajouté" "$(valeur_env "$E" VEILLE_SEUIL_DISQUE)" 1
egal "une seule ligne VEILLE_SEUIL_DISQUE effective (la dernière)" "$(grep -c '^VEILLE_SEUIL_DISQUE=' "$E")" 2
for cle in JWT_SECRET JUPYTERHUB_CRYPT_KEY HUB_ADMIN_TOKEN POSTGRES_PASSWORD GRAFANA_ADMIN_PASSWORD; do
  v=$(valeur_env "$E" "$cle")
  if [[ $v =~ ^[0-9a-f]{64}$ ]]; then ok "$cle généré"; else ko "$cle : « $v »"; fi
done
[ "$(valeur_env "$E" JWT_SECRET)" != "$(valeur_env "$E" HUB_ADMIN_TOKEN)" ] && ok "secrets distincts" || ko "secrets identiques"
egal "droits du fichier" "$(stat -c %a "$E")" 600
grep -q '^[A-Z_]*=remplacer' "$E" && ko "valeur d'exemple restante" || ok "aucune valeur d'exemple"
# deploy/.env généré : docker compose le lit sans erreur
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  if (cd "$RACINE/deploy" && docker compose --env-file "$E" config --quiet 2>"$TMP/compose.err"); then
    ok "docker compose config"
  else
    ko "docker compose config : $(head -3 "$TMP/compose.err")"
  fi
fi

echo "lire_options"
EXTRA_ENV=()
lire_options --domaine a.fr --admin x@a.fr --sans-smtp --sessions 5 --env A=1 --env B_2=x=y --non-interactif
egal "domaine" "$DOMAINE" a.fr
egal "sessions" "$SESSIONS" 5
egal "sans smtp" "$SANS_SMTP" 1
egal "non interactif" "$INTERACTIF" 0
egal "--env répété" "${EXTRA_ENV[*]}" "A=1 B_2=x=y"
( lire_options --env "pas bon" ) >/dev/null 2>&1 && ko "--env invalide accepté" || ok "--env invalide refusé"
( lire_options --inconnue ) >/dev/null 2>&1 && ko "option inconnue acceptée" || ok "option inconnue refusée"

rm -rf "$TMP"
[ "$echecs" = 0 ] && echo "TOUS LES TESTS DE L'INSTALLEUR PASSENT" || { echo "$echecs échec(s)"; exit 1; }
