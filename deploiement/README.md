# Mise en ligne : Cloudflare Pages, et IONOS en transition

Le site est publié à **deux endroits** pendant la bascule :

| Destination | Adresse | Rôle |
|---|---|---|
| Cloudflare Pages | `https://handball.pages.dev`, puis `https://handball.belliere.fr` | **cible** : HTTPS émis et renouvelé automatiquement |
| IONOS (SFTP) | `http://handball.belliere.fr` | secours, retiré après validation |

IONOS reste le **registrar** et la **zone DNS** : on n'y ajoute qu'un
enregistrement CNAME. Mail, SPF, DMARC et certificat wildcard ne bougent pas.

## Ce qui part en ligne

| Fichier | Rôle | Taille |
|---|---|---|
| `index.html` | la page (style, onglets, données incluses) | 71 Ko |
| `calendrier.ics` | le flux à souscrire dans Outlook | 9 Ko |
| `matchs.json` | données brutes, utilisées par la page | 41 Ko |
| `suivi_handball.csv` | export tableur | 13 Ko |
| `logos/*.webp` | 19 logos de clubs | 136 Ko |
| `_headers` | en-têtes HTTP pour Pages (type MIME du `.ics`, cache) | 1 Ko |
| `.htaccess` | équivalent Apache, ajouté uniquement pour l'envoi IONOS | 2 Ko |

**280 Ko, 24 fichiers.** Aucune base de données n'est nécessaire : le site est
entièrement statique.

Ne partent jamais en ligne : les scripts `.py`, l'état de suivi
`.suivi_handball_etat.json`, le cache `ffhb_poules_index.json`.

## Contraintes IONOS (aide officielle, novembre 2026)

| Moyen | Ce qu'il permet | Verdict |
|---|---|---|
| Tâches cron du panel | appel **HTTP GET** uniquement, intervalle quotidien / hebdomadaire / mensuel, **60 s maximum** | inutilisable : ni 3 h, ni 20-40 s de collecte |
| Crontab serveur | fréquence libre, `MAILTO` | réservé aux offres avec accès Shell |
| **SFTP** | dépôt de fichiers, comptes dédiés, clés SSH acceptées | **ce qui est disponible ici** |
| root, service permanent | non | sans objet |

## Architecture retenue

```
GitHub Actions (toutes les 3 h)
        │  python3 suivi_handball.py
        │  contrôle de cohérence
        │  deploiement/construire.sh  -> dist/
        ▼
     dist/
        ├── wrangler pages deploy ──►  Cloudflare Pages  ──►  https://handball.belliere.fr
        └── SFTP ───────────────────►  IONOS (secours)   ──►  http://handball.belliere.fr
```

Rien ne tourne sur IONOS à part Apache, et rien ne dépend de la maison : le Mac
peut être éteint, la page se met à jour quand même.

Coût : environ 1 min 30 par exécution, 8 exécutions par jour. Le dépôt est
public, donc les minutes Actions sont illimitées ; Pages et Cloudflare sont sur
l'offre gratuite.

## Bascule vers Cloudflare Pages

### 1. Projet Pages

Tableau de bord → `Workers & Pages` → `Créer` → `Pages` → **Upload assets**.
Nom du projet : **`handball`** — il doit correspondre au `--project-name` du
workflow. À l'écran suivant, ne rien téléverser : le premier envoi automatique
remplira le site.

Équivalent en ligne de commande :

```bash
npx wrangler@4 pages project create handball --production-branch=main
```

Si `handball.pages.dev` est déjà pris par quelqu'un d'autre, choisir un autre
nom, puis adapter `--project-name` dans le workflow **et** la cible du CNAME.

### 2. Jeton d'API

`My Profile` → `API Tokens` → `Create Token` → **Custom token** :

| Champ | Valeur |
|---|---|
| Permissions | `Account` → **Cloudflare Pages** → **Edit** |
| Account Resources | ton compte |
| Zone Resources | laisser vide — inutile, le sous-domaine passe par un CNAME |
| TTL | sans expiration, ou 1 an |

