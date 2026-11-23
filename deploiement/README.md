# Mise en ligne

Le site est servi par **Cloudflare Pages** :

| | |
|---|---|
| Adresse | **https://handball.belliere.fr** |
| Projet Pages | `handball-belliere` |
| Adresse technique | `https://handball-belliere.pages.dev` |
| Certificat | émis et renouvelé par Cloudflare (Google Trust Services) |
| Coût | 0 € — offre gratuite |

IONOS reste **registrar** et **zone DNS**. Il n'y héberge plus rien : la zone ne
contient qu'un `CNAME` vers Pages. Mail, SPF, DMARC et wildcard sont intacts.

## Ce qui part en ligne

| Fichier | Rôle | Taille |
|---|---|---|
| `index.html` | la page (style, onglets, données incluses) | 71 Ko |
| `calendrier.ics` | le flux à souscrire dans Outlook | 8 Ko |
| `matchs.json` | données brutes, utilisées par la page | 41 Ko |
| `suivi_handball.csv` | export tableur | 13 Ko |
| `logos/*.webp` | 19 logos de clubs | 136 Ko |
| `_headers` | en-têtes HTTP (type MIME du `.ics`, cache) | 1 Ko |

**280 Ko, 24 fichiers.** Aucune base de données : le site est entièrement
statique.

Ne partent jamais en ligne : les scripts `.py`, l'état de suivi
`.suivi_handball_etat.json`, le cache `ffhb_poules_index.json`.

## Architecture

```
GitHub Actions (toutes les 3 h, le samedi toutes les 30 min en journée,
        │        ou lancement manuel)
        │  python3 suivi_handball.py
        │  contrôle de cohérence       (échec = rien n'est publié)
        │  deploiement/construire.sh   -> dist/
        ▼
      dist/
        │  npx wrangler pages deploy
        ▼
  Cloudflare Pages  ──►  https://handball.belliere.fr
```

Rien ne tourne sur une machine personnelle : le Mac peut être éteint, la page se
met à jour quand même.

Coût : environ 1 min 30 par exécution, 8 exécutions par jour (plus 22 le samedi
après-midi quand une équipe joue). Le dépôt est public, donc les minutes Actions
sont illimitées.

## Planification

Deux déclencheurs indépendants, à 25 minutes d'écart :

| Heure UTC | Déclencheur | Fiabilité |
|---|---|---|
| `01:17`, `04:17`, … | `schedule` de GitHub Actions | irrégulière : des exécutions sautent sans prévenir |
| `01:42`, `04:42`, … | Worker Cloudflare `declencheur` | à l'heure dite |

Le Worker ne collecte rien : son `scheduled()` fait un seul appel à l'API
GitHub (`workflow_dispatch`) et s'arrête. Ce qui suit reste entièrement dans
Actions.

Le doublon est neutralisé par le job **`fraicheur`**, exécuté en premier : si
`matchs.json` en ligne a moins de **2 h**, le workflow s'arrête avant toute
collecte. Conséquence : le cron GitHub peut rester en secours, et un
déclenchement manuel accidentel ne relance rien. En cas de doute (site
injoignable), on collecte — un run de trop vaut mieux qu'une page figée.

### Le samedi après-midi

Les scores tombent en continu pendant les rencontres : trois heures d'attente
seraient visibles. Le Worker ajoute donc, **le samedi uniquement**, un passage
toutes les 30 minutes :

| Heure UTC | Heure de Paris | |
|---|---|---|
| `10:07`, `10:37`, … `20:37` | 11 h – 21 h 37 (hiver) | 12 h – 22 h 37 (été) |

Deux conditions pour que ce rythme serve à quelque chose :

- le job `fraicheur` abaisse son seuil de 2 h à **25 minutes** dans cette
  fenêtre (9 h → 21 h UTC, pour couvrir l'hiver comme l'été) ;
- il ne l'abaisse que **s'il y a un match ce jour-là** — un samedi sans
  rencontre garde le rythme normal. Conséquence : aucun passage inutile en
  juillet, ni le samedi matin.

