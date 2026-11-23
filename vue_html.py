#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rendu HTML du suivi handball.

Page autonome : aucun fichier externe, aucune police distante, aucune image.
Le style reprend une maquette type tableau de bord sportif (fond sombre,
bandeau degrade, onglets, scores encadres, classement).
"""

import hashlib
import json
import os
import unicodedata
from datetime import datetime, timedelta, timezone

# Facteurs de cadrage par logo (voir logos/cadrage.json) : certains fichiers
# FFHB contiennent de grandes marges transparentes, le logo parait alors minuscule.
CADRAGE_FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "logos", "cadrage.json")
_CADRAGE = None


def cadrage(chemin):
    global _CADRAGE
    if _CADRAGE is None:
        try:
            with open(CADRAGE_FICHIER, encoding="utf-8") as f:
                _CADRAGE = json.load(f)
        except Exception:
            _CADRAGE = {}
    try:
        return float(_CADRAGE.get(chemin) or 1.0)
    except (TypeError, ValueError):
        return 1.0

MOIS = ["janv.", "fevr.", "mars", "avr.", "mai", "juin",
        "juil.", "aout", "sept.", "oct.", "nov.", "dec."]

JOURS_LONGS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_LONGS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
              "aout", "septembre", "octobre", "novembre", "decembre"]

STOPWORDS = {"DE", "DU", "DES", "LE", "LA", "LES", "ET", "SUR", "EN", "AUX", "AU"}

ORDRE_FILTRES = ["Championnat", "Preparation", "Coupe"]
LIBELLE_FILTRE = {"Championnat": "Championnat",
                  "Preparation": "Preparation",
                  "Coupe": "Coupe"}

# Ordre d'affichage des classements : le championnat fait reference toute la
# saison, la coupe est un episode. La phase preparatoire vient en dernier.
ORDRE_CLASSEMENT = {"Championnat": 0, "Coupe": 1, "Preparation": 2}


# ------------------------------------------------------------------ outils

def sans_accents(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def mots(nom):
    brut = sans_accents(nom).upper().replace("/", " ").replace("-", " ")
    return [m for m in brut.split() if m]


def monogramme(nom):
    sig = [m for m in mots(nom) if len(m) > 1 and m not in STOPWORDS]
    if not sig:
        sig = mots(nom)
    return "".join(m[0] for m in sig[:2]) or "?"


def teinte(nom):
    return int(hashlib.md5(str(nom).encode("utf-8")).hexdigest()[:6], 16) % 360


def date_courte(iso):
    if not iso:
        return None
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        return iso
    return f"{d.day:02d} {MOIS[d.month - 1]} {d.year}"


def filtre_de(m):
    phase = sans_accents(m.get("phase") or "").upper()
    comp = sans_accents(m.get("competition") or "").upper()
    if "PREPARATOIRE" in phase or "PREPA" in phase:
        return "Preparation"
    if "COUPE" in comp:
        return "Coupe"
    return "Championnat"


def notre_cote(m, club):
    c = sans_accents(club).upper()
    return ("domicile" if c in sans_accents(m["domicile"]).upper()
            else "exterieur" if c in sans_accents(m["exterieur"]).upper()
            else None)


# ------------------------------------------------------------------ week-end

def periode_weekend(ref):
    """Samedi et dimanche du week-end en cours (ou du prochain)."""
    j = ref.weekday()          # lundi=0 ... dimanche=6
    if j <= 4:                 # lundi -> vendredi : week-end a venir
        sam = ref + timedelta(days=5 - j)
    elif j == 5:               # samedi
        sam = ref
    else:                      # dimanche : le week-end a commence la veille
        sam = ref - timedelta(days=1)
    return sam, sam + timedelta(days=1)


def date_longue(d):
    return f"{JOURS_LONGS[d.weekday()]} {d.day} {MOIS_LONGS[d.month - 1]}"


def semaines_de_matchs(equipes):
    """Tous les week-ends comptant au moins un match, passes comme a venir.

    Le samedi sert de cle de regroupement : un match le samedi et un autre le
    dimanche du meme week-end forment un seul bloc. Chaque entree vaut
    {"samedi": date, "jours": [(date, [(match, equipe), ...])]}.
    """
    par_samedi = {}
    for eq in equipes:
        for m in eq.get("matchs", []):
            try:
                d = datetime.strptime(m.get("date") or "", "%Y-%m-%d").date()
            except ValueError:
                continue
            par_samedi.setdefault(periode_weekend(d)[0], []).append((m, eq))

    semaines = []
    for sam in sorted(par_samedi):
        jours = []
        for d in (sam, sam + timedelta(days=1)):
            lot = [(m, eq) for m, eq in par_samedi[sam]
                   if m.get("date") == d.isoformat()]
            lot.sort(key=lambda x: (x[0].get("heure") or "99:99",
                                    x[1]["libelle"]))
            if lot:
                jours.append((d, lot))
        if jours:
            semaines.append({"samedi": sam, "jours": jours})
    return semaines


def index_du_weekend(semaines, ref):
    """Week-end montre par defaut : celui en cours, sinon le suivant."""
    sam = periode_weekend(ref)[0]
    for i, s in enumerate(semaines):
        if s["samedi"] >= sam:
            return i
    return len(semaines) - 1


def badge(nom, logo=None, extra=""):
    """Pastille de club : logo officiel si disponible, sinon monogramme colore."""
    classes = "badge" + (" " + extra if extra else "") + (" a-logo" if logo else "")
    if logo:
        k = cadrage(logo.replace("logos/", ""))
        zoom = f' style="transform:scale({k:.2f})"' if k > 1.001 else ""
        img = (f'<img src="{logo}" alt="" loading="lazy"{zoom} '
               f'onerror="this.parentNode.classList.remove(\'a-logo\');this.remove()">')
    else:
        img = ""
    return (f'<span class="{classes}" style="--h:{teinte(nom)}">'
            f'{monogramme(nom)}{img}</span>')


# ------------------------------------------------------------------ style

CSS = """
:root{
  --bg:#0c0d10; --panel:#16171c; --panel2:#1d1f26; --line:#282a33;
  --txt:#f4f5f9; --muted:#9298a6; --accent:#e5177b; --accent2:#2f3aa8;
  --ok:#34d399; --warn:#fbbf24;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--txt); line-height:1.45;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1000px;margin:0 auto;padding:0 16px 40px}

/* ---------- bandeau ---------- */
header.top{
  background:linear-gradient(105deg,#e5177b 0%,#a3208f 38%,#4a2a9e 68%,#2f3aa8 100%);
  padding:26px 0 0; margin-bottom:22px;
  box-shadow:0 10px 40px rgba(0,0,0,.55);
}
header.top .wrap{padding-bottom:0}
.brand{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{
  margin:0; font-size:clamp(1.6rem,4.5vw,2.4rem); font-weight:800;
  letter-spacing:.14em; text-transform:uppercase; line-height:1;
}
.brand p{margin:8px 0 0;font-size:.82rem;opacity:.9;letter-spacing:.02em}
.gen{
  font-size:.7rem; text-transform:uppercase; letter-spacing:.08em;
  background:rgba(255,255,255,.16); padding:7px 12px; border-radius:999px;
  border:1px solid rgba(255,255,255,.22); white-space:nowrap;
}

/* ---------- onglets equipes ---------- */
nav.teams{display:flex;gap:8px;margin-top:22px;overflow-x:auto;scrollbar-width:none}
nav.teams::-webkit-scrollbar{display:none}
.team-tab{
  appearance:none;cursor:pointer;white-space:nowrap;
  background:rgba(0,0,0,.22); color:#fff; border:1px solid rgba(255,255,255,.28);
  border-bottom:none; border-radius:10px 10px 0 0;
  padding:12px 20px 13px; font-size:.86rem; font-weight:600; letter-spacing:.03em;
  opacity:.72; transition:opacity .15s, background .15s;
}
.team-tab:hover{opacity:1}
.team-tab.on{background:var(--panel);opacity:1;color:#fff}

/* ---------- panneau ---------- */
.panel{display:none}
.js .panel{display:none}
.panel.on{display:block}
.js .panel.on{display:block}
.panel{
  background:var(--panel); border:1px solid var(--line); border-radius:14px;
  padding:20px 18px 22px;
}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.panel-head h2{margin:0;font-size:1.22rem;font-weight:700;letter-spacing:.01em}
.panel-head h2 small{color:var(--muted);font-weight:500;font-size:.8rem;margin-left:8px}

/* ---------- segments ---------- */
.seg{display:flex;gap:8px}
.seg-btn{
  appearance:none;cursor:pointer;background:transparent;color:var(--muted);
  border:1px solid var(--line); border-radius:999px; padding:8px 18px;
  font-size:.82rem;font-weight:600;letter-spacing:.02em;transition:.15s;
}
.seg-btn:hover{color:var(--txt);border-color:#3a3d48}
.seg-btn.on{color:var(--txt);border-color:#fff;background:rgba(255,255,255,.06)}

/* ---------- filtres ---------- */
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.chip{
  appearance:none;cursor:pointer;background:var(--panel2);color:var(--muted);
  border:1px solid var(--line);border-radius:8px;padding:7px 14px;
  font-size:.76rem;font-weight:600;letter-spacing:.03em;transition:.15s;
}
.chip:hover{color:var(--txt)}
.chip.on{background:linear-gradient(100deg,var(--accent),#a3208f);color:#fff;border-color:transparent}

/* ---------- tableaux ---------- */
.tablewrap{overflow-x:auto;margin:0 -6px}
table{width:100%;border-collapse:separate;border-spacing:0 6px;font-size:.88rem}
thead th{
  text-align:left;font-size:.68rem;font-weight:600;text-transform:uppercase;
  letter-spacing:.09em;color:var(--muted);padding:0 12px 6px;white-space:nowrap;
}
tbody td{
  padding:11px 12px;background:var(--panel2);border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);vertical-align:middle;
}
tbody tr td:first-child{border-left:1px solid var(--line);border-radius:9px 0 0 9px}
tbody tr td:last-child{border-right:1px solid var(--line);border-radius:0 9px 9px 0}
tbody tr:hover td{background:#232630}
[hidden]{display:none!important}
tr[hidden]{display:none}

.c-date{white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums;font-size:.82rem;width:1%}
.c-team{width:40%}
.c-team .nom{display:inline-block;vertical-align:middle;max-width:calc(100% - 38px);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c-team.nous .nom{font-weight:700;color:#fff}
.c-team:not(.nous) .nom{color:#c3c8d4}
.c-score{width:1%;white-space:nowrap;text-align:center}
.c-comp{width:1%;white-space:nowrap;color:var(--muted);font-size:.76rem}

.badge{
  position:relative; overflow:hidden;
  display:inline-flex;align-items:center;justify-content:center;
  width:26px;height:26px;border-radius:50%;margin-right:9px;
  font-size:.62rem;font-weight:800;letter-spacing:.02em;vertical-align:middle;
  background:hsl(var(--h) 62% 34%); color:#fff;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.14);
}
.badge img{
  position:absolute; inset:0; width:100%; height:100%;
  object-fit:contain; padding:1px;
  filter:drop-shadow(0 0 1.2px rgba(0,0,0,.6));
}
.badge.a-logo{background:#f2f4f8;box-shadow:inset 0 0 0 1px rgba(0,0,0,.18)}
.badge-lg{width:34px;height:34px;font-size:.7rem;margin-right:11px;border-radius:9px}
.badge-lg img{padding:3px}

.score{
  display:inline-block;min-width:78px;padding:7px 12px;border-radius:8px;
  border:1px solid #3a3d48;background:#101116;
  font-variant-numeric:tabular-nums;font-weight:700;letter-spacing:.04em;
}
.score.avenir{border-style:dashed;border-color:#3f4350;color:var(--muted);font-weight:600}
.score.code{border-color:rgba(251,191,36,.55);color:var(--warn)}
.score.code small{display:block;font-size:.56rem;letter-spacing:.06em;color:var(--muted);font-weight:500;margin-top:2px}

/* ---------- classement ---------- */
h3.h3{
  margin:26px 0 10px;font-size:.72rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);
}
.cl-titre{font-size:.84rem;font-weight:600;margin:20px 0 8px;color:#dfe3ec}
.cl-titre .tag{
  font-size:.62rem;background:rgba(251,191,36,.14);color:var(--warn);
  padding:2px 7px;border-radius:5px;margin-left:8px;letter-spacing:.04em;
  text-transform:uppercase;vertical-align:middle;
}
table.cl{font-size:.82rem;border-spacing:0 4px}
table.cl td{padding:9px 10px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
table.cl td:first-child{border-left:1px solid var(--line);border-radius:8px 0 0 8px}
table.cl td:last-child{border-right:1px solid var(--line);border-radius:0 8px 8px 0}
table.cl tr.moi td{background:#232a3d;border-color:#33405c}
table.cl tr.moi td:first-child{box-shadow:inset 3px 0 0 var(--accent)}
table.cl .num{text-align:center;font-variant-numeric:tabular-nums;color:var(--muted)}
table.cl .pts{font-weight:800;color:#fff;text-align:center}

.empty{color:var(--muted);font-size:.85rem;font-style:italic;padding:14px 4px}
.vide{color:var(--muted);font-style:italic;font-weight:400}

/* ---------- programme du week-end ---------- */
.w-note{
  margin:-4px 0 18px;font-size:.78rem;font-style:italic;color:var(--muted);
}
.weekend .jour + .jour{margin-top:22px}
.jour-titre{
  font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);margin:0 0 10px;
}
.jour-titre b{color:#dfe3ec;font-weight:700}
.wmatch{
  display:grid;grid-template-columns:64px minmax(0,1fr) auto;
  column-gap:14px;align-items:center;
  background:var(--panel2);border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;margin-bottom:8px;
}
.wmatch:hover{background:#232630}
.w-heure{
  font-size:1.06rem;font-weight:800;font-variant-numeric:tabular-nums;
  letter-spacing:.02em;color:#fff;
}
.w-eq{min-width:0}
.w-ligne{display:flex;align-items:center;min-width:0}
.w-ligne + .w-ligne{margin-top:5px}
.w-ligne .nom{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.w-ligne.nous .nom{font-weight:700;color:#fff}
.w-ligne:not(.nous) .nom{color:#c3c8d4}
.w-score{justify-self:end}
.w-meta{
  grid-column:2 / -1;display:flex;align-items:center;gap:10px;min-width:0;
  margin-top:9px;font-size:.75rem;color:var(--muted);
}
.w-tag{
  flex:none;background:rgba(255,255,255,.1);border:1px solid #3b4050;
  border-radius:5px;padding:2px 8px;font-size:.7rem;font-weight:800;
  letter-spacing:.06em;text-transform:uppercase;color:#fff;
}
.w-comp{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* navigation d'un week-end a l'autre : inutile sans JavaScript, d'ou html.js */
.we-nav{display:none;align-items:center;gap:8px}
html.js .we-nav{display:flex}
.we-btn{
  width:30px;height:30px;flex:none;display:grid;place-items:center;padding:0 0 2px;
  background:rgba(255,255,255,.07);border:1px solid var(--line);border-radius:8px;
  color:#e7eaf2;font-size:1.15rem;line-height:1;cursor:pointer;
}
.we-btn:hover:not(:disabled){background:rgba(255,255,255,.16);color:#fff}
.we-btn:disabled{opacity:.3;cursor:default}
.we-libelle{
  font-size:.8rem;color:var(--muted);font-variant-numeric:tabular-nums;
}
.w-fdm{
  flex:none;margin-left:auto;display:inline-flex;align-items:center;gap:5px;
  background:rgba(255,255,255,.07);border:1px solid var(--line);
  border-radius:6px;padding:3px 9px;font-size:.71rem;font-weight:600;
  color:#cfd4e0;text-decoration:none;white-space:nowrap;
}
.w-fdm:hover{background:rgba(255,255,255,.16);border-color:#4a5163;color:#fff}
.w-fdm span{font-size:.82rem;line-height:1}
.w-fdm-court{display:none}

footer.pied{
  text-align:center;font-size:.74rem;color:#5f6675;padding:26px 16px 10px;
}
footer.pied a{color:#9aa3b8;text-decoration:none;border-bottom:1px dotted #565d6d}
footer.pied a:hover{color:#fff}

@media(max-width:620px){
  .panel{padding:16px 12px 18px}
  .panel-head h2{font-size:1.08rem}
  .panel-head h2 small{display:block;margin:6px 0 0;font-size:.76rem}
  .team-tab{padding:10px 13px;font-size:.8rem}
  .seg-btn{padding:7px 14px;font-size:.78rem}

  /* matchs : une carte par ligne */
  .tablewrap{overflow:visible;margin:0}
  table{border-spacing:0;font-size:.86rem}
  table.cl{font-size:.79rem}
  table:not(.cl) thead{display:none}
  table:not(.cl) tbody{display:block}
  table:not(.cl) tbody tr{
    display:grid; grid-template-columns:1fr auto;
    grid-template-areas:"date date" "e1 score" "e2 score";
    align-items:center; column-gap:10px;
    background:var(--panel2); border:1px solid var(--line);
    border-radius:10px; padding:10px 12px; margin-bottom:8px;
  }
  table:not(.cl) tbody tr:hover td{background:none}
  table:not(.cl) tbody td{
    background:none; border:0; border-radius:0; padding:0; width:auto;
  }
  table:not(.cl) td.c-date{
    grid-area:date; font-size:.72rem; letter-spacing:.04em;
    text-transform:uppercase; margin-bottom:6px;
  }
  table:not(.cl) td.c-date::after{
    content:" \\00b7  " attr(data-comp);
    color:#6e7484; text-transform:none; letter-spacing:0;
  }
  table:not(.cl) td.c-team:nth-of-type(2){grid-area:e1}
  table:not(.cl) td.c-team:nth-of-type(4){grid-area:e2}
  table:not(.cl) td.c-team .nom{display:inline; max-width:none; white-space:normal}
  table:not(.cl) td.c-team:not(.nous) .nom{color:#aeb4c2}
  table:not(.cl) td.c-score{grid-area:score; align-self:center}
  table:not(.cl) td.c-comp{display:none}
  .badge{width:22px;height:22px;margin-right:7px;font-size:.56rem}
  .score{min-width:74px;padding:6px 10px;font-size:.84rem}

  /* classement : colonnes secondaires masquees */
  table.cl th, table.cl td{padding:8px 6px}
  table.cl th:nth-child(5), table.cl td:nth-child(5),
  table.cl th:nth-child(6), table.cl td:nth-child(6),
  table.cl th:nth-child(7), table.cl td:nth-child(7),
  table.cl th:nth-child(9), table.cl td:nth-child(9){display:none}
  table.cl .badge{display:none}

  /* programme : colonnes resserrees */
  .wmatch{grid-template-columns:52px minmax(0,1fr) auto;padding:11px 12px;column-gap:10px}
  .w-heure{font-size:.94rem}
  .w-ligne .nom{font-size:.82rem;line-height:1.3}
  .w-meta{font-size:.7rem;margin-top:8px;flex-wrap:wrap;gap:8px}
  .we-libelle{font-size:.73rem}
  .we-btn{width:28px;height:28px}
  .w-fdm{font-size:.66rem;padding:3px 7px;gap:4px}
  .w-fdm-long{display:none}
  .w-fdm-court{display:inline}
}
"""

JS = """
document.documentElement.classList.add('js');

// Le tableau est ecrit dans l'ordre chronologique : c'est ce qu'il faut pour
// « A venir » (le prochain match en tete). Pour « Resultats », on veut l'inverse,
// le dernier match joue en premier. Plutot que deux rendus, on deplace les
// lignes existantes : aucun aller-retour reseau, aucun doublon dans le HTML.
function ordonner(p, tab){
  var tb = p.querySelector('tbody');
  if (!tb) return;
  var sens = (tab === 'joue') ? -1 : 1;
  var lignes = Array.prototype.slice.call(tb.querySelectorAll('tr[data-m]'));
  lignes.sort(function(a, b){
    var ka = a.getAttribute('data-ordre') || '';
    var kb = b.getAttribute('data-ordre') || '';
    if (ka === kb) return 0;
    return (ka < kb ? -1 : 1) * sens;
  });
  for (var i = 0; i < lignes.length; i++) tb.appendChild(lignes[i]);
}

function appliquer(p){
  var tab = p.dataset.tab || 'avenir';
  var f = p.dataset.filtre || '*';
  ordonner(p, tab);
  var n = 0;
  p.querySelectorAll('tbody tr[data-m]').forEach(function(tr){
    var ok = (tr.dataset.etat === tab) && (f === '*' || tr.dataset.f === f);
    tr.hidden = !ok;
    if (ok) n++;
  });
  var vide = p.querySelector('.empty');
  if (vide) vide.hidden = (n !== 0);
}
document.querySelectorAll('.team-tab').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.team-tab').forEach(function(b){ b.classList.toggle('on', b === btn); });
    document.querySelectorAll('.panel').forEach(function(p){ p.classList.toggle('on', p.dataset.team === btn.dataset.team); });
  });
});
document.querySelectorAll('.panel').forEach(function(p){
  p.querySelectorAll('.seg-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      p.querySelectorAll('.seg-btn').forEach(function(b){ b.classList.toggle('on', b === btn); });
      p.dataset.tab = btn.dataset.tab;
      appliquer(p);
    });
  });
  p.querySelectorAll('.chip').forEach(function(chip){
    chip.addEventListener('click', function(){
      p.querySelectorAll('.chip').forEach(function(c){ c.classList.toggle('on', c === chip); });
      p.dataset.filtre = chip.dataset.filtre;
      appliquer(p);
    });
  });
  appliquer(p);
});

// ---------------- navigation du programme du week-end
// Tous les week-ends sont deja ecrits dans la page ; un seul est visible. Les
// fleches deplacent l attribut hidden : pas de requete, pas de rechargement.
(function(){
  var p = document.querySelector('.panel[data-team="weekend"]');
  if (!p) return;
  var blocs = p.querySelectorAll('.we');
  if (blocs.length < 2) return;
  var libelle = p.querySelector('.we-libelle');
  var boutons = p.querySelectorAll('.we-btn');
  var note = p.querySelector('[data-note]');
  var defaut = parseInt(p.getAttribute('data-defaut'), 10) || 0;
  var i = defaut;

  function montrer(n){
    if (n < 0 || n >= blocs.length || n === i) return;
    blocs[i].hidden = true;
    i = n;
    var b = blocs[i];
    b.hidden = false;
    var total = parseInt(b.getAttribute('data-total'), 10) || 0;
    libelle.textContent = b.getAttribute('data-periode') + ' \\u00b7 ' +
                          total + ' match' + (total > 1 ? 's' : '');
    boutons[0].disabled = (i === 0);
    boutons[1].disabled = (i === blocs.length - 1);
    if (note) note.hidden = (i !== defaut);
  }

  boutons[0].addEventListener('click', function(){ montrer(i - 1); });
  boutons[1].addEventListener('click', function(){ montrer(i + 1); });
})();
"""


# ------------------------------------------------------------------ rendu

def ligne_match(m, club):
    cote = notre_cote(m, club)
    filtre = filtre_de(m)

    classes = ["c-team"]
    if cote == "domicile":
        classes.append("nous")
    dom = (f'{badge(m["domicile"], m.get("logo_dom"))}<span class="nom" title="{m["domicile"]}">'
           f'{m["domicile"]}</span>')
    classes2 = ["c-team"]
    if cote == "exterieur":
        classes2.append("nous")
    ext = (f'{badge(m["exterieur"], m.get("logo_ext"))}<span class="nom" title="{m["exterieur"]}">'
           f'{m["exterieur"]}</span>')

    if m["joue"]:
        valeur = f'{m["score_dom"]}&nbsp;:&nbsp;{m["score_ext"]}'
        cls = "score" if m.get("score_valide", True) else "score code"
        note = "" if m.get("score_valide", True) else "<small>code FFHB</small>"
        box = f'<span class="{cls}">{valeur}{note}</span>'
        etat = "joue"
    else:
        box = f'<span class="score avenir">{m["heure"] or "--:--"}</span>'
        etat = "avenir"

    date = date_courte(m.get("date"))
    if not date:
        date = '<span class="vide">a definir</span>'

    # Cle de tri lisible par le navigateur : "date heure", donc comparable
    # comme du texte. Sert a inverser l'ordre de l'onglet Resultats (du plus
    # recent au plus ancien) sans recharger la page.
    ordre = f"{m.get('date') or '9999-99-99'} {m.get('heure') or '99:99'}"

    return (
        f'<tr data-m data-etat="{etat}" data-f="{filtre}" data-ordre="{ordre}">'
        f'<td class="c-date" data-comp="{filtre}">{date}</td>'
        f'<td class="{" ".join(classes)}">{dom}</td>'
        f'<td class="c-score">{box}</td>'
        f'<td class="{" ".join(classes2)}">{ext}</td>'
        f'<td class="c-comp">{filtre}</td>'
        f'</tr>'
    )


def bloc_classement(cl, club):
    nos = {sans_accents(x).upper() for x in cl.get("nos_equipes", [])}
    titre = f'<div class="cl-titre">{cl["competition"]}'
    if "PREPARATOIRE" in (cl.get("phase") or "").upper():
        titre += '<span class="tag">preparation</span>'
    titre += "</div>"

    corps = []
    for l in cl["lignes"]:
        moi = sans_accents(l.get("equipe")).upper() in nos
        corps.append(
            f'<tr class="{"moi" if moi else ""}">'
            f'<td class="num">{l.get("place")}</td>'
            f'<td>{badge(l.get("equipe"), l.get("logo"))}{l.get("equipe")}</td>'
            f'<td class="pts">{l.get("points")}</td>'
            f'<td class="num">{l.get("joues")}</td>'
            f'<td class="num">{l.get("gagnes")}</td>'
            f'<td class="num">{l.get("nuls")}</td>'
            f'<td class="num">{l.get("perdus")}</td>'
            f'<td class="num">{l.get("difference")}</td>'
            f'<td class="num" title="{l.get("buts_pour")} buts marques, {l.get("buts_contre")} encaisses">'
            f'{l.get("buts_pour")}/{l.get("buts_contre")}</td>'
            f'</tr>'
        )

    return (
        titre
        + '<div class="tablewrap"><table class="cl"><thead><tr>'
          '<th>#</th><th>Equipe</th><th style="text-align:center">Pts</th>'
          '<th style="text-align:center">J</th><th style="text-align:center">G</th>'
          '<th style="text-align:center">N</th><th style="text-align:center">P</th>'
          '<th style="text-align:center" title="Difference de buts">Diff</th>'
          '<th style="text-align:center" title="Buts marques / buts encaisses">Buts</th>'
          '</tr></thead><tbody>'
        + "".join(corps)
        + "</tbody></table></div>"
    )


def url_feuille(m):
    """Adresse du PDF officiel de la feuille de match, sinon None.

    ffhandball.fr nomme chaque feuille par un code de 7 caracteres (WAGVOAU) et
    la sert a l'adresse fdm.fdme.ffhandball.fr/W/A/G/V/WAGVOAU.pdf : les quatre
    premiers caracteres deviennent des dossiers. La page de la rencontre sert de
    repli quand le code manque.
    """
    code = str(m.get("fdm") or "").strip()
    if len(code) == 7:
        return "https://fdm.fdme.ffhandball.fr/" + "/".join(code[:4]) + f"/{code}.pdf"
    if m.get("id") and m.get("url"):
        return f'{m["url"]}rencontre-{m["id"]}/'
    return None


def ligne_weekend(m, eq):
    club = eq["club"]
    court = eq["libelle"].split()[0]
    cote = notre_cote(m, club)

    def cote_equipe(nom, logo, nous):
        return (f'<div class="w-ligne{" nous" if nous else ""}">'
                f'{badge(nom, logo)}'
                f'<span class="nom" title="{nom}">{nom}</span></div>')

    equipes = (cote_equipe(m["domicile"], m.get("logo_dom"), cote == "domicile")
               + cote_equipe(m["exterieur"], m.get("logo_ext"), cote == "exterieur"))

    if m["joue"]:
        valeur = f'{m["score_dom"]}&nbsp;:&nbsp;{m["score_ext"]}'
        cls = "score" if m.get("score_valide", True) else "score code"
        note = "" if m.get("score_valide", True) else "<small>code FFHB</small>"
        score = f'<span class="{cls}">{valeur}{note}</span>'
    else:
        score = ""

    detail = (m.get("competition") or "").replace('"', "&quot;")
    if m.get("phase"):
        detail += " / " + str(m["phase"]).replace('"', "&quot;")

    # Feuille de match : PDF officiel de la federation quand le code est connu,
    # sinon la page de la rencontre. Affichee seulement sur un match joue.
    fdm = ""
    cible = url_feuille(m) if m["joue"] else None
    if cible:
        pdf = cible.endswith(".pdf")
        titre = ("Telecharger la feuille de match (PDF)"
                 if pdf else "Ouvrir la rencontre sur ffhandball.fr")        # Deux libelles : « Feuille de match » sur ecran large, « FDME » sur
        # mobile ou la ligne doit tenir a cote de « Championnat ».
        fdm = (f'<a class="w-fdm" href="{cible}" target="_blank" rel="noopener"'
               f' title="{titre} - nouvel onglet">'
               '<span class="w-fdm-long">Feuille de match</span>'
               '<span class="w-fdm-court">FDME</span>'
               '<span aria-hidden="true">&#8599;</span></a>')

    return (
        '<article class="wmatch">'
        f'<div class="w-heure">{m.get("heure") or "--:--"}</div>'
        f'<div class="w-eq">{equipes}</div>'
        f'<div class="w-score">{score}</div>'
        f'<div class="w-meta"><span class="w-tag">{court}</span>'
        f'<span class="w-comp" title="{detail}">{filtre_de(m)}</span>{fdm}</div>'
        '</article>'
    )


def bloc_weekend(equipes, ref):
    semaines = semaines_de_matchs(equipes)

    if not semaines:
        return """
  <section class="panel on" data-team="weekend" data-tab="avenir" data-filtre="*">
    <div class="panel-head"><h2>Programme du week-end</h2></div>
    <div class="empty">Aucun match date pour le moment : les prochaines
      journees ne sont pas encore programmees par la federation.</div>
  </section>"""

    actif = index_du_weekend(semaines, ref)

    def resume(s):
        dates = [d for d, _ in s["jours"]]
        if len(dates) == 1:
            periode = date_longue(dates[0])
        else:
            periode = f"{date_longue(dates[0])} et {date_longue(dates[-1])}"
        total = sum(len(lot) for _, lot in s["jours"])
        return periode + f" {dates[0].year}", total

    # Tous les week-ends sont ecrits dans la page, un seul est visible : les
    # fleches ne font que deplacer un attribut hidden, sans requete ni rechargement.
    blocs = []
    for i, s in enumerate(semaines):
        periode, total = resume(s)
        corps = "".join(
            f'<div class="jour"><div class="jour-titre">'
            f'<b>{date_longue(d)}</b></div>'
            + "".join(ligne_weekend(m, eq) for m, eq in lot)
            + "</div>"
            for d, lot in s["jours"]
        )
        blocs.append(
            f'<div class="we"{"" if i == actif else " hidden"}'
            f' data-periode="{periode}" data-total="{total}">{corps}</div>'
        )

    periode, total = resume(semaines[actif])
    libelle = f'{periode} &middot; {total} match{"s" if total > 1 else ""}'

    note = ""
    if semaines[actif]["samedi"] != periode_weekend(ref)[0]:
        note = ('<p class="w-note" data-note>Aucun match ce week-end : '
                'voici le week-end suivant.</p>')

    return f"""
  <section class="panel on" data-team="weekend" data-tab="avenir" data-filtre="*"
           data-defaut="{actif}">
    <div class="panel-head">
      <h2>Programme du week-end</h2>
      <div class="we-nav">
        <button class="we-btn" type="button" data-sens="-1" title="Week-end precedent"
                aria-label="Week-end precedent"{' disabled' if actif == 0 else ''}>&lsaquo;</button>
        <div class="we-libelle" aria-live="polite">{libelle}</div>
        <button class="we-btn" type="button" data-sens="1" title="Week-end suivant"
                aria-label="Week-end suivant"{' disabled' if actif == len(semaines) - 1 else ''}>&rsaquo;</button>
      </div>
    </div>
    {note}
    <div class="weekend">{''.join(blocs)}</div>
  </section>"""


def bloc_equipe(eq, actif):
    club = eq["club"]
    matchs = eq["matchs"]

    lignes = "".join(ligne_match(m, club) for m in matchs)

    presents = {filtre_de(m) for m in matchs}
    filtres = [f for f in ORDRE_FILTRES if f in presents]
    chips = ['<button class="chip on" data-filtre="*">Tout</button>']
    for f in filtres:
        chips.append(f'<button class="chip" data-filtre="{f}">{LIBELLE_FILTRE[f]}</button>')

    if absent := (not matchs):
        lignes = ""

    # Championnat d'abord, puis coupe, puis phase preparatoire : c'est l'ordre
    # de lecture attendu, et stabilite du tri conserve l'ordre d'origine a
    # l'interieur de chaque categorie.
    classements = "".join(
        bloc_classement(cl, club)
        for cl in sorted(eq.get("classements", []),
                         key=lambda cl: ORDRE_CLASSEMENT.get(filtre_de(cl), 9))
    )
    bloc_cl = f'<h3 class="h3">Classement</h3>{classements}' if classements else ""

    court = eq["libelle"].split()[0]
    titre = eq["libelle"]
    club_txt = titre[len(court):].strip() or club

    return f"""
  <section class="panel{' on' if actif else ''}" data-team="{court}"
           data-tab="avenir" data-filtre="*">
    <div class="panel-head">
      <h2>{badge(club, eq.get("logo"), "badge-lg")}{court} <small>{club_txt}</small></h2>
      <div class="seg">
        <button class="seg-btn on" data-tab="avenir">A venir</button>
        <button class="seg-btn" data-tab="joue">Resultats</button>
      </div>
    </div>
    <div class="chips">{''.join(chips)}</div>
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>Date</th><th>Equipe 1</th><th style="text-align:center">Score</th>
          <th>Equipe 2</th><th>Competition</th>
        </tr></thead>
        <tbody>{lignes}</tbody>
      </table>
    </div>
    <div class="empty">Aucun match pour ce filtre.</div>
    {bloc_cl}
  </section>"""


def rendre_page(data):
    equipes = data["equipes"]

    try:
        genere = datetime.fromisoformat(data["genere_le"])
    except Exception:
        genere = datetime.now()

    onglets = ('<button class="team-tab on" data-team="weekend">Week-end</button>'
               + "".join(
                   f'<button class="team-tab" '
                   f'data-team="{eq["libelle"].split()[0]}">{eq["libelle"].split()[0]}</button>'
                   for eq in equipes
               ))

    panneaux = (bloc_weekend(equipes, genere.date())
                + "".join(bloc_equipe(eq, False) for eq in equipes))

    try:
        # genere_le est ecrit en heure du runner (UTC dans GitHub Actions) ;
        # on l'affiche explicitement en UTC pour eviter toute ambiguite.
        moment = datetime.fromisoformat(data["genere_le"])
        if moment.tzinfo is not None:
            moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
        maj = moment.strftime("%d/%m/%Y %H:%M UTC")
    except Exception:
        maj = data.get("genere_le", "")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Handball - Bonsecours / Belbeuf</title>
<style>{CSS}</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <div class="brand">
      <div>
        <h1>Handball</h1>
        <p>Bonsecours / Belbeuf &middot; saison 2026-2027</p>
      </div>
      <div class="gen">MAJ {maj}</div>
    </div>
    <nav class="teams">{onglets}</nav>
  </div>
</header>

<div class="wrap">
{panneaux}
</div>

<footer class="pied">
  Donnees officielles FFHandball &middot; logos des clubs via FFHandball &middot;
  <a href="calendrier.ics">S'abonner au calendrier</a> &middot;
  <a href="matchs.json">Donnees brutes</a>
</footer>

<script>{JS}</script>
</body>
</html>
"""
