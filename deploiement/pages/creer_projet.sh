#!/usr/bin/env bash
# Cree (ou retrouve) le projet Cloudflare Pages et affiche son adresse publique.
#
#   export CF_TOKEN='v1.0-...'      # jeton « Account > Cloudflare Pages > Edit »
#   ./deploiement/pages/creer_projet.sh
#
# CF_ACCOUNT est facultatif : s'il est absent et que le jeton ne voit qu'un
# compte, le script le deduit tout seul. Le jeton ne passe ni en argument, ni
# dans un fichier : il reste dans l'environnement du shell.
set -euo pipefail

NOM="${PROJET:-handball-belliere}"
API="https://api.cloudflare.com/client/v4"

# Pas d apostrophe dans ce message : bash 3.2 (celui de macOS) se perd sur les
# guillemets simples imbriques dans ${VAR:?message}.
: "${CF_TOKEN:?CF_TOKEN manquant - lancer export CF_TOKEN=<jeton>}"

# Cloudflare a deux formats : l ancien (40 caracteres sans prefixe) et le
# nouveau, prefixe et scannable (cfut_ pour un jeton utilisateur, cfat_ pour un
# jeton de compte, 53 caracteres au total). Les deux sont acceptes ici.
CF_TOKEN="${CF_TOKEN//[[:space:]]/}"
case "$CF_TOKEN" in
  *ton_jeton*|*votre_jeton*|*xxx*|v1.0-*)
    echo "CF_TOKEN contient encore un texte d exemple (${CF_TOKEN:0:12}...)." >&2
    echo "Recopie le vrai jeton depuis dash.cloudflare.com/profile/api-tokens." >&2
    exit 1 ;;
esac
if ! [[ "$CF_TOKEN" =~ ^cf(k|ut|at)_[A-Za-z0-9_-]{40,}$ || "$CF_TOKEN" =~ ^[A-Za-z0-9_-]{40}$ ]]; then
  echo "CF_TOKEN n a pas la forme d un jeton Cloudflare (${#CF_TOKEN} caracteres)." >&2
  echo "Attendu : cfut_... (53) ou 40 caracteres sans prefixe." >&2
  exit 1
fi

api() {  # methode, chemin, [corps JSON]
  local methode="$1" chemin="$2" corps="${3:-}"
  if [ -n "$corps" ]; then
    curl -sS -X "$methode" "$API$chemin" \
      -H "Authorization: Bearer $CF_TOKEN" \
      -H "Content-Type: application/json" \
      --data "$corps"
  else
    curl -sS -X "$methode" "$API$chemin" \
      -H "Authorization: Bearer $CF_TOKEN"
  fi
}

# ------------------------------------------------------ 1. validite du jeton
# Cet endpoint ne demande aucune permission : il repond « active » pour tout
# jeton vivant, ce qui distingue tout de suite « jeton mort » de « permission
# Pages manquante ».
printf 'Jeton    : '
api GET /user/tokens/verify | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("success"):
    e = (d.get("errors") or [{}])[0]
    sys.exit("refuse (%s) : %s" % (e.get("code"), e.get("message")))
print("valide, statut %s" % (d.get("result") or {}).get("status", "inconnu"))
'

# ------------------------------------------------------------ 2. le compte
if [ -z "${CF_ACCOUNT:-}" ]; then
  echo "Recherche du compte..."
  reponse=$(api GET /accounts)
  if ! CF_ACCOUNT=$(printf '%s' "$reponse" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("success"):
    e = (d.get("errors") or [{}])[0]
    sys.exit("Liste des comptes refusee (%s) : %s"
             % (e.get("code"), e.get("message")))
comptes = d.get("result") or []
if len(comptes) == 1:
    print(comptes[0]["id"])
elif not comptes:
    sys.exit("Aucun compte visible : la ressource Account Resources du jeton est vide.")
else:
    print("Plusieurs comptes accessibles :", file=sys.stderr)
    for c in comptes:
        print("  %s  %s" % (c["id"], c["name"]), file=sys.stderr)
    print("Relance avec : export CF_ACCOUNT=<id>", file=sys.stderr)
    sys.exit(2)
'); then
    echo
    echo "Le jeton fonctionne, mais l identifiant de compte n a pas pu etre lu." >&2
    echo "Prends-le dans l URL du tableau de bord (dash.cloudflare.com/<id>) puis :" >&2
    echo "  export CF_ACCOUNT=<les 32 caracteres>" >&2
    exit 1
  fi
fi

echo "Compte   : $CF_ACCOUNT"

# ------------------------------------------------ 3. le projet existe-t-il ?
existant=$(api GET "/accounts/$CF_ACCOUNT/pages/projects/$NOM" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("oui" if d.get("success") and d.get("result") else "non")
' 2>/dev/null || echo non)

if [ "$existant" = "oui" ]; then
  echo "Projet   : $NOM (deja present, rien a creer)"
else
  echo "Projet   : $NOM (creation)"
  api POST "/accounts/$CF_ACCOUNT/pages/projects" \
    "{\"name\":\"$NOM\",\"production_branch\":\"main\"}" \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("success"):
    e = (d.get("errors") or [{}])[0]
    sys.exit("Creation refusee (%s) : %s" % (e.get("code"), e.get("message")))
r = d["result"]
print("           cree, branche de production : %s" % r.get("production_branch"))
'
fi

# ------------------------------------------------------- 4. l'adresse finale
api GET "/accounts/$CF_ACCOUNT/pages/projects/$NOM" | CF_ACCOUNT="$CF_ACCOUNT" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
if not d.get("success"):
    e = (d.get("errors") or [{}])[0]
    sys.exit("Lecture du projet impossible (%s) : %s"
             % (e.get("code"), e.get("message")))
r = d["result"]
sous = r.get("subdomain") or (r.get("name", "") + ".pages.dev")
compte = r.get("account_id") or os.environ["CF_ACCOUNT"]
print()
print("Adresse  : https://%s" % sous)
print("Depots   : %s" % ("aucun pour le moment, le workflow remplira le site"
                         if not r.get("latest_deployment")
                         else "au moins un deja en ligne"))
print()
print("Secrets a renseigner sur GitHub :")
print("  CLOUDFLARE_API_TOKEN   = le jeton cfut_... (ne pas recopier ici)")
print("  CLOUDFLARE_ACCOUNT_ID  = %s" % compte)
'
