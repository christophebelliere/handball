#!/usr/bin/env bash
# Verifie que le site publie bien des donnees fraiches.
#
#   ./verifier_publication.sh                      # seuil 4 h
#   ./verifier_publication.sh https://autre.site   # autre site
#   SEUIL_HEURES=6 ./verifier_publication.sh       # seuil personnalise
#
# Codes de sortie : 0 = a jour, 1 = trop vieux, 2 = inaccessible ou incomplet.
# Ne demande aucun identifiant : tout se lit sur le site public.

set -uo pipefail

SITE="${1:-https://handball.belliere.fr}"
SEUIL="${SEUIL_HEURES:-4}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "Site : $SITE"

# HTTPS d'abord, HTTP en secours (le certificat a pu ne pas encore etre emis).
if ! curl -fsS --max-time 20 "$SITE/matchs.json" -o "$TMP" 2>/dev/null; then
  if ! curl -fsS --max-time 20 "${SITE/https:/http:}/matchs.json" -o "$TMP" 2>/dev/null; then
    echo "ECHEC : matchs.json inaccessible" >&2
    exit 2
  fi
fi

python3 - "$TMP" "$SEUIL" <<'PY'
import json
import sys
from datetime import datetime, timezone

chemin, seuil = sys.argv[1], float(sys.argv[2])

try:
    data = json.load(open(chemin, encoding="utf-8"))
except Exception as erreur:
    sys.exit("ECHEC : matchs.json illisible (%s)" % erreur)

genere = data.get("genere_le")
if not genere:
    sys.exit("ECHEC : champ genere_le absent")

try:
    moment = datetime.fromisoformat(genere)
except ValueError:
    sys.exit("ECHEC : genere_le illisible (%r)" % genere)
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=timezone.utc)

age = (datetime.now(timezone.utc) - moment).total_seconds() / 3600
equipes = data.get("equipes", [])
matchs = sum(len(e.get("matchs", [])) for e in equipes)

print("Publie le   : %s UTC" % moment.strftime("%d/%m/%Y %H:%M"))
print("Il y a      : %.1f h" % age)
print("Equipes     : %d   Matchs : %d" % (len(equipes), matchs))

if len(equipes) != 3 or matchs < 10:
    print("ECHEC : donnees incompletes, la collecte a echoue")
    sys.exit(2)

if age > seuil:
    print("ANOMALIE : aucune mise a jour depuis plus de %g h." % seuil)
    print("           Verifier Actions -> Collecte FFHandball dans le depot GitHub.")
    sys.exit(1)

print("OK : la publication est a jour")
PY