### 3. Secrets du dépôt

`Settings` → `Secrets and variables` → `Actions` :

| Nom | Valeur |
|---|---|
| `CLOUDFLARE_API_TOKEN` | le jeton ci-dessus |
| `CLOUDFLARE_ACCOUNT_ID` | identifiant à 32 caractères, visible dans l'URL du tableau de bord : `dash.cloudflare.com/<identifiant>` |

### 4. Premier déploiement

`Actions` → `Collecte FFHandball` → `Run workflow`. Le journal doit finir par une
ligne du type :

```
✨ Deployment complete! Take a peek over at https://handball.pages.dev
```

Le site est alors consultable **en HTTPS**, sans avoir touché au DNS. C'est le
moment de tout vérifier :

```bash
./verifier_publication.sh https://handball.pages.dev
curl -sI https://handball.pages.dev/calendrier.ics | grep -i content-type
```

Attendu : `content-type: text/calendar; charset=utf-8`.

### 5. Domaine personnalisé

`Workers & Pages` → projet `handball` → `Custom domains` → `Set up a domain`
→ **`handball.belliere.fr`**.

**L'ordre est impératif** : créer le CNAME avant d'avoir déclaré le domaine
provoque une erreur 522, le trafic arrivant chez Pages sans domaine associé.

Pages indique alors la cible à utiliser. Chez IONOS, dans la zone DNS du
domaine :

| Type | Nom | Valeur | TTL |
|---|---|---|---|
| `CNAME` | `handball` | `handball.pages.dev` | par défaut |

Le statut passe à **Active** en quelques minutes et Cloudflare émet le
certificat de lui-même. Rien à installer, rien à renouveler.

Un point à contrôler avant : si la zone contient des enregistrements **CAA**,
ils doivent autoriser `letsencrypt.org`, `pki.goog` et `ssl.com`, sinon
l'émission échoue.

### 6. Après validation

1. Retirer `continue-on-error: true` de l'étape « Déploiement Cloudflare Pages ».
2. Supprimer l'étape « Envoi SFTP » et les secrets `IONOS_SFTP_*`.
3. `deploiement/htaccess` devient inutile et peut être supprimé.

Retour arrière à tout moment : remettre l'ancien CNAME chez IONOS, le site
repart sur IONOS, `.htaccess` toujours en place.

## Mise en route

### 1. Dépôt GitHub

Créer un dépôt **privé** vide, par exemple `suivi-handball`, puis :

```bash
cd "API Tests"
git remote add origin git@github.com:UTILISATEUR/suivi-handball.git
git push -u origin main
```

