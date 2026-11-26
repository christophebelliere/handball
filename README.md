# Suivi handball — Bonsecours / Belbeuf

Page web, flux calendrier `.ics` et classements pour trois équipes, alimentés
par les données officielles de [ffhandball.fr](https://www.ffhandball.fr).

- `index.html` — page autonome (onglet **Week-end**, puis une par équipe)
- `calendrier.ics` — flux à souscrire dans Outlook / Google / Apple
- `matchs.json` — données brutes
- `suivi_handball.csv` — export tableur
- `logos/` — logos des clubs, téléchargés depuis FFHandball
- `manifest.webmanifest` + `icones/` — installation sur l'écran d'accueil
  (iPhone / Android), sans cache local

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

La collecte tourne dans GitHub Actions (`.github/workflows/collecte.yml`) et
publie sur **Cloudflare Pages**, servi par <https://handball.belliere.fr>. Si la
collecte est incomplète (site FFHandball indisponible), rien n'est publié et la
version en ligne reste intacte.

Cadence : toutes les 3 h, plus un passage toutes les 30 min le samedi après-midi
quand une équipe joue. Un déclencheur Cloudflare double le planificateur de
GitHub, dont les exécutions sautent parfois ; un garde-fou de fraîcheur empêche
les collectes en double. Aucune machine personnelle n'est nécessaire.