Les minutes `:07` et `:37` évitent de doubler le cron de 3 h (`:42`). Ce rythme
n'existe que côté Cloudflare, qui part à l'heure dite ; le cron GitHub reste le
filet de sécurité. Si le jeton du Worker venait à expirer, on retomberait
simplement sur le rythme de 3 h.

Coût : 22 collectes de plus par samedi de compétition, soit environ 15 minutes
de runner. Le dépôt est public, les minutes Actions sont illimitées.

Pour forcer une collecte malgré tout : `Run workflow` → cocher **forcer**.

### Secrets du Worker

Une seule fois, dans `Workers & Pages` → `declencheur` → `Settings` →
`Variables and secrets` :

| Nom | Contenu |
|---|---|
| `GITHUB_TOKEN` | jeton GitHub **fine-grained**, dépôt `handball` uniquement, permission `Actions: Read and write`, expiration 1 an |
| `JETON_MANUEL` | facultatif, chaîne aléatoire protégeant `GET /declencher` |

Sans `GITHUB_TOKEN`, le cron tourne mais ne déclenche rien (visible dans
`Logs` du Worker). Sans `JETON_MANUEL`, le déclenchement manuel par URL reste
fermé : fermé par défaut plutôt qu'ouvert par accident.

Le jeton GitHub expire au bout d'un an : noter la date, sinon le cron cesse
silencieusement de fonctionner à l'échéance.


## Mise en route

### 1. Projet Pages

`Workers & Pages` → `Créer` → onglet **Pages** → **Upload assets**. Nom :
**`handball-belliere`** — il doit correspondre au `--project-name` du workflow.

Les adresses `*.pages.dev` sont uniques au monde : `handball` appartenait déjà à
un autre compte, d'où le suffixe. Si `handball-belliere` est pris à son tour,
choisir un autre nom et l'adapter **dans le workflow** et **dans le CNAME**.

Le script `pages/creer_projet.sh` fait la même chose par l'API :

```bash
export CF_TOKEN='cfut_...'
./deploiement/pages/creer_projet.sh
```

> **Ne pas confondre avec Workers.** Un Worker ne peut pas recevoir un CNAME
> venu d'un DNS externe : ses domaines personnalisés exigent que la zone soit
> chez Cloudflare. Pages, lui, accepte un sous-domaine rattaché par simple
> CNAME — c'est la seule différence qui compte ici.

### 2. Jeton d'API

`My Profile` → `API Tokens` → `Create Token` → **Custom token** :

| Champ | Valeur |
|---|---|
| Permissions | `Account` → **Cloudflare Pages** → **Edit** |
| Permissions | `Account` → **Workers Scripts** → **Edit** (déploiement du déclencheur) |
| Account Resources | ton compte |
| Zone Resources | laisser vide — le sous-domaine passe par un CNAME externe |
| TTL | sans expiration, ou 1 an |

La seconde permission s'ajoute en cliquant **+ Add more** sous le premier bloc
de permissions. La valeur du jeton ne change pas : inutile de le régénérer.

Depuis 2026 les jetons sont préfixés : `cfut_` (utilisateur) ou `cfat_` (compte),
53 caractères. Les anciens jetons de 40 caractères fonctionnent toujours.

### 3. Secrets du dépôt

`Settings` → `Secrets and variables` → `Actions` :

| Nom | Valeur |
|---|---|
| `CLOUDFLARE_API_TOKEN` | le jeton ci-dessus |
| `CLOUDFLARE_ACCOUNT_ID` | 32 caractères, dans l'URL du tableau de bord : `dash.cloudflare.com/<identifiant>` |

Le nom doit être exact : un secret mal orthographié n'est pas signalé, il est
simplement ignoré.

### 4. Domaine personnalisé

`Workers & Pages` → `handball-belliere` → `Custom domains` → `Set up a domain`
→ `handball.belliere.fr`.

**L'ordre est impératif** : créer le CNAME avant d'avoir déclaré le domaine
provoque une erreur 522 — le trafic arrive chez Pages sans domaine associé.

Puis, dans la zone DNS IONOS :

| Type | Nom | Valeur | TTL |
|---|---|---|---|
| `CNAME` | `handball` | `handball-belliere.pages.dev` | 300 pendant la bascule, 3600 ensuite |