### 2. Secrets du dépôt

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`.

| Nom | Valeur |
|---|---|
| `IONOS_SFTP_HOST` | hôte indiqué dans « Détails techniques », du type `home12345678.1and1-data.host` |
| `IONOS_SFTP_USER` | utilisateur principal FTP (le même que pour SSH) |
| `IONOS_SFTP_PASS` | son mot de passe |
| `IONOS_SFTP_DIR` | dossier du sous-domaine, par exemple `/handball.mondomaine.fr` |

Le mot de passe n'est jamais interpolé dans une commande shell : il est lu
depuis la variable d'environnement par une bibliothèque SFTP Python
(`paramiko`), qui gère elle-même l'authentification. Un mot de passe contenant
espaces, guillemets ou `$` ne pose donc aucun problème.

Deux précautions prises par le workflow :

- `IONOS_SFTP_DIR` est nettoyé des espaces et retours à la ligne parasites
  (fréquents lors d'un copier-coller), et `/` seul est refusé — écrire à la
  racine du compte FTP serait une erreur coûteuse.
- **Le dossier cible doit déjà exister.** Il n'y a volontairement pas de
  `mkdir -p` : si le chemin est faux, le job échoue avec un message explicite
  plutôt que de créer un dossier fantôme que le serveur web ne sert pas.

### 3. Sous-domaine et certificat — état des lieux

Dans l'espace client IONOS : `Domaines & SSL` → le domaine → sous-domaine
`handball`. IONOS crée un dossier correspondant dans l'espace Web — c'est la
valeur de `IONOS_SFTP_DIR`. Le HTTP fonctionne immédiatement.

**Le HTTPS, en revanche, est hors de portée chez IONOS :**

- le certificat wildcard inclus est installé sur un **autre** espace web — il ne
  suit pas le DNS ;
- un hébergement mutualisé **n'accepte aucun certificat tiers** : installer un
  certificat, c'est modifier la configuration du serveur au moment du handshake
  TLS, ce qui exige un accès root. Le sélecteur de domaine du panneau ne propose
  donc jamais `handball`, et un certificat payant de plus ne changerait rien.

C'est la raison du passage à Cloudflare Pages, qui gère le certificat à la place
d'IONOS. Le bloc `https` de `deploiement/htaccess` reste commenté : sur IONOS il
n'y aura jamais de HTTPS à forcer.

### 4. Premier envoi

`Actions` → `Collecte FFHandball` → `Run workflow`. L'étape d'envoi doit
afficher :

```
Connecte a homeXXXXXXX.1and1-data.host
24 fichier(s) envoye(s) vers homeXXXXXXX.1and1-data.host:/handball
index.html distant : 7xxxx octets
```

puis `Aucun changement de données` ou un commit `Etat de suivi … UTC`.

Vérifier ensuite :

- `https://handball.<domaine>.fr/` affiche la page
- les logos se chargent (dossier `logos/` bien transféré)
- `curl -sI https://handball.<domaine>.fr/calendrier.ics` renvoie
  `Content-Type: text/calendar`
- l'URL du `.ics` s'abonne correctement dans Outlook

### 5. Collecte automatique

Le planificateur est **actif** : `.github/workflows/collecte.yml` déclenche une
collecte toutes les 3 h (`17 1,4,7,10,13,16,19,22 * * *`, en UTC) et
`workflow_dispatch` reste disponible pour un lancement manuel.

Le site en ligne : **http://handball.belliere.fr** tant que la bascule n'est pas
faite, puis **https://handball.belliere.fr** servi par Cloudflare Pages.

Penser à `Settings` → `Actions` → `General` → **Workflow permissions** =
*Read and write* : sans cela le commit de `.suivi_handball_etat.json` échoue en
fin de workflow.

## Garde-fous en place

- **Collecte incomplète** (moins de 10 matchs, page anormalement petite, une
  équipe manquante) : le workflow échoue **avant** l'envoi, le site en ligne
  reste intact, et GitHub envoie un e-mail d'échec.
- **Exécutions simultanées** : `concurrency` les sérialise.
- **Dépôt inactif** : GitHub désactive les workflows programmés après 60 jours
  sans activité, mais chaque collecte qui change une donnée crée un commit —
  le dépôt reste actif par construction.
- **Fichiers obsolètes** : le miroir n'utilise pas `--delete`. Un logo renommé
  laisse un fichier orphelin, sans effet sur la page.

## Variantes écartées

| Variante | Pourquoi |
|---|---|
| Crontab IONOS | pas d'accès Shell sur cette offre |
| Cron du panel | HTTP GET seulement, une fois par jour, 60 s maximum |
| Mac + `launchd` + SFTP | dépend du Mac allumé ; `deploiement/publier.sh` reste utilisable pour un envoi manuel |

## Outils du dossier

| Script | Rôle |
|---|---|
| `construire.sh` | fabrique `dist/` : uniquement les fichiers publics + `_headers` |
| `publier.sh` | envoi manuel par SSH (`tar` + `ssh`) — pour une offre avec accès Shell |
| `collecter.sh` | collecte côté serveur avec verrou et journal borné — variante crontab |
| `diagnostic.sh` | à lancer en SSH : Python, PHP, crontab, réseau sortant |
| `pages/_headers` | en-têtes HTTP pour Cloudflare Pages, copié dans `dist/` |
| `htaccess` | configuration Apache équivalente, ajoutée seulement pour l'envoi IONOS |
