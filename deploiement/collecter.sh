#!/usr/bin/env bash
# Collecte quotidienne/hebdomadaire cote serveur (a appeler par crontab).
#
#   cd ~/suivi && ./collecter.sh
#
# Ecrit la page, le calendrier, le json, le csv et les logos dans RACINE_WEB ;
# le code et l'etat de suivi restent dans ~/suivi, hors du domaine public.
set -euo pipefail

SUIVI="$(cd "$(dirname "$0")/.." && pwd)"
RACINE_WEB="${RACINE_WEB:-$HOME/htdocs}"
PYTHON="${PYTHON:-python3}"
JOURNAL="${JOURNAL:-$SUIVI/collecte.log}"

cd "$SUIVI"

# Un seul run a la fois : deux collectes simultanees ecraseraient les fichiers
# en cours d'ecriture.
exec 9>"$SUIVI/.collecte.lock"
if ! flock -n 9 2>/dev/null; then
  echo "$(date '+%F %T') deja en cours, abandon" >>"$JOURNAL"
  exit 0
fi

horodatage="$(date '+%F %T')"
SUIVI_SORTIE="$RACINE_WEB" "$PYTHON" "$SUIVI/suivi_handball.py" >>"$JOURNAL" 2>&1
code=$?

# Le journal ne doit pas grossir sans fin sur un espace de 50 Mo.
tail -n 2000 "$JOURNAL" >"$JOURNAL.tmp" && mv "$JOURNAL.tmp" "$JOURNAL"

echo "$horodatage fin (code $code)" >>"$JOURNAL"
exit "$code"