Si la zone contient des enregistrements **CAA**, ils doivent autoriser
`pki.goog` et `letsencrypt.org`, sinon l'émission du certificat échoue.

### 5. Premier déploiement

`Actions` → `Collecte FFHandball` → `Run workflow`. Le journal doit finir par :

```
✨ Deployment complete! Take a peek over at https://handball-belliere.pages.dev
```

Le même run déploie le Worker `declencheur`. Son secret `GITHUB_TOKEN` se crée
**après** ce premier déploiement (voir *Planification*) : d'ici là, le cron
tourne à vide, sans conséquence.

## Vérifier

```bash
./verifier_publication.sh                      # seuil 4 h
curl -sI https://handball.belliere.fr/calendrier.ics | grep -i content-type
```

Attendu : `text/calendar; charset=utf-8`. Codes de sortie du script : `0` à jour,
`1` trop vieux, `2` inaccessible.

Contrôles ponctuels :

```bash
dig +short handball.belliere.fr CNAME          # doit renvoyer *.pages.dev
echo | openssl s_client -connect 188.114.96.2:443 \
  -servername handball.belliere.fr 2>/dev/null | grep -E 'subject=|issuer='
```

## Dépannage

| Symptôme | Cause | Geste |
|---|---|---|
| `522` sur le domaine | CNAME créé avant le domaine, ou projet sans déploiement | vérifier l'ordre ; lancer un run |
| `handshake failure` en HTTPS, `301` en HTTP | certificat pas encore émis | attendre 15–30 min, puis `Check status` dans `Custom domains` |
| `tlsv1 alert internal error` en local | cache DNS local pointant encore l'ancien hébergeur | `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` |
| `*.pages.dev` inaccessible depuis le bureau | filtrage Cisco Umbrella | tester en 4G / sur téléphone |
| Secrets « manquants » | nom mal orthographié | recréer avec le nom exact |
| Cron Cloudflare sans effet | `GITHUB_TOKEN` absent ou expiré dans le Worker | `Workers & Pages` → `declencheur` → `Logs` |
| Workflow refusé au lancement | données en ligne récentes (< 2 h) | c'est le garde-fou ; cocher **forcer** |
| Déploiement du Worker refusé | jeton sans `Workers Scripts: Edit` | compléter le jeton, valeur inchangée |

## Pourquoi Cloudflare et pas IONOS

IONOS ne peut pas servir de HTTPS sur `handball.belliere.fr` :

- le certificat wildcard inclus est installé sur un **autre** espace web — il ne
  suit pas le DNS ;
- un hébergement mutualisé **n'accepte aucun certificat tiers** : installer un
  certificat, c'est modifier la configuration du serveur au moment du handshake
  TLS, ce qui exige un accès root. Le sélecteur de domaine du panneau ne propose
  donc jamais `handball`, et un certificat payant de plus ne changerait rien.

Le registrar et l'émetteur du certificat sont indépendants : un hôte joint par
CNAME obtient son propre certificat, renouvelé sans intervention.

## Garde-fous

- **Collecte incomplète** (moins de 10 matchs, page anormalement petite, une
  équipe manquante) : le workflow échoue **avant** le déploiement, le site en
  ligne reste intact, GitHub envoie un e-mail.
- **Exécutions simultanées** : `concurrency` les sérialise.
- **Dépôt inactif** : GitHub désactive les workflows programmés après 60 jours
  sans activité — mais chaque collecte qui change une donnée crée un commit, le
  dépôt reste donc actif par construction.
- **Fichiers obsolètes** : aucun miroir n'est maintenu côté serveur, chaque
  déploiement Pages remplace l'ensemble.

## Outils du dossier

| Fichier | Rôle |
|---|---|
| `construire.sh` | fabrique `dist/` : uniquement les fichiers publics + `_headers` |
| `pages/_headers` | en-têtes HTTP servis par Pages, copié dans `dist/` |
| `pages/creer_projet.sh` | crée le projet Pages par l'API et rappelle les secrets à renseigner |
| `worker/declencheur.js` | Worker appelé par le cron Cloudflare, déclenche le workflow |
| `worker/wrangler.toml` | nom, horaires du cron, déploiement du Worker |
