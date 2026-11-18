# Mise en ligne sur IONOS (SFTP, sans SSH)

## Ce qui part en ligne

| Fichier | Rôle | Taille |
|---|---|---|
| `index.html` | la page (style, onglets, données incluses) | 71 Ko |
| `calendrier.ics` | le flux à souscrire dans Outlook | 9 Ko |
| `matchs.json` | données brutes, utilisées par la page | 41 Ko |
| `suivi_handball.csv` | export tableur | 13 Ko |
| `logos/*.webp` | 19 logos de clubs | 136 Ko |
| `.htaccess` | type MIME du `.ics`, cache, compression | 2 Ko |

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
   SFTP  ──────────────►  IONOS  ──►  https://handball.<domaine>.fr
```

Rien ne tourne sur IONOS à part Apache, et rien ne dépend de la maison : le Mac
peut être éteint, la page se met à jour quand même.

Coût : environ 1 min 30 par exécution, 8 exécutions par jour, soit ~360 minutes
par mois sur les 2000 offertes aux dépôts privés.

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

### 3. Sous-domaine et certificat

Dans l'espace client IONOS : `Domaines & SSL` → le domaine → créer le
sous-domaine `handball` (ou celui qui convient). IONOS crée alors un dossier
correspondant dans l'espace Web — c'est la valeur de `IONOS_SFTP_DIR`.

Le certificat SSL est inclus : une fois le sous-domaine actif, IONOS émet le
certificat automatiquement (compter quelques minutes à quelques heures). À ce
moment-là, décommenter le bloc `https` à la fin de `deploiement/htaccess` pour
forcer la redirection.

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

Le site en ligne : **https://handball.belliere.fr** (le HTTP fonctionne
immédiatement ; le certificat du sous-domaine est émis par IONOS avec un peu de
retard, d'où le bloc `https` encore commenté dans `deploiement/htaccess`).

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
| `construire.sh` | fabrique `dist/` : uniquement les fichiers publics + `.htaccess` |
| `publier.sh` | envoi manuel par SSH (`tar` + `ssh`) — pour une offre avec accès Shell |
| `collecter.sh` | collecte côté serveur avec verrou et journal borné — variante crontab |
| `diagnostic.sh` | à lancer en SSH : Python, PHP, crontab, réseau sortant |
| `htaccess` | configuration Apache copiée dans `dist/` sous le nom `.htaccess` |
