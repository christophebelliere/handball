#!/usr/bin/env bash
# Diagnostic de l'hebergement IONOS : a lancer une fois en SSH, en lecture seule.
#   ssh UTILISATEUR@homeXXXXXXX.1and1-data.host
#   bash diagnostic.sh
# puis me copier la sortie.
# Aucune modification, aucun fichier cree.

echo "===== systeme ====="
uname -a

echo
echo "===== python ====="
for p in python3 python3.11 python3.9 python; do
  chemin="$(command -v "$p" 2>/dev/null)"
  [ -n "$chemin" ] && { echo "$p -> $chemin"; "$p" -V 2>&1; }
done
[ -z "$(command -v python3 2>/dev/null)" ] && echo "python3 : ABSENT"

echo
echo "===== php ====="
if command -v php >/dev/null 2>&1; then
  php -v | head -1
else
  echo "php : absent en ligne de commande"
fi

echo
echo "===== outils ====="
for o in rsync curl wget tar crontab unzip; do
  printf "%-9s %s\n" "$o" "$(command -v "$o" 2>/dev/null || echo absent)"
done

echo
echo "===== crontab ====="
crontab -l 2>&1 | head -20

echo
echo "===== espace disque ====="
df -h . 2>/dev/null | tail -2

echo
echo "===== dossier courant ====="
pwd
ls -la | head -15

echo
echo "===== reseau sortant ====="
if command -v curl >/dev/null 2>&1; then
  curl -s -o /dev/null -w "www.ffhandball.fr  HTTP %{http_code}  %{time_total}s\n" --max-time 20 https://www.ffhandball.fr/
  curl -s -o /dev/null -w "api.handapi.fr     HTTP %{http_code}  %{time_total}s\n" --max-time 20 https://api.handapi.fr/health
  curl -s -o /dev/null -w "media-logos-clubs  HTTP %{http_code}\n" --max-time 20 https://media-logos-clubs.ffhandball.fr/64/2024-08-21-58a11b0c-1d13-4285-a9f6-899cae5a14e2.webp
else
  echo "curl absent : test reseau impossible"
fi

echo
echo "===== fin ====="
