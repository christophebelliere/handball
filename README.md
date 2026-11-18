# Suivi handball — Bonsecours / Belbeuf

Page web, flux calendrier `.ics` et classements pour trois équipes, alimentés
par les données officielles de [ffhandball.fr](https://www.ffhandball.fr).

- `index.html` — page autonome (onglet **Week-end**, puis une par équipe)
- `calendrier.ics` — flux à souscrire dans Outlook / Google / Apple
- `matchs.json` — données brutes
- `suivi_handball.csv` — export tableur
- `logos/` — logos des clubs, téléchargés depuis FFHandball

## Fonctionnement

1. `handapi.fr` sert uniquement à découvrir les clubs, équipes, compétitions
   et poules (aucun identifiant n'est codé en dur).
2. Les matchs et les classements sont lus sur `ffhandball.fr`, seule source
   faisant foi pour les scores.
3. Les poules des tours de coupe à venir sont retrouvées via la fiche de la
   compétition, car les engagements ne listent que la phase en cours.
4. La page, le calendrier, le JSON et le CSV sont réécrits, puis publiés.

## Publication

Voir [`deploiement/README.md`](deploiement/README.md).

La collecte tourne toutes les 3 h dans GitHub Actions
(`.github/workflows/collecte.yml`) puis publie par SFTP sur l'hébergement IONOS.
Si la collecte est incomplète (site FFHandball indisponible), rien n'est publié
et la version en ligne reste intacte.

Le planificateur est commenté tant que les secrets SFTP ne sont pas créés :
en attendant, la collecte se lance à la main (`Actions` → `Run workflow`).
