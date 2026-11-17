#!/usr/bin/env bash
# Construit dist/ : uniquement les fichiers a publier, plus le .htaccess.
# Aucun script, aucun etat de suivi, aucun cache n'y entre.
set -euo pipefail

ICI="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ICI/dist"

cd "$ICI"

for f in index.html matchs.json calendrier.ics suivi_handball.csv; do
  [ -f "$f" ] || { echo "manquant : $f (lancer suivi_handball.py d'abord)" >&2; exit 1; }
done

rm -rf "$DIST"
mkdir -p "$DIST"

cp index.html matchs.json calendrier.ics suivi_handball.csv "$DIST/"
cp -R logos "$DIST/logos"

# cadrage.json sert au rendu, pas a l'affichage : il reste cote code.
rm -f "$DIST/logos/cadrage.json"

cp deploiement/htaccess "$DIST/.htaccess"

echo "dist/ : $(du -sh "$DIST" | cut -f1), $(find "$DIST" -type f | wc -l | tr -d ' ') fichiers"
