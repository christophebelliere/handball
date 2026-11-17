#!/usr/bin/env bash
# Publie dist/ sur l'hebergement IONOS, par SSH.
#
#   IONOS_HOST=home12345678.1and1-data.host \
#   IONOS_USER=a12345678 \
#   IONOS_DIR=htdocs \
#   ./deploiement/publier.sh
#
# Options :
#   IONOS_PORT=22            port SSH (voir "Details techniques" dans le panel)
#   IONOS_KEY=~/.ssh/ionos   cle privee a utiliser
#   IONOS_DIR=handball       sous-dossier de la racine web (defaut : htdocs)
#   IONOS_MIROIR=1           avec des fichiers distants en trop a supprimer
#
# Le transfert se fait par tar+ssh : pas besoin que rsync soit installe en face,
# et l'envoi reste en un seul flux compresse.
set -euo pipefail

ICI="$(cd "$(dirname "$0")/.." && pwd)"

: "${IONOS_HOST:?Definir IONOS_HOST (ex. home12345678.1and1-data.host)}"
: "${IONOS_USER:?Definir IONOS_USER (utilisateur principal FTP = utilisateur SSH)}"

CIBLE="${IONOS_DIR:-htdocs}"
PORT="${IONOS_PORT:-22}"
KEY_ARG=()
[ -n "${IONOS_KEY:-}" ] && KEY_ARG=(-i "$IONOS_KEY")

SSH=(ssh -p "$PORT" "${KEY_ARG[@]}" "$IONOS_USER@$IONOS_HOST")

"$ICI/deploiement/construire.sh"

echo "== Envoi de $(find "$ICI/dist" -type f | wc -l | tr -d ' ') fichiers vers $IONOS_USER@$IONOS_HOST:$CIBLE =="

if [ "${IONOS_MIROIR:-0}" = "1" ]; then
  # Le miroir ne s'applique QU'A $CIBLE : ne jamais le pointer sur la racine web
  # si elle contient autre chose que ce site.
  "${SSH[@]}" "mkdir -p '$CIBLE' && find '$CIBLE' -mindepth 1 -delete"
fi

tar -czf - -C "$ICI/dist" . | "${SSH[@]}" "mkdir -p '$CIBLE' && tar -xzf - -C '$CIBLE'"

echo "== Verifications distantes =="
"${SSH[@]}" "ls -l '$CIBLE/index.html' '$CIBLE/calendrier.ics' ; ls '$CIBLE/logos' | wc -l | xargs echo 'logos:'"
echo "OK"
